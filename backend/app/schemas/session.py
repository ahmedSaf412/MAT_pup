# backend/app/schemas/session.py
# Pydantic v2 schemas for sessions, detections, recordings

from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


# ── Session ───────────────────────────────────────────────────────────────────
class SessionBase(BaseModel):
    trainee_id: int
    coach_id: Optional[int] = None
    session_type: str = "solo"   # 'live' | 'recorded' | 'solo'
    kata_name: Optional[str] = None
    status: str = "active"

class SessionCreate(BaseModel):
    coach_id:     Optional[int] = None
    session_type: Optional[str] = None
    kata_name:    Optional[str] = None
    status:       str = "active"

    model_config = {"from_attributes": True}

class SessionOut(BaseModel):
    id:           int
    trainee_id:   int
    coach_id:     Optional[int] = None
    session_type: Optional[str] = None
    kata_name:    Optional[str] = None
    status:       str
    started_at:   Optional[datetime] = None
    ended_at:     Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Detection ─────────────────────────────────────────────────────────────────
class DetectionCreate(BaseModel):
    session_id:        int
    move_reference_id: Optional[int] = None
    confidence:        float
    input_mode:        str = "camera"
    corrections:       Optional[Any] = None     # list[dict] from DTW
    frame_timestamp:   Optional[float] = None   # Unix timestamp of window start

class DetectionOut(BaseModel):
    id:                int
    session_id:        int
    move_reference_id: Optional[int] = None
    confidence:        float
    input_mode:        Optional[str] = None
    corrections:       Optional[Any] = None
    frame_timestamp:   Optional[float] = None
    detected_at:       Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Recording ─────────────────────────────────────────────────────────────────
class RecordingOut(BaseModel):
    id:               int
    session_id:       Optional[int] = None
    trainee_id:       Optional[int] = None
    file_path:        str
    duration_seconds: Optional[int] = None
    status:           str
    created_at:       Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── WebSocket message sent to coaches ────────────────────────────────────────
class LiveDetectionEvent(BaseModel):
    event:             str = "detection"
    session_id:        int
    move:              str
    move_id:           str
    confidence:        float
    is_unknown:        bool = False
    corrections:       Optional[List[Any]] = None
    frame_timestamp:   Optional[float] = None
    inference_time_ms: Optional[float] = None
