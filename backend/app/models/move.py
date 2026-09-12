# backend/app/models/move.py
# Table: move_reference

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class MoveReference(Base):
    __tablename__ = "move_reference"

    id               = Column(Integer, primary_key=True, index=True)
    move_name        = Column(String(100), unique=True, index=True)  # e.g. 'mae_geri'
    display_name     = Column(String(100), nullable=True)            # e.g. 'Front Kick'
    description      = Column(Text, nullable=True)
    category         = Column(String(50), nullable=True)             # e.g. 'kick'
    difficulty_level = Column(String(50), nullable=True)             # e.g. 'beginner'
    tips             = Column(JSONB, nullable=True)  # list of coaching tip strings
    key_joints       = Column(JSONB, nullable=True)  # list of joint names
    ideal_angles     = Column(JSONB, nullable=True)  # {joint: degrees}
    angle_tolerances = Column(JSONB, nullable=True)  # {joint: tolerance_degrees}

    detections = relationship("Detection", back_populates="move_reference")