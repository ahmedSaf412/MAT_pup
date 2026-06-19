# backend/app/routers/kata.py
#
# Full Kata Practice — Optimized Real-time WebSocket inference
#
# Optimizations applied:
#   Fix 1 — Direct Tensor Calling:
#     Replace model.predict(..., verbose=0) with model(..., training=False).numpy()
#     This skips Keras's internal batching/dispatch overhead for single-window calls,
#     reducing per-inference latency by ~30-60%.
#
#   Fix 2 — Inference Throttling:
#     Still accepts EVERY frame and maintains the sliding window.
#     Only runs AI inference every 5th frame (frame_count % 5 == 0).
#     For skipped frames, instantly broadcasts the cached last prediction.
#     This caps the inference rate to ~6 fps while the UI stays at 30 fps,
#     giving the CPU breathing room and reducing per-frame queuing delay.
#
#   Fix 3 — Model-Ready Gate:
#     A module-level asyncio.Event (_model_ready) is set once load_kata_models()
#     completes.  The WebSocket handler checks the gate and returns a "warming"
#     status message while the model is still loading, preventing the silent
#     conf=0.00 problem when a client connects before startup finishes.
#
# WebSocket protocol:
#   Client → Server:  { "landmarks": [{x, y, z, visibility} × 33] }
#   Server → Client:  { "status": "live"|"buffering"|"warming", "frame_count": N,
#                        "move": "...", "confidence": 0.0–1.0,
#                        "all_probs": [...], "throttled": true|false }

import os
import asyncio
import collections

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.rag.feature_extractor import extract_102_features

router = APIRouter(prefix="/api/kata", tags=["kata"])

# ── Constants ──────────────────────────────────────────────────────────────────
SEQ_LEN           = 30
INFER_EVERY_N     = 5          # Run inference every N-th frame (raised from 3→5)
CLASS_NAMES       = ["GedanBarai", "Gyakudzuki", "MaeGeri"]

PRODUCTION_BEST = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "models", "Results", "Production_Best"
))

DUAL_MODEL_PATH  = os.path.join(PRODUCTION_BEST, "best_dual_stem_fusion.keras")
XGB_MODEL_PATH   = os.path.join(PRODUCTION_BEST, "model_xgboost.pkl")

# Feature split (matches feature_extractor.py structure)
UPPER_DIM = 54   # landmarks 11-22 (×4) + angles 8-13
LOWER_DIM = 48   # landmarks 23-32 (×4) + angles 0-7

# ── Model cache (loaded once at startup) ──────────────────────────────────────
_kata_models: dict = {}

# ── Model-ready gate ──────────────────────────────────────────────────────────
# Set by load_kata_models() when the Dual-Stem model is ready.
# The WS handler awaits this before running inference.
_model_ready: asyncio.Event = asyncio.Event()


def load_kata_models():
    """Load the Dual-Stem Production_Best Keras model and XGBoost into the shared cache."""
    if "dual" in _kata_models and "xgb" in _kata_models:
        _model_ready.set()
        return  # already loaded

    import tensorflow as tf
    import pickle
    try:
        if "dual" not in _kata_models:
            _kata_models["dual"]  = tf.keras.models.load_model(DUAL_MODEL_PATH)
            # Warm-up: run a dummy inference to JIT-compile the TF graph
            dummy_102 = np.zeros((1, SEQ_LEN, UPPER_DIM + LOWER_DIM), dtype=np.float32)
            _kata_models["dual"]([dummy_102[:, :, :UPPER_DIM], dummy_102[:, :, UPPER_DIM:]], training=False)
            print(f"[kata] ✅ Dual-Stem model loaded & warmed up")
            
        if "xgb" not in _kata_models:
            with open(XGB_MODEL_PATH, "rb") as f:
                _kata_models["xgb"] = pickle.load(f)
            print(f"[kata] ✅ XGBoost model loaded")
            
        _model_ready.set()   # signal that inference is now available
    except Exception as e:
        print(f"[kata] ⚠️  Model load error: {e}")
        _model_ready.set()   # unblock WS even on error (it will return empty results)


# ── Inference ─────────────────────────────────────────────────────────────────
import tensorflow as tf   # noqa: E402 — imported here so it's not a hard dep at import time


