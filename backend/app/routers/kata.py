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
#     Only runs AI inference every 3rd frame (frame_count % 3 == 0).
#     For skipped frames, instantly broadcasts the cached last prediction.
#     This caps the inference rate to ~10 fps while the UI stays at 30 fps.
#
# WebSocket protocol:
#   Client → Server:  { "landmarks": [{x, y, z, visibility} × 33] }
#   Server → Client:  { "status": "live"|"buffering", "frame_count": N,
#                        "dual_stem": {...}, "single_v1": {...}, "consensus": "...",
#                        "throttled": true|false }

import os
import asyncio
import collections

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.rag.feature_extractor import extract_102_features

router = APIRouter(prefix="/api/kata", tags=["kata"])

# ── Constants ──────────────────────────────────────────────────────────────────
SEQ_LEN           = 30
INFER_EVERY_N     = 3          # Run inference every N-th frame
CLASS_NAMES       = ["GedanBarai", "Gyakudzuki", "MaeGeri"]

PRODUCTION_BEST = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "models", "Results", "Production_Best"
))

DUAL_MODEL_PATH  = os.path.join(PRODUCTION_BEST, "best_dual_stem_fusion.keras")
SINV1_MODEL_PATH = os.path.join(PRODUCTION_BEST, "best_single_bilstmV1.keras")

# Feature split (matches feature_extractor.py structure)
UPPER_DIM = 54   # landmarks 11-22 (×4) + angles 8-13
LOWER_DIM = 48   # landmarks 23-32 (×4) + angles 0-7

# ── Model cache (loaded once at startup) ──────────────────────────────────────
_kata_models: dict = {}


def load_kata_models():
    """Load both Production_Best Keras models into the shared cache."""
    if "dual" in _kata_models:
        return  # already loaded

    import tensorflow as tf
    try:
        _kata_models["dual"]  = tf.keras.models.load_model(DUAL_MODEL_PATH)
        _kata_models["sinv1"] = tf.keras.models.load_model(SINV1_MODEL_PATH)
        # Warm-up: run a dummy inference to JIT-compile the TF graph
        dummy_102 = np.zeros((1, SEQ_LEN, UPPER_DIM + LOWER_DIM), dtype=np.float32)
        _kata_models["dual"]([dummy_102[:, :, :UPPER_DIM], dummy_102[:, :, UPPER_DIM:]], training=False)
        _kata_models["sinv1"](dummy_102, training=False)
        print(f"[kata] ✅ Dual-Stem model loaded & warmed up")
        print(f"[kata] ✅ Single-V1 model loaded & warmed up")
    except Exception as e:
        print(f"[kata] ⚠️  Model load error: {e}")


# ── Inference ─────────────────────────────────────────────────────────────────
import tensorflow as tf   # noqa: E402 — imported here so it's not a hard dep at import time


def _run_inference(window_list: list) -> dict:
    """
    Run both models on a full 30-frame window using direct tensor calling.
    This avoids Keras batching overhead vs model.predict().

    Args:
        window_list: list[list[float]] of shape (30, 102)
    Returns:
        dict with dual_stem, single_v1, consensus
    """
    seq = np.array(window_list, dtype=np.float32)   # (30, 102)

    upper = tf.constant(seq[np.newaxis, :, :UPPER_DIM])  # (1, 30, 54)
    lower = tf.constant(seq[np.newaxis, :, UPPER_DIM:])  # (1, 30, 48)
    full  = tf.constant(seq[np.newaxis])                  # (1, 30, 102)

    results = {}

    # ── Fix 1: Direct tensor call — no Keras predict() overhead ──────────────
    if "dual" in _kata_models:
        p_dual = _kata_models["dual"]([upper, lower], training=False).numpy()[0]
        idx    = int(np.argmax(p_dual))
        results["dual_stem"] = {
            "move":       CLASS_NAMES[idx],
            "confidence": float(round(float(np.max(p_dual)), 4)),
            "all_probs":  [round(float(v), 4) for v in p_dual],
        }

    if "sinv1" in _kata_models:
        p_v1 = _kata_models["sinv1"](full, training=False).numpy()[0]
        idx  = int(np.argmax(p_v1))
        results["single_v1"] = {
            "move":       CLASS_NAMES[idx],
            "confidence": float(round(float(np.max(p_v1)), 4)),
            "all_probs":  [round(float(v), 4) for v in p_v1],
        }

    # ── Consensus ─────────────────────────────────────────────────────────────
    moves = [r["move"] for r in results.values()]
    results["consensus"] = moves[0] if len(set(moves)) == 1 else "Disagree"

    return results


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
@router.websocket("/ws")
async def kata_ws(websocket: WebSocket):
    """
    Real-time Kata WebSocket — optimized version.

    - Accepts one landmark frame per message.
    - Maintains a 30-frame sliding window (deque).
    - Fix 1: Uses direct tensor calling for inference (no model.predict overhead).
    - Fix 2: Runs inference every INFER_EVERY_N frames (throttling).
             For skipped frames, immediately broadcasts the cached last result.
    """
    await websocket.accept()

    window: collections.deque = collections.deque(maxlen=SEQ_LEN)
    frame_count  = 0
    last_result: dict | None = None          # cached inference result
    loop = asyncio.get_event_loop()

    print("[kata-ws] ✅ Client connected")
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
                print(
                    f"[kata-ws] frame={frame_count} infer → "
                    f"{last_result.get('consensus', '?')} "
                    f"(dual={last_result.get('dual_stem', {}).get('confidence', 0):.2f})"
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
