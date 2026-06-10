# backend/app/routers/kata.py
#
# Full Kata Practice — XGBoost Real-time WebSocket Inference
#
# Architecture:
#   - Model: model_xgboost.pkl  (sklearn-compatible, loaded once with pickle)
#   - No TensorFlow / Keras anywhere in this file.
#   - Async queue: WebSocket receive loop only extracts features and enqueues;
#     a background asyncio worker runs inference and broadcasts results.
#   - Frame dropping: if queue backs up > 2 items, stale frames are discarded.
#   - Flattening: window deque (30 frames × 102 features) is np.ravel'd to
#     shape (1, 3060) before calling model.predict_proba().
#
# WebSocket protocol:
#   Client → Server:  { "landmarks": [{x, y, z, visibility} × 33] }
#   Server → Client:  { "status": "live"|"buffering",
#                        "frame_count": N,  "buffer_fill": N,
#                        "move": "GedanBarai",  "confidence": 0.96,
#                        "all_probs": [0.96, 0.02, 0.02],
#                        "dropped": 0 }

import os
import pickle
import asyncio
import collections

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.rag.feature_extractor import extract_102_features

router = APIRouter(prefix="/api/kata", tags=["kata"])

# ── Constants ──────────────────────────────────────────────────────────────────
SEQ_LEN    = 30                                        # frames in sliding window
FLAT_DIM   = SEQ_LEN * 102                            # 3060 — XGBoost input width
CLASS_NAMES = ["GedanBarai", "Gyakudzuki", "MaeGeri"] # must match training label order

PRODUCTION_BEST = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "models", "Results", "Production_Best",
))
XGB_MODEL_PATH = os.path.join(PRODUCTION_BEST, "model_xgboost.pkl")

# ── Model cache (loaded once at startup) ──────────────────────────────────────
_xgb_model = None


def load_kata_models():
    """
    Load model_xgboost.pkl from Production_Best/ into the module-level cache.
    Called once during FastAPI startup — pickle.load() is fast (~50 ms).
    No warm-up pass required (sklearn models are already compiled).
    """
    global _xgb_model
    if _xgb_model is not None:
        return

    if not os.path.exists(XGB_MODEL_PATH):
        print(f"[kata] WARN: XGBoost model not found at {XGB_MODEL_PATH}")
        return

    with open(XGB_MODEL_PATH, "rb") as f:
        _xgb_model = pickle.load(f)

    print(f"[kata] OK XGBoost model loaded from {XGB_MODEL_PATH}")


# ── Inference ─────────────────────────────────────────────────────────────────
def _run_xgb(window_list: list) -> dict:
    """
    Run XGBoost inference on a full 30-frame window.

    Input:  window_list — list of 30 feature vectors, each length 102.
    Output: dict with move, confidence, all_probs.

    Flattening: np.ravel(window_array)  →  shape (3060,)
                then np.expand_dims     →  shape (1, 3060)
    XGBoost predict_proba() is purely CPU / numpy — no event-loop blocking.
    """
    if _xgb_model is None:
        return {"move": "—", "confidence": 0.0, "all_probs": [0.0, 0.0, 0.0]}

    # (30, 102) → (1, 3060)
    window_arr = np.array(window_list, dtype=np.float32)   # (30, 102)
    X_flat     = window_arr.ravel()[np.newaxis, :]          # (1, 3060)

    probs = _xgb_model.predict_proba(X_flat)[0]             # (3,)
    idx   = int(np.argmax(probs))

    return {
        "move":       CLASS_NAMES[idx],
        "confidence": float(round(float(np.max(probs)), 4)),
        "all_probs":  [round(float(p), 4) for p in probs],
    }


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
@router.websocket("/ws")
async def kata_ws(websocket: WebSocket):
    """
    Real-time Kata WebSocket (XGBoost edition).

    Receive loop:   extracts 102-d features, pushes (frame_count, features) to queue.
    Worker task:    consumes queue, drops stale frames, maintains 30-frame deque,
                    runs _run_xgb() in thread-pool executor, broadcasts JSON.
    """
    await websocket.accept()

    queue:  asyncio.Queue      = asyncio.Queue()
    window: collections.deque  = collections.deque(maxlen=SEQ_LEN)
    loop = asyncio.get_event_loop()

    frame_count = 0
    drop_count  = 0
    last_result: dict | None = None

    print("[kata-ws] Client connected")

    # ── Background worker ──────────────────────────────────────────────────────
    async def inference_worker():
        nonlocal last_result, drop_count

        while True:
            item = await queue.get()
            if item is None:       # stop sentinel
                break

            fc, features = item

            # Drain queue — keep only the freshest frame
            while not queue.empty():
                next_item = queue.get_nowait()
                if next_item is None:
                    await queue.put(None)
                    return
                drop_count += 1
                fc, features = next_item

            window.append(features)

            # ── Buffering: window not yet full ──────────────────────────────
            if len(window) < SEQ_LEN:
                try:
                    await websocket.send_json({
                        "status":      "buffering",
                        "frame_count": fc,
                        "buffer_fill": len(window),
                        "buffer_size": SEQ_LEN,
                    })
                except Exception:
                    break
                continue

            # ── Inference in thread-pool (non-blocking) ─────────────────────
            last_result = await loop.run_in_executor(
                None, _run_xgb, list(window)
            )

            try:
                await websocket.send_json({
                    "status":      "live",
                    "frame_count": fc,
                    "buffer_fill": SEQ_LEN,
                    "buffer_size": SEQ_LEN,
                    "dropped":     drop_count,
                    **last_result,
                })
                drop_count = 0
            except Exception:
                break

    worker_task = asyncio.create_task(inference_worker())

    # ── Receive loop ───────────────────────────────────────────────────────────
    try:
        while True:
            data = await websocket.receive_json()
            landmarks = data.get("landmarks")
            if not landmarks or len(landmarks) < 33:
                await websocket.send_json({"status": "error", "detail": "Need 33 landmarks"})
                continue

            try:
                features = extract_102_features(landmarks)  # returns list of 102 floats
            except Exception as exc:
                await websocket.send_json({"status": "error", "detail": str(exc)})
                continue

            frame_count += 1
            await queue.put((frame_count, features))

    except WebSocketDisconnect:
        print("[kata-ws] Client disconnected")
    except Exception as exc:
        print(f"[kata-ws] Error: {exc}")
    finally:
        await queue.put(None)
        await worker_task
