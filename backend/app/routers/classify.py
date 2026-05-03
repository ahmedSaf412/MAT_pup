# backend/app/routers/classify.py
#
# Three-layer OOD guard:
#   Layer 1 — Confidence threshold  (fast, always active)
#   Layer 2 — Margin check          (fast, always active)
#   Layer 3 — DTW validation        (slower, only when exampler_sequences.json exists)
#             If the model says "gedan_barai" but DTW thinks "mae_geri" is a
#             much better fit, the DTW winner overrides the model prediction.

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
import tensorflow as tf
import os
import time

from app.rag.ood_config import (
    CONFIDENCE_THRESHOLD,
    MARGIN_THRESHOLD,
    DTW_OVERRIDE_RATIO,
    DTW_UNKNOWN_THRESHOLD,
)
from app.rag.dtw_comparator import score_all_classes   # DTW distances per class

router = APIRouter(prefix="/api", tags=["classification"])

# ── Constants ─────────────────────────────────────────────────────────────────
CLASS_NAMES = ["mae_geri", "gyaku_zuki", "gedan_barai"]

# ── Model cache ───────────────────────────────────────────────────────────────
_model_cache = {}

def load_model(model_name: str, feature_set: str):
    key = f"{model_name}_{feature_set}"
    if key not in _model_cache:
        model_path = os.path.join("app", "models", "Results", f"{model_name}_{feature_set}.keras")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        _model_cache[key] = tf.keras.models.load_model(model_path)
        print(f"✅ Loaded: {model_path}")
    return _model_cache[key]


# ── Request / Response schemas ────────────────────────────────────────────────
class FrameData(BaseModel):
    angles: Optional[List[float]] = None
    coords: Optional[List[float]] = None

class ClassifyRequest(BaseModel):
    frames: List[FrameData]
    feature_set: str = "angles14"
    model: str = "Bi-LSTM"

class ClassifyResponse(BaseModel):
    move: str
    confidence: float
    move_id: str
    inference_time_ms: float
    all_probabilities: List[float]
    is_unknown: bool = False
    rejection_reason: Optional[str] = None


# ── OOD helper ────────────────────────────────────────────────────────────────
def _dtw_ood_check(
    raw_angles_01: np.ndarray,    # (30, 14) — normalized 0-1 angles
    predicted_class: str,
) -> tuple[bool, str, str]:
    """
    Layer-3 DTW validation.

    Returns (is_ood, corrected_move_id, reason_string).
    corrected_move_id is the DTW-best class (may differ from predicted_class).
    """
    # Convert normalized angles (0-1) to degrees for DTW comparison
    user_angles_deg = raw_angles_01 * 180.0          # (30, 14) in degrees

    dtw_scores = score_all_classes(user_angles_deg)
    if not dtw_scores:
        # exampler_sequences.json not available — skip this layer
        return False, predicted_class, ""

    best_class = min(dtw_scores, key=dtw_scores.get)
    best_dist  = dtw_scores[best_class]
    pred_dist  = dtw_scores.get(predicted_class, best_dist)

    # Move is totally unlike anything in our reference set
    if best_dist > DTW_UNKNOWN_THRESHOLD:
        reason = (
            f"DTW: best match '{best_class}' has mean deviation {best_dist:.1f}° "
            f"> unknown threshold {DTW_UNKNOWN_THRESHOLD}°"
        )
        return True, "unknown", reason

    # Model disagrees significantly with DTW
    if best_class != predicted_class and pred_dist > best_dist * DTW_OVERRIDE_RATIO:
        reason = (
            f"DTW override: model→{predicted_class} ({pred_dist:.1f}°) "
            f"but DTW→{best_class} ({best_dist:.1f}°); ratio={pred_dist/best_dist:.2f}"
        )
        print(f"[classify] {reason}")
        return False, best_class, reason   # not OOD, but corrected

    return False, predicted_class, ""


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("/classify", response_model=ClassifyResponse)
async def classify_movement(request: ClassifyRequest):
    start_time = time.time()

    try:
        if len(request.frames) != 30:
            raise HTTPException(400, f"Exactly 30 frames required, got {len(request.frames)}")

        if request.feature_set == "angles14":
            X = np.array([frame.angles for frame in request.frames], dtype=np.float32)
            feature_key = "Angles14"
        elif request.feature_set == "coords132":
            X = np.array([frame.coords for frame in request.frames], dtype=np.float32)
            feature_key = "Coords132"
        else:
            raise HTTPException(400, "Use 'angles14' or 'coords132'")

        raw_angles = X.copy()                 # (30, 14) in 0-1 scale — kept for OOD
        model      = load_model("Bi-LSTM", feature_key)
        prediction = model.predict(np.expand_dims(X, 0), verbose=0)[0]

        predicted_idx  = int(np.argmax(prediction))
        confidence     = float(np.max(prediction))
        predicted_class = CLASS_NAMES[predicted_idx]
        inference_time = (time.time() - start_time) * 1000

        is_unknown      = False
        rejection_reason = None
        final_class      = predicted_class

        # ── Layer 1: Confidence ───────────────────────────────────────────────
        if confidence < CONFIDENCE_THRESHOLD:
            is_unknown = True
            rejection_reason = (
                f"Low confidence: {confidence:.3f} < {CONFIDENCE_THRESHOLD}"
            )

        # ── Layer 2: Margin ───────────────────────────────────────────────────
        if not is_unknown:
            sorted_probs = sorted(prediction, reverse=True)
            margin = sorted_probs[0] - sorted_probs[1]
            if margin < MARGIN_THRESHOLD:
                is_unknown = True
                rejection_reason = (
                    f"Ambiguous: margin {margin:.3f} < {MARGIN_THRESHOLD}"
                )

        # ── Layer 3: DTW Validation ───────────────────────────────────────────
        if not is_unknown and request.feature_set == "angles14":
            is_ood, corrected_class, dtw_reason = _dtw_ood_check(
                raw_angles, predicted_class
            )
            if is_ood:
                is_unknown       = True
                rejection_reason = dtw_reason
            elif corrected_class != predicted_class:
                # DTW overrides model (not unknown — just a correction)
                final_class      = corrected_class
                rejection_reason = dtw_reason   # informational
                # Update predicted_idx for title formatting
                predicted_idx    = CLASS_NAMES.index(final_class)

        # ── Build response ────────────────────────────────────────────────────
        if is_unknown:
            return ClassifyResponse(
                move             ="Unknown",
                confidence       = round(confidence, 4),
                move_id          ="unknown",
                inference_time_ms= round(inference_time, 2),
                all_probabilities=[round(float(p), 4) for p in prediction],
                is_unknown       = True,
                rejection_reason = rejection_reason,
            )

        display_name = final_class.replace("_", " ").title()
        return ClassifyResponse(
            move             = display_name,
            confidence       = round(confidence, 4),
            move_id          = final_class,
            inference_time_ms= round(inference_time, 2),
            all_probabilities=[round(float(p), 4) for p in prediction],
            is_unknown       = False,
            rejection_reason = rejection_reason,   # may carry the DTW override note
        )

    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")