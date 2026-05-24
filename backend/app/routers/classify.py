# backend/app/routers/classify.py
#
# Three-layer OOD guard:
#   Layer 1 — Confidence threshold  (fast, always active)
#   Layer 2 — Margin check          (fast, always active)
#   Layer 3 — DTW validation        (slower, only when exampler_sequences.json exists)
#
# DB Integration:
#   If session_id is passed, saves a Detection row with:
#     - frame_timestamp (Unix timestamp of the window start)
#     - corrections (DTW error list as JSONB)
#   Then broadcasts to any connected coaches via WebSocket.

import time
import asyncio
from typing import List, Optional

import numpy as np
import tensorflow as tf
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.rag.ood_config import (
    CONFIDENCE_THRESHOLD,
    MARGIN_THRESHOLD,
    DTW_OVERRIDE_RATIO,
    DTW_UNKNOWN_THRESHOLD,
)
from app.rag.dtw_comparator import score_all_classes
from app.rag.feature_extractor import extract_102_features
from app.database import get_db
from app.models.session import Detection
from app.models.move    import MoveReference

import os

router = APIRouter(prefix="/api", tags=["classification"])

# ── Constants ─────────────────────────────────────────────────────────────────
# New model (Run_May21_2217/best_single_bilstm.keras) was trained with classes
# in alphabetical order: GedanBarai (0), Gyakudzuki (1), MaeGeri (2).
# We map those to the snake_case API names used throughout this system.
CLASS_NAMES = ["gedan_barai", "gyaku_zuki", "mae_geri"]

# ── Active model path (single source of truth) ─────────────────────────────
ACTIVE_MODEL_PATH = os.path.join(
    "app", "models", "Results", "Run_May21_2217", "best_single_bilstm.keras"
)

# ── Model cache ───────────────────────────────────────────────────────────────
_model_cache = {}

def load_model(model_name: str = None, feature_set: str = None):
    key = "active_model"
    if key not in _model_cache:
        if not os.path.exists(ACTIVE_MODEL_PATH):
            raise FileNotFoundError(f"Active model not found: {ACTIVE_MODEL_PATH}")
        _model_cache[key] = tf.keras.models.load_model(ACTIVE_MODEL_PATH)
        print(f"✅ Loaded active model: {ACTIVE_MODEL_PATH}")
    return _model_cache[key]


# ── Request / Response schemas ────────────────────────────────────────────────
class FrameData(BaseModel):
    angles: Optional[List[float]] = None
    coords: Optional[List[float]] = None
    landmarks: Optional[List[dict]] = None

class ClassifyRequest(BaseModel):
    frames:           List[FrameData]
    feature_set:      str = "angles14"
    model:            str = "Bi-LSTM"
    # ── DB persistence (optional) ──────────────────────────────────────────
    session_id:       Optional[int]   = None   # if provided, saves Detection row
    frame_timestamp:  Optional[float] = None   # Unix ts of the 30-frame window start
    input_mode:       Optional[str]   = "camera"  # 'camera' | 'upload'

class ClassifyResponse(BaseModel):
    move:              str
    confidence:        float
    move_id:           str
    inference_time_ms: float
    all_probabilities: List[float]
    is_unknown:        bool = False
    rejection_reason:  Optional[str] = None
    detection_id:      Optional[int] = None    # DB row ID if saved


# ── OOD DTW check ─────────────────────────────────────────────────────────────
def _dtw_ood_check(raw_angles_01: np.ndarray, predicted_class: str, user_landmark_frames: list = None):
    user_angles_deg = raw_angles_01 * 180.0
    dtw_scores      = score_all_classes(user_angles_deg, user_landmark_frames)
    if not dtw_scores:
        return False, predicted_class, ""

    best_class = min(dtw_scores, key=dtw_scores.get)
    best_dist  = dtw_scores[best_class]
    pred_dist  = dtw_scores.get(predicted_class, best_dist)

    if best_dist > DTW_UNKNOWN_THRESHOLD:
        return True, "unknown", (
            f"DTW: best match '{best_class}' has mean deviation "
            f"{best_dist:.1f}° > threshold {DTW_UNKNOWN_THRESHOLD}°"
        )

    if best_class != predicted_class and pred_dist > best_dist * DTW_OVERRIDE_RATIO:
        reason = (
            f"DTW override: model->{predicted_class} ({pred_dist:.1f}°) "
            f"but DTW->{best_class} ({best_dist:.1f}°)"
        )
        print(f"[classify] {reason}")
        return False, best_class, reason

    return False, predicted_class, ""


# ── DB helpers ────────────────────────────────────────────────────────────────
def _resolve_move_reference_id(move_id: str, db: DBSession) -> Optional[int]:
    """Look up the move_reference PK by move_name; create a stub row if missing."""
    ref = db.query(MoveReference).filter(MoveReference.move_name == move_id).first()
    if ref:
        return ref.id
    # Auto-create a minimal row so FK constraint is satisfied
    display = move_id.replace("_", " ").title()
    new_ref = MoveReference(move_name=move_id, display_name=display)
    db.add(new_ref)
    db.flush()
    return new_ref.id


