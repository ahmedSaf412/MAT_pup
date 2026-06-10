# backend/app/routers/classify.py
#
# Single-move classification endpoint — XGBoost edition (feat-xgb-classifier)
#
# Replaces Bi-LSTM / TensorFlow with model_xgboost.pkl.
# Feature contract:
#   - Frontend sends 30 frames of MediaPipe landmarks (33 dicts each).
#   - extract_102_features() converts each frame → 102-d feature vector.
#   - The 30×102 matrix is flattened with np.ravel → shape (1, 3060).
#   - model_xgboost.pkl.predict_proba() returns class probabilities.
#
# OOD guard:
#   Layer 1 — Confidence threshold  (fast)
#   Layer 2 — Margin check          (fast)
#   Layer 3 — DTW validation        (skipped for XGBoost; DTW thresholds were
#               calibrated against LSTM angle outputs, not XGB proba vectors.
#               Re-enable once DTW thresholds are re-tuned for XGB.)
#
# DB integration identical to before:
#   - Saves a Detection row if session_id is provided.
#   - Broadcasts event to coaches via WebSocket.

import os
import pickle
import time
import asyncio
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.rag.ood_config import CONFIDENCE_THRESHOLD, MARGIN_THRESHOLD
from app.rag.feature_extractor import extract_102_features
from app.database import get_db
from app.models.session import Detection
from app.models.move    import MoveReference

router = APIRouter(prefix="/api", tags=["classification"])

# ── Constants ─────────────────────────────────────────────────────────────────
# Must match the label order used when training model_xgboost.pkl.
# From model_metadata.json: ["GedanBarai", "Gyakudzuki", "MaeGeri"]
# The snake_case versions are used for DB storage and RAG routing.
CLASS_NAMES_DISPLAY = ["GedanBarai", "Gyakudzuki", "MaeGeri"]
CLASS_NAMES_DB      = ["gedan_barai", "gyaku_zuki", "mae_geri"]

SEQ_LEN  = 30
FLAT_DIM = SEQ_LEN * 102   # 3060

# ── Model path ────────────────────────────────────────────────────────────────
PRODUCTION_BEST  = os.path.join(
    "app", "models", "Results", "Production_Best"
)
ACTIVE_MODEL_PATH = os.path.join(PRODUCTION_BEST, "model_xgboost.pkl")

# ── Model cache ───────────────────────────────────────────────────────────────
_model_cache: dict = {}


def load_model(*_args, **_kwargs):
    """
    Load model_xgboost.pkl once and cache it.
    Signature kept compatible with old callers (model_name, feature_set ignored).
    """
    key = "xgb"
    if key not in _model_cache:
        if not os.path.exists(ACTIVE_MODEL_PATH):
            raise FileNotFoundError(
                f"XGBoost model not found: {ACTIVE_MODEL_PATH}\n"
                "Run the training notebook and copy model_xgboost.pkl to Production_Best/."
            )
        with open(ACTIVE_MODEL_PATH, "rb") as f:
            _model_cache[key] = pickle.load(f)
        print(f"[classify] OK XGBoost model loaded: {ACTIVE_MODEL_PATH}")
    return _model_cache[key]


# ── Request / Response schemas ────────────────────────────────────────────────
class FrameData(BaseModel):
    angles:    Optional[List[float]] = None
    coords:    Optional[List[float]] = None
    landmarks: Optional[List[dict]]  = None

class ClassifyRequest(BaseModel):
    frames:          List[FrameData]
    feature_set:     str = "landmarks"
    model:           str = "XGBoost"
    # ── DB persistence (optional) ─────────────────────────────────────────
    session_id:      Optional[int]   = None
    frame_timestamp: Optional[float] = None
    input_mode:      Optional[str]   = "camera"

class ClassifyResponse(BaseModel):
    move:              str
    confidence:        float
    move_id:           str
    inference_time_ms: float
    all_probabilities: List[float]
    is_unknown:        bool = False
    rejection_reason:  Optional[str] = None
    detection_id:      Optional[int] = None


# ── DB helpers ────────────────────────────────────────────────────────────────
def _resolve_move_reference_id(move_id: str, db: DBSession) -> Optional[int]:
    ref = db.query(MoveReference).filter(MoveReference.move_name == move_id).first()
    if ref:
        return ref.id
    display = move_id.replace("_", " ").title()
    new_ref = MoveReference(move_name=move_id, display_name=display)
    db.add(new_ref)
    db.flush()
    return new_ref.id


