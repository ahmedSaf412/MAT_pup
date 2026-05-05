# backend/app/models/user.py
# SQLAlchemy models matching the PostgreSQL schema in query.txt
# Tables: users, trainee, coach

from sqlalchemy import (
    Column, Integer, String, Boolean, Text,
    DateTime, ForeignKey, func,
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    email            = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password  = Column(Text, nullable=False)
    role             = Column(String(20), nullable=False, default="trainee")   # 'trainee' | 'coach'
    phone            = Column(String(20), nullable=True)
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime, server_default=func.now())

    # relationships
    trainee_profile  = relationship("Trainee", back_populates="user", uselist=False)
    coach_profile    = relationship("Coach",   back_populates="user", uselist=False)
    rag_queries      = relationship("RagQuery", back_populates="user")


class Trainee(Base):
    __tablename__ = "trainee"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    coach_id   = Column(Integer, ForeignKey("coach.id",  ondelete="SET NULL"), nullable=True)
    age        = Column(Integer, nullable=True)
    belt_level = Column(String(50), nullable=True, default="white")
    joined_at  = Column(DateTime, server_default=func.now())

    user     = relationship("User",  back_populates="trainee_profile")
    coach    = relationship("Coach", back_populates="trainees", foreign_keys=[coach_id])
    sessions = relationship("Session",   back_populates="trainee")
    recordings = relationship("Recording", back_populates="trainee")


class Coach(Base):
    __tablename__ = "coach"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    specialization   = Column(Text, nullable=True)
    years_experience = Column(Integer, nullable=True)
    bio              = Column(Text, nullable=True)

    user     = relationship("User",  back_populates="coach_profile")
    trainees = relationship("Trainee", back_populates="coach", foreign_keys="Trainee.coach_id")
    sessions = relationship("Session", back_populates="coach")
    feedbacks = relationship("Feedback", back_populates="coach")