def _save_detection(
    db:                DBSession,
    session_id:        int,
    move_id:           str,
    confidence:        float,
    corrections:       Optional[list],
    frame_timestamp:   Optional[float],
    input_mode:        str,
) -> Optional[Detection]:
    """Insert a Detection row and return it (or None if session_id absent)."""
    move_ref_id = _resolve_move_reference_id(move_id, db)
    det = Detection(
        session_id        = session_id,
        move_reference_id = move_ref_id,
        confidence        = confidence,
        input_mode        = input_mode,
        corrections       = corrections,  # stored as JSONB
        frame_timestamp   = frame_timestamp or time.time(),
    )
    db.add(det)
    db.commit()
    db.refresh(det)
    return det


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("/classify", response_model=ClassifyResponse)
async def classify_movement(
    request: ClassifyRequest,
    db:      DBSession = Depends(get_db),
):
    start_time = time.time()

    try:
        if len(request.frames) != 30:
            raise HTTPException(400, f"Exactly 30 frames required, got {len(request.frames)}")

        if request.frames[0].landmarks is not None:
            # New frontend sends landmarks -> we can build 102 features
            X = np.array([extract_102_features(f.landmarks) for f in request.frames], dtype=np.float32)
            raw_angles = np.array([f.angles for f in request.frames], dtype=np.float32)
        else:
            # Old frontend, or missing landmarks
            raise HTTPException(400, "Frontend update required: Please refresh your browser. The new active model requires 'landmarks' to extract 102 features, but only received 'angles'.")

        model      = load_model()
        prediction = model.predict(np.expand_dims(X, 0), verbose=0)[0]

        predicted_idx   = int(np.argmax(prediction))
        confidence      = float(np.max(prediction))
        predicted_class = CLASS_NAMES[predicted_idx]
        inference_time  = (time.time() - start_time) * 1000

        is_unknown       = False
        rejection_reason = None
        final_class      = predicted_class

        # ── Layer 1: Confidence ───────────────────────────────────────────────
        if confidence < CONFIDENCE_THRESHOLD:
            is_unknown       = True
            rejection_reason = f"Low confidence: {confidence:.3f} < {CONFIDENCE_THRESHOLD}"

        # ── Layer 2: Margin ───────────────────────────────────────────────────
        if not is_unknown:
            sorted_probs = sorted(prediction, reverse=True)
            margin = sorted_probs[0] - sorted_probs[1]
            if margin < MARGIN_THRESHOLD:
                is_unknown       = True
                rejection_reason = f"Ambiguous: margin {margin:.3f} < {MARGIN_THRESHOLD}"

        # ── Layer 3: DTW Validation ───────────────────────────────────────────
        if not is_unknown and request.feature_set in ["angles14", "landmarks"]:
            user_lms = [f.landmarks for f in request.frames] if request.frames[0].landmarks else None
            is_ood, corrected_class, dtw_reason = _dtw_ood_check(raw_angles, predicted_class, user_lms)
            if is_ood:
                is_unknown       = True
                rejection_reason = dtw_reason
            elif corrected_class != predicted_class:
                final_class      = corrected_class
                rejection_reason = dtw_reason
                predicted_idx    = CLASS_NAMES.index(final_class)

        # ── Build response ────────────────────────────────────────────────────
        move_id_for_db  = "unknown" if is_unknown else final_class
        detection_db_id = None

        # ── Persist to DB if session_id was provided ──────────────────────────
        if request.session_id:
            det = _save_detection(
                db             = db,
                session_id     = request.session_id,
                move_id        = move_id_for_db,
                confidence     = confidence,
                corrections    = None,    # DTW corrections come from /api/rag/feedback
                frame_timestamp = request.frame_timestamp or time.time(),
                input_mode     = request.input_mode or "camera",
            )
            detection_db_id = det.id if det else None

            # ── Broadcast to coaches via WebSocket ────────────────────────────
            from app.routers.live_session import manager as ws_manager
            if ws_manager.session_has_coaches(request.session_id):
                event = {
                    "event":             "detection",
                    "session_id":        request.session_id,
                    "detection_id":      detection_db_id,
                    "move":              move_id_for_db.replace("_", " ").title(),
                    "move_id":           move_id_for_db,
                    "confidence":        round(confidence, 4),
                    "is_unknown":        is_unknown,
                    "rejection_reason":  rejection_reason,
                    "inference_time_ms": round(inference_time, 2),
                    "frame_timestamp":   request.frame_timestamp,
                    "all_probabilities": [round(float(p), 4) for p in prediction],
                }
                asyncio.create_task(
                    ws_manager.broadcast(request.session_id, event)
                )

        if is_unknown:
            return ClassifyResponse(
                move              = "Unknown",
                confidence        = round(confidence, 4),
                move_id           = "unknown",
                inference_time_ms = round(inference_time, 2),
                all_probabilities = [round(float(p), 4) for p in prediction],
                is_unknown        = True,
                rejection_reason  = rejection_reason,
                detection_id      = detection_db_id,
            )

        return ClassifyResponse(
            move              = final_class.replace("_", " ").title(),
            confidence        = round(confidence, 4),
            move_id           = final_class,
            inference_time_ms = round(inference_time, 2),
            all_probabilities = [round(float(p), 4) for p in prediction],
            is_unknown        = False,
            rejection_reason  = rejection_reason,
            detection_id      = detection_db_id,
        )

    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Classify error: {str(e)}")