def _save_detection(
    db:              DBSession,
    session_id:      int,
    move_id:         str,
    confidence:      float,
    corrections:     Optional[list],
    frame_timestamp: Optional[float],
    input_mode:      str,
) -> Optional[Detection]:
    move_ref_id = _resolve_move_reference_id(move_id, db)
    det = Detection(
        session_id        = session_id,
        move_reference_id = move_ref_id,
        confidence        = confidence,
        input_mode        = input_mode,
        corrections       = corrections,
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
        if len(request.frames) != SEQ_LEN:
            raise HTTPException(400, f"Exactly {SEQ_LEN} frames required, got {len(request.frames)}")

        # ── Feature extraction ────────────────────────────────────────────────
        if not request.frames[0].landmarks:
            raise HTTPException(
                400,
                "landmarks required per frame. Please refresh your browser — "
                "the active XGBoost model needs raw landmarks to build 102-d features."
            )

        # Build (30, 102) matrix then flatten → (1, 3060)
        frame_features = np.array(
            [extract_102_features(f.landmarks) for f in request.frames],
            dtype=np.float32,
        )   # shape (30, 102)
        X_flat = frame_features.ravel()[np.newaxis, :]   # shape (1, 3060)

        # ── Inference ─────────────────────────────────────────────────────────
        model      = load_model()
        probs      = model.predict_proba(X_flat)[0]       # (3,)
        idx        = int(np.argmax(probs))
        confidence = float(np.max(probs))
        predicted_display = CLASS_NAMES_DISPLAY[idx]
        predicted_db      = CLASS_NAMES_DB[idx]

        inference_time = (time.time() - start_time) * 1000

        # ── Layer 1: Confidence ───────────────────────────────────────────────
        is_unknown       = False
        rejection_reason = None

        if confidence < CONFIDENCE_THRESHOLD:
            is_unknown       = True
            rejection_reason = f"Low confidence: {confidence:.3f} < {CONFIDENCE_THRESHOLD}"

        # ── Layer 2: Margin ───────────────────────────────────────────────────
        if not is_unknown:
            sorted_probs = sorted(probs, reverse=True)
            margin = sorted_probs[0] - sorted_probs[1]
            if margin < MARGIN_THRESHOLD:
                is_unknown       = True
                rejection_reason = f"Ambiguous: margin {margin:.3f} < {MARGIN_THRESHOLD}"

        # Layer 3 (DTW) intentionally skipped on this branch:
        #   DTW thresholds were calibrated against LSTM angle-sequence outputs.
        #   They need to be re-derived for XGBoost's flattened window before
        #   re-enabling. Flag: TODO(feat-xgb-classifier) re-tune DTW.

        # ── Persist to DB ─────────────────────────────────────────────────────
        move_id_for_db  = "unknown" if is_unknown else predicted_db
        detection_db_id = None

        if request.session_id:
            det = _save_detection(
                db             = db,
                session_id     = request.session_id,
                move_id        = move_id_for_db,
                confidence     = confidence,
                corrections    = None,
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
                    "move":              predicted_display,
                    "move_id":           move_id_for_db,
                    "confidence":        round(confidence, 4),
                    "is_unknown":        is_unknown,
                    "rejection_reason":  rejection_reason,
                    "inference_time_ms": round(inference_time, 2),
                    "frame_timestamp":   request.frame_timestamp,
                    "all_probabilities": [round(float(p), 4) for p in probs],
                }
                asyncio.create_task(
                    ws_manager.broadcast(request.session_id, event)
                )

        # ── Build response ────────────────────────────────────────────────────
        if is_unknown:
            return ClassifyResponse(
                move              = "Unknown",
                confidence        = round(confidence, 4),
                move_id           = "unknown",
                inference_time_ms = round(inference_time, 2),
                all_probabilities = [round(float(p), 4) for p in probs],
                is_unknown        = True,
                rejection_reason  = rejection_reason,
                detection_id      = detection_db_id,
            )

        return ClassifyResponse(
            move              = predicted_display,
            confidence        = round(confidence, 4),
            move_id           = predicted_db,
            inference_time_ms = round(inference_time, 2),
            all_probabilities = [round(float(p), 4) for p in probs],
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