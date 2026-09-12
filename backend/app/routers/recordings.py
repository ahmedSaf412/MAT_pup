# backend/app/routers/recordings.py
# Upload a video → save to recording table → process with MediaPipe → classify all 30-frame windows
#
# POST /api/recordings/upload  — multipart form upload
# GET  /api/recordings/{id}    — status check
# POST /api/recordings/{id}/feedback  — coach leaves text feedback

import os
import time
import shutil
import asyncio
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File,
    Form, BackgroundTasks,
)
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.user    import User, Trainee
from app.models.session import Session as DBSession_, Detection, Recording
from app.models.rag     import Feedback
from app.schemas.session import RecordingOut
from app.services.auth  import get_current_user

router = APIRouter(prefix="/api/recordings", tags=["recordings"])

# ── Upload directory ──────────────────────────────────────────────────────────
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "recordings"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_SIZE = 30   # frames per Bi-LSTM window


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_trainee(user: User, db: DBSession) -> Trainee:
    t = db.query(Trainee).filter(Trainee.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Trainee profile not found.")
    return t


# ── Background processing ─────────────────────────────────────────────────────
def _process_video_background(recording_id: int, file_path: str, session_id: int):
    """
    Run in a background thread:
    1. Extract poses with MediaPipe
    2. Classify every non-overlapping 30-frame window
    3. Save each Detection to the DB
    4. Mark recording as 'done'
    """
    from sqlalchemy.orm import sessionmaker
    from app.database import engine
    from app.models.session import Detection
    from app.models.move import MoveReference
    from app.routers.classify import load_model, _dtw_ood_check, _save_detection, CLASS_NAMES
    from app.rag.angle_calculator import compute_14_angles, ANGLE_NAMES
    from app.rag.feature_extractor import extract_102_features
    import math

    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        import cv2, mediapipe as mp
        pose    = mp.solutions.pose.Pose(
            static_image_mode=False, model_complexity=1,
            smooth_landmarks=True, min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        cap     = cv2.VideoCapture(file_path)
        fps     = cap.get(cv2.CAP_PROP_FPS) or 30.0
        buffer  = []   # list of 14-float angle arrays

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.pose_landmarks:
                lm_list = [
                    {"x": lm.x, "y": lm.y, "z": lm.z, "visibility": lm.visibility}
                    for lm in results.pose_landmarks.landmark
                ]
                angles_dict = compute_14_angles(lm_list)
                # Normalise to 0-1 to match model training scale
                norm_angles = [
                    max(0.0, min(1.0, angles_dict[n] / 180.0))
                    for n in ANGLE_NAMES
                ]
                buffer.append({
                    "norm": norm_angles,
                    "raw_deg": [angles_dict[n] for n in ANGLE_NAMES],
                    "features_102": extract_102_features(lm_list),
                    "timestamp": frame_idx / fps,
                })
            frame_idx += 1

        cap.release()
        pose.close()

        # Load model once
        model = load_model("Bi-LSTM", "Angles14")

        detected_moves = []

        # Slide a window of 30 frames (non-overlapping)
        step = WINDOW_SIZE
        for start in range(0, len(buffer) - WINDOW_SIZE + 1, step):
            window    = buffer[start: start + WINDOW_SIZE]
            X         = np.array([w["features_102"] for w in window], dtype=np.float32)
            ts_start  = window[0]["timestamp"]  # Unix offset in video seconds

            prediction    = model.predict(np.expand_dims(X, 0), verbose=0)[0]
            predicted_idx = int(np.argmax(prediction))
            confidence    = float(np.max(prediction))
            move_id       = CLASS_NAMES[predicted_idx]

            # OOD check
            from app.rag.ood_config import CONFIDENCE_THRESHOLD, MARGIN_THRESHOLD
            is_ood = confidence < CONFIDENCE_THRESHOLD
            if not is_ood:
                probs  = sorted(prediction, reverse=True)
                is_ood = (probs[0] - probs[1]) < MARGIN_THRESHOLD
            if not is_ood:
                raw_deg_seq = np.array(
                    [w["raw_deg"] for w in window], dtype=np.float32
                )
                from app.rag.dtw_comparator import score_all_classes
                from app.rag.ood_config import DTW_OVERRIDE_RATIO, DTW_UNKNOWN_THRESHOLD
                scores = score_all_classes(raw_deg_seq)
                if scores:
                    best = min(scores, key=scores.get)
                    if scores[best] > DTW_UNKNOWN_THRESHOLD:
                        is_ood = True; move_id = "unknown"
                    elif best != move_id and scores.get(move_id, 0) > scores[best] * DTW_OVERRIDE_RATIO:
                        move_id = best   # DTW override

            _save_detection(
                db             = db,
                session_id     = session_id,
                move_id        = move_id if not is_ood else "unknown",
                confidence     = confidence,
                corrections    = None,
                frame_timestamp = ts_start,
                input_mode     = "upload",
            )
            if not is_ood and move_id != "unknown":
                detected_moves.append(move_id)

        # Mark recording done and update duration
        rec = db.query(Recording).filter(Recording.id == recording_id).first()
        if rec:
            rec.status           = "done"
            rec.duration_seconds = int(frame_idx / fps) if fps else 0

        # Aggregate unique consecutive moves to form Kata Name
        sess = db.query(DBSession_).filter(DBSession_.id == session_id).first()
        if sess and detected_moves:
            consecutive_moves = []
            for m in detected_moves:
                if not consecutive_moves or consecutive_moves[-1] != m:
                    consecutive_moves.append(m)
            acronyms = {"mae_geri": "MG", "gyaku_zuki": "GDZ", "gedan_barai": "GB"}
            kata_str = "-".join([acronyms.get(m, m.upper()) for m in consecutive_moves])
            sess.kata_name = kata_str

        db.commit()

    except Exception as e:
        print(f"[recordings] Processing error for recording {recording_id}: {e}")
        rec = db.query(Recording).filter(Recording.id == recording_id).first()
        if rec:
            rec.status = "error"
            db.commit()
    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/upload", response_model=RecordingOut, status_code=201)
async def upload_recording(
    background_tasks: BackgroundTasks,
    file:         UploadFile = File(..., description="MP4/WebM video file"),
    session_id:   Optional[int] = Form(None, description="Existing session ID to attach to"),
    current_user: User    = Depends(get_current_user),
    db:           DBSession = Depends(get_db),
):
    """
    Upload a training video.
    - Saves file to disk
    - Creates a Recording row (status='uploaded')
    - Runs 30-frame classification in the background
    - Creates Detection rows for each window
    """
    # Validate file type
    if not file.content_type.startswith("video/"):
        raise HTTPException(415, "Only video files are accepted")

    # Resolve or create a session
    if session_id is None:
        # Auto-create a solo upload session
        trainee = _get_trainee(current_user, db)
        sess = DBSession_(
            trainee_id   = trainee.id,
            session_type = "recorded",
            status       = "active",
        )
        db.add(sess)
        db.flush()
        session_id = sess.id
    else:
        # Check if the session exists and was incorrectly marked as 'live'
        from app.models.session import Session as DBSession_
        sess = db.query(DBSession_).filter(DBSession_.id == session_id).first()
        if sess and sess.session_type == "live":
            sess.session_type = "recorded"
            db.commit()
    
    # Save file
    safe_name = f"rec_{session_id}_{int(time.time())}_{file.filename}"
    dest_path  = str(UPLOAD_DIR / safe_name)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Get trainee id
    trainee_id = None
    if current_user.role in ("trainee", "trainer"):
        t = db.query(Trainee).filter(Trainee.user_id == current_user.id).first()
        if t:
            trainee_id = t.id

    rec = Recording(
        session_id = session_id,
        trainee_id = trainee_id,
        file_path  = dest_path,
        status     = "processing",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # Kick off background processing
    background_tasks.add_task(
        _process_video_background, rec.id, dest_path, session_id
    )

    return rec


@router.get("/{recording_id}", response_model=RecordingOut)
def get_recording(
    recording_id: int,
    current_user: User     = Depends(get_current_user),
    db:           DBSession = Depends(get_db),
):
    rec = db.query(Recording).filter(Recording.id == recording_id).first()
    if not rec:
        raise HTTPException(404, "Recording not found")
    return rec


@router.post("/{recording_id}/feedback")
def add_feedback(
    recording_id: int,
    message:      str     = Form(...),
    current_user: User     = Depends(get_current_user),
    db:           DBSession = Depends(get_db),
):
    """Coach leaves a text comment on a recording."""
    if current_user.role != "coach":
        raise HTTPException(403, "Only coaches can leave feedback")

    coach = db.query(__import__("app.models.user", fromlist=["Coach"]).Coach)\
              .filter_by(user_id=current_user.id).first()
    if not coach:
        raise HTTPException(404, "Coach profile not found")

    fb = Feedback(recording_id=recording_id, coach_id=coach.id, message=message)
    db.add(fb)
    db.commit()
    return {"status": "ok", "message": "Feedback saved"}
