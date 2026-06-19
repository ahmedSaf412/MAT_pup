# backend/app/routers/classify.py
#
# Three-Model Classification Endpoint (feat-xgb-classifier / presentation branch)
#
# Supported models (pass in request.model):
#   "XGBoost"     — scikit-learn XGBoost pickle, flat (1, 3060) input
#   "Single-BiLSTM" — Keras BiLSTM V1, shape (1, 30, 102) input
#   "Dual-Stem"   — Keras Dual-Stem Fusion BiLSTM, same shape as Single-BiLSTM
#
# OOD guard (all models):
#   Layer 1 — Confidence threshold
#   Layer 2 — Margin check
#   Layer 3 — DTW (Bi-LSTM only; skipped for XGBoost pending threshold re-tuning)
#
# DB integration: saves Detection row if session_id provided + broadcasts to coaches.

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

# ── Class names (same for all three models — same training label order) ────────
CLASS_NAMES_DISPLAY = ["GedanBarai", "Gyakudzuki", "MaeGeri"]
CLASS_NAMES_DB      = ["gedan_barai", "gyaku_zuki", "mae_geri"]

SEQ_LEN  = 30
FEAT_DIM = 102
FLAT_DIM = SEQ_LEN * FEAT_DIM   # 3060

# ── Model file paths ──────────────────────────────────────────────────────────
PRODUCTION_BEST = os.path.join("app", "models", "Results", "Production_Best")

MODEL_PATHS = {
    "xgb":          os.path.join(PRODUCTION_BEST, "model_xgboost.pkl"),
    "single_bilstm": os.path.join(PRODUCTION_BEST, "best_single_bilstmV1.keras"),
    "dual_stem":    os.path.join(PRODUCTION_BEST, "best_dual_stem_fusion.keras"),
}

# ── Model cache ───────────────────────────────────────────────────────────────
_model_cache: dict = {}


def _normalize_model_key(model_str: str) -> str:
    """Map frontend model selector values to internal cache keys."""
    m = (model_str or "").strip().lower().replace("-", "_").replace(" ", "_")
    if m in ("xgboost", "xgb"):
        return "xgb"
    if m in ("dual_stem", "dual_stem_fusion", "dual", "bilstm_dual"):
        return "dual_stem"
    # Default: single bilstm
    return "single_bilstm"


def load_model(model_key: str = "xgb"):
    """Load a model by key and cache it. Thread-safe for single-worker uvicorn."""
    key = _normalize_model_key(model_key)
    if key not in _model_cache:
        path = MODEL_PATHS[key]
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")

        if key == "xgb":
            with open(path, "rb") as f:
                _model_cache[key] = pickle.load(f)
            print(f"[classify] ✅ XGBoost loaded: {path}")
        else:
            import tensorflow as tf
            _model_cache[key] = tf.keras.models.load_model(path)
            print(f"[classify] ✅ Keras model loaded ({key}): {path}")

    return _model_cache[key], key


# ── Request / Response schemas ────────────────────────────────────────────────
class FrameData(BaseModel):
    angles:    Optional[List[float]] = None
    coords:    Optional[List[float]] = None
    landmarks: Optional[List[dict]]  = None

