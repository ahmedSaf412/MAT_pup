# backend/app/models/session.py
# Tables: session, detection, recording

from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    ForeignKey, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Session(Base):
    __tablename__ = "session"

    id           = Column(Integer, primary_key=True, index=True)
    trainee_id   = Column(Integer, ForeignKey("trainee.id", ondelete="CASCADE"))
    coach_id     = Column(Integer, ForeignKey("coach.id",   ondelete="SET NULL"), nullable=True)
    session_type = Column(String(20), nullable=True)   # 'live' | 'recorded' | 'solo'
    kata_name    = Column(String(100), nullable=True)  # Auto-generated sequence of moves or assigned name
    status       = Column(String(20), default="active") # 'active' | 'ended'
    started_at   = Column(DateTime, server_default=func.now())
    ended_at     = Column(DateTime, nullable=True)

    trainee    = relationship("Trainee",   back_populates="sessions")
    coach      = relationship("Coach",     back_populates="sessions")
    detections = relationship("Detection", back_populates="session", cascade="all, delete")
    recordings = relationship("Recording", back_populates="session", cascade="all, delete")


class Detection(Base):
    """One detection = one 30-frame classified rep."""
    __tablename__ = "detection"

    id               = Column(Integer, primary_key=True, index=True)
    session_id       = Column(Integer, ForeignKey("session.id",        ondelete="CASCADE"))
    move_reference_id = Column(Integer, ForeignKey("move_reference.id"), nullable=True)
    confidence       = Column(Float,   nullable=True)
    input_mode       = Column(String(50), default="camera")  # 'camera' | 'upload'
    corrections      = Column(JSONB, nullable=True)   # DTW error list stored as JSON
    frame_timestamp  = Column(Float, nullable=True)   # Unix ts of window start
    detected_at      = Column(DateTime, server_default=func.now())

    session        = relationship("Session",       back_populates="detections")
    move_reference = relationship("MoveReference", back_populates="detections")


class Recording(Base):
    __tablename__ = "recording"

    id               = Column(Integer, primary_key=True, index=True)
    session_id       = Column(Integer, ForeignKey("session.id",   ondelete="CASCADE"), nullable=True)
    trainee_id       = Column(Integer, ForeignKey("trainee.id"), nullable=True)
    file_path        = Column(String,  nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    status           = Column(String(50), default="uploaded")  # 'uploaded' | 'processing' | 'done'
    created_at       = Column(DateTime, server_default=func.now())

    session   = relationship("Session",  back_populates="recordings")
    trainee   = relationship("Trainee",  back_populates="recordings")
    feedbacks = relationship("Feedback", back_populates="recording", cascade="all, delete")