def _run_inference(window_list: list) -> dict:
    """
    Run only the Dual-Stem model on a full 30-frame window using direct tensor calling.
    This avoids Keras batching overhead vs model.predict() and saves CPU cycles.

    Args:
        window_list: list[list[float]] of shape (30, 102)
    Returns:
        dict with move, confidence, all_probs (flat structure for frontend)
    """
    seq = np.array(window_list, dtype=np.float32)   # (30, 102)

    upper = tf.constant(seq[np.newaxis, :, :UPPER_DIM])  # (1, 30, 54)
    lower = tf.constant(seq[np.newaxis, :, UPPER_DIM:])  # (1, 30, 48)

    results = {}

    # ── Fix 1: Direct tensor call — no Keras predict() overhead ──────────────
    if "dual" in _kata_models:
        p_dual = _kata_models["dual"]([upper, lower], training=False).numpy()[0]
        idx    = int(np.argmax(p_dual))
        results["move"]       = CLASS_NAMES[idx]
        results["confidence"] = float(round(float(np.max(p_dual)), 4))
        results["all_probs"]  = [round(float(v), 4) for v in p_dual]
        
    if "xgb" in _kata_models:
        X_flat = seq.ravel()[np.newaxis, :]  # (1, 3060)
        p_xgb = _kata_models["xgb"].predict_proba(X_flat)[0]
        idx_xgb = int(np.argmax(p_xgb))
        results["xgb_move"]       = CLASS_NAMES[idx_xgb]
        results["xgb_confidence"] = float(round(float(np.max(p_xgb)), 4))
        results["xgb_probs"]      = [round(float(v), 4) for v in p_xgb]

    return results


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
@router.websocket("/ws")
async def kata_ws(websocket: WebSocket):
    """
    Real-time Kata WebSocket — optimized version.

    - Fix 3: Waits for _model_ready gate before starting inference.
             Sends "warming" pings while the model is still loading,
             so the client can display a human-readable status instead
             of silently returning conf=0.00.
    - Accepts one landmark frame per message.
    - Maintains a 30-frame sliding window (deque).
    - Fix 1: Uses direct tensor calling for inference (no model.predict overhead).
    - Fix 2: Runs inference every INFER_EVERY_N frames (throttling).
             For skipped frames, immediately broadcasts the cached last result.
    """
    await websocket.accept()
    print("[kata-ws] ✅ Client connected")

    # ── Fix 3: Wait for the Dual-Stem model to finish loading ────────────────
    if not _model_ready.is_set():
        print("[kata-ws] ⏳ Model not ready — sending warming pings")
        try:
            while not _model_ready.is_set():
                await websocket.send_json({"status": "warming", "detail": "AI model loading, please wait…"})
                # Wait up to 1 s for the event, then ping again
                try:
                    await asyncio.wait_for(_model_ready.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            print("[kata-ws] Client disconnected during warming")
            return
        print("[kata-ws] ✅ Model ready — starting inference")

    window: collections.deque = collections.deque(maxlen=SEQ_LEN)
    frame_count  = 0
    last_result: dict | None = None          # cached inference result
    loop = asyncio.get_event_loop()

    try:
        while True:
            data = await websocket.receive_json()
            landmarks = data.get("landmarks")
            if not landmarks or len(landmarks) < 33:
                await websocket.send_json({"status": "error", "detail": "Need 33 landmarks"})
                continue

            # Feature extraction (fast, pure Python/numpy — no blocking)
            try:
                features = extract_102_features(landmarks)
            except Exception as exc:
                await websocket.send_json({"status": "error", "detail": str(exc)})
                continue

            # Always push to sliding window — window never skips frames
            window.append(features)
            frame_count += 1

            # ── Buffering phase: window not yet full ─────────────────────────
            if len(window) < SEQ_LEN:
                await websocket.send_json({
                    "status":      "buffering",
                    "frame_count": frame_count,
                    "buffer_fill": len(window),
                    "buffer_size": SEQ_LEN,
                })
                continue

            # ── Fix 2: Throttle — only infer every INFER_EVERY_N frames ──────
            throttled = (frame_count % INFER_EVERY_N != 0)

            if not throttled:
                # Run real inference in thread pool so event loop stays unblocked
                last_result = await loop.run_in_executor(
                    None, _run_inference, list(window)
                )
                if last_result:
                    print(
                        f"[kata-ws] frame={frame_count} infer → "
                        f"{last_result.get('move', '?')} "
                        f"(conf={last_result.get('confidence', 0):.2f})"
                    )

            # ── Broadcast (real or cached result) ────────────────────────────
            if last_result:
                await websocket.send_json({
                    "status":      "live",
                    "frame_count": frame_count,
                    "buffer_fill": SEQ_LEN,
                    "buffer_size": SEQ_LEN,
                    "throttled":   throttled,
                    **last_result,
                })

    except WebSocketDisconnect:
        print("[kata-ws] Client disconnected")
    except Exception as exc:
        print(f"[kata-ws] Error: {exc}")
        try:
            await websocket.send_json({"status": "error", "detail": str(exc)})
        except Exception:
            pass