class ClassifyRequest(BaseModel):
    frames:          List[FrameData]
    feature_set:     str = "landmarks"
    model:           str = "XGBoost"    # "XGBoost" | "Single-BiLSTM" | "Dual-Stem"
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
    model_used:        str = ""     # echo back which model ran


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
            raise HTTPException(400, f"Exactly {SEQ_LEN} frames required, got {len(request.frames)}.")

        if not request.frames[0].landmarks:
            raise HTTPException(400, "landmarks are required per frame for all three models.")

        # ── Feature extraction (same for all three models) ─────────────────────
        frame_features = np.array(
            [extract_102_features(f.landmarks) for f in request.frames],
            dtype=np.float32,
        )   # shape (30, 102)

        # ── Load the requested model ──────────────────────────────────────────
        model, model_key = load_model(request.model)

        # ── Inference (input shape differs by model type) ─────────────────────
        if model_key == "xgb":
            # XGBoost: flat (1, 3060)
            X = frame_features.ravel()[np.newaxis, :]   # (1, 3060)
            probs = model.predict_proba(X)[0]           # (3,)
        elif model_key == "dual_stem":
            # Dual-Stem Fusion BiLSTM: takes [upper_features, lower_features]
            X = frame_features[np.newaxis, ...]         # (1, 30, 102)
            upper = X[:, :, :54]                        # first 54 features
            lower = X[:, :, 54:]                        # remaining 48 features
            raw = model.predict([upper, lower], verbose=0)[0] # (3,)
            probs = raw.astype(float)
        else:
            # Single-BiLSTM: (1, 30, 102)
            X = frame_features[np.newaxis, ...]         # (1, 30, 102)
            raw = model.predict(X, verbose=0)[0]        # (3,)
            probs = raw.astype(float)

        idx        = int(np.argmax(probs))
        confidence = float(np.max(probs))
        predicted_display = CLASS_NAMES_DISPLAY[idx]
        predicted_db      = CLASS_NAMES_DB[idx]
        inference_time    = (time.time() - start_time) * 1000
        print(f"[Metrics] {model_key} Inference took {inference_time:.2f} ms")

        # ── OOD Layer 1: Confidence ───────────────────────────────────────────
        is_unknown       = False
        rejection_reason = None

        if confidence < CONFIDENCE_THRESHOLD:
            is_unknown       = True
            rejection_reason = f"Low confidence: {confidence:.3f} < {CONFIDENCE_THRESHOLD}"

        # ── OOD Layer 2: Margin ───────────────────────────────────────────────
        if not is_unknown:
            sorted_probs = sorted(probs, reverse=True)
            margin = sorted_probs[0] - sorted_probs[1]
            if margin < MARGIN_THRESHOLD:
                is_unknown       = True
                rejection_reason = f"Ambiguous: margin {margin:.3f} < {MARGIN_THRESHOLD}"

        # ── OOD Layer 3: DTW (Bi-LSTM models only) ────────────────────────────
        corrections = None
        if not is_unknown and model_key != "xgb":
            try:
                from app.rag.dtw_comparator import score_all_classes
                from app.rag.ood_config import DTW_OVERRIDE_RATIO, DTW_UNKNOWN_THRESHOLD
                
                t_dtw_start = time.time()
                dtw_scores = score_all_classes(predicted_db, frame_features)
                dtw_time_ms = (time.time() - t_dtw_start) * 1000
                print(f"[Metrics] DTW comparison took {dtw_time_ms:.2f} ms")
                
                if dtw_scores:
                    best_class, best_score = min(dtw_scores.items(), key=lambda kv: kv[1])
                    if best_score > DTW_UNKNOWN_THRESHOLD:
                        is_unknown = True
                        rejection_reason = f"DTW distance too high: {best_score:.2f}"
                    corrections = [
                        {"joint": k, "dtw_distance": round(v, 3)}
                        for k, v in dtw_scores.items()
                    ]
            except Exception:
                pass   # DTW is optional — don't crash if references missing

        # ── Persist to DB ─────────────────────────────────────────────────────
        move_id_for_db  = "unknown" if is_unknown else predicted_db
        detection_db_id = None

        if request.session_id:
            det = _save_detection(
                db             = db,
                session_id     = request.session_id,
                move_id        = move_id_for_db,
                confidence     = confidence,
                corrections    = corrections,
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
                    "model_used":        request.model,
                }
                asyncio.create_task(
                    ws_manager.broadcast(request.session_id, event)
                )

        # ── Build response ────────────────────────────────────────────────────
        return ClassifyResponse(
            move              = "Unknown" if is_unknown else predicted_display,
            confidence        = round(confidence, 4),
            move_id           = "unknown" if is_unknown else predicted_db,
            inference_time_ms = round(inference_time, 2),
            all_probabilities = [round(float(p), 4) for p in probs],
            is_unknown        = is_unknown,
            rejection_reason  = rejection_reason,
            detection_id      = detection_db_id,
            model_used        = request.model,
        )

    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Classify error: {str(e)}")