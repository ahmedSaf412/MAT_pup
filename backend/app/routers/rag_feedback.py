from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.rag.pipeline import process_form_feedback, process_chat_message

router = APIRouter(prefix="/api/rag", tags=["rag"])


# ── DTW Feedback endpoint ─────────────────────────────────────────────────────

class LandmarkSchema(BaseModel):
    x: float
    y: float
    z: float
    visibility: Optional[float] = 1.0

class DTWFeedbackRequest(BaseModel):
    move_id: str
    # Full rep as a list of frames; each frame is 33 MediaPipe landmarks.
    # Shape: [num_frames][33]  (typically 30 frames)
    frames: List[List[LandmarkSchema]]

@router.post("/feedback")
async def get_feedback(req: DTWFeedbackRequest):
    if len(req.frames) < 5:
        raise HTTPException(400, "Need at least 5 frames for DTW comparison")

    # Convert nested Pydantic models → plain dicts for the pipeline
    frames_as_dicts = [
        [lm.model_dump() for lm in frame]
        for frame in req.frames
    ]

    try:
        result = await process_form_feedback(req.move_id, frames_as_dicts)
        return result
    except Exception as e:
        raise HTTPException(500, f"DTW feedback error: {str(e)}")


# ── Chat endpoint ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    move_id: Optional[str] = None
    current_errors: Optional[List[Dict[str, Any]]] = None

@router.post("/chat")
async def chat(req: ChatRequest):
    try:
        result = await process_chat_message(req.message, req.move_id)
        return result
    except Exception as e:
        raise HTTPException(500, f"Chat error: {str(e)}")
