# backend/app/routers/sessions.py
# Session management: start, end, list detections

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.user    import User, Trainee
from app.models.session import Session as DBSession, Detection
from app.schemas.session import SessionCreate, SessionOut, DetectionOut
from app.services.auth  import get_current_user, require_trainee

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _get_trainee(user: User, db: Session) -> Trainee:
    trainee = db.query(Trainee).filter(Trainee.user_id == user.id).first()
    if not trainee:
        raise HTTPException(404, "Trainee profile not found. Complete registration first.")
    return trainee


@router.post("/start", response_model=SessionOut, status_code=201)
def start_session(
    body:         SessionCreate = SessionCreate(),
    current_user: User          = Depends(require_trainee),
    db:           Session       = Depends(get_db),
):
    """Start a new training session and return its ID."""
    trainee = _get_trainee(current_user, db)
    sess    = DBSession(
        trainee_id   = trainee.id,
        session_type = body.session_type,
        status       = "active",
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


@router.post("/{session_id}/end", response_model=SessionOut)
def end_session(
    session_id:   int,
    current_user: User    = Depends(require_trainee),
    db:           Session = Depends(get_db),
):
    """Mark a session as ended."""
    sess = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not sess:
        raise HTTPException(404, f"Session {session_id} not found")

    sess.status   = "ended"
    sess.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(sess)
    return sess


@router.get("/{session_id}/detections", response_model=list[DetectionOut])
def get_session_detections(
    session_id:   int,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Fetch all detection records for a session (used by coach dashboard)."""
    return (
        db.query(Detection)
          .filter(Detection.session_id == session_id)
          .order_by(Detection.detected_at)
          .all()
    )


@router.get("/", response_model=list[SessionOut])
def list_my_sessions(
    current_user: User    = Depends(require_trainee),
    db:           Session = Depends(get_db),
):
    """List all sessions for the authenticated trainee."""
    trainee = _get_trainee(current_user, db)
    return (
        db.query(DBSession)
          .filter(DBSession.trainee_id == trainee.id)
          .order_by(DBSession.started_at.desc())
          .limit(50)
          .all()
    )
