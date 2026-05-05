# backend/app/schemas/user.py
# Pydantic v2 schemas for auth + user profile

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


# ── Registration / Login ──────────────────────────────────────────────────────
class UserRegister(BaseModel):
    email:      EmailStr
    password:   str
    full_name:  Optional[str] = None
    role:       str = "trainee"          # 'trainee' | 'coach'
    belt_level: Optional[str] = "white"  # for trainees
    phone:      Optional[str] = None

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ("trainee", "trainer", "coach"):
            raise ValueError("role must be 'trainee' or 'coach'")
        return "trainee" if v == "trainer" else v   # normalise legacy 'trainer'


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


# ── Responses ─────────────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"


class UserOut(BaseModel):
    id:         int
    email:      str
    role:       str
    is_active:  bool
    created_at: Optional[datetime] = None
    full_name:  Optional[str] = None   # from trainee/coach profile if available
    belt_level: Optional[str] = None   # trainee only

    model_config = {"from_attributes": True}


# ── Trainee / Coach profile ───────────────────────────────────────────────────
class TraineeOut(BaseModel):
    id:         int
    user_id:    int
    belt_level: Optional[str] = None
    joined_at:  Optional[datetime] = None

    model_config = {"from_attributes": True}


class CoachOut(BaseModel):
    id:               int
    user_id:          int
    specialization:   Optional[str] = None
    years_experience: Optional[int] = None
    bio:              Optional[str] = None

    model_config = {"from_attributes": True}
