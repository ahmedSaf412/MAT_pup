from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User, Trainee, Coach
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/trainee", tags=["trainee"])

class CoachResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    specialization: str | None
    bio: str | None
    email: str
    
    model_config = {"from_attributes": True}

@router.get("/coach", response_model=CoachResponse | None)
def get_my_coach(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "trainee":
        raise HTTPException(403, "Not a trainee")
        
    trainee = current_user.trainee_profile
    if not trainee:
        raise HTTPException(404, "Trainee profile not found")
        
    coach = trainee.coach
    if not coach:
        return None
        
    return CoachResponse(
        id=coach.id,
        user_id=coach.user_id,
        full_name=coach.user.full_name or "Unknown",
        specialization=coach.specialization,
        bio=coach.bio,
        email=coach.user.email
    )

@router.get("/coaches", response_model=List[CoachResponse])
def list_available_coaches(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    coaches = db.query(Coach).all()
    result = []
    for c in coaches:
        result.append(CoachResponse(
            id=c.id,
            user_id=c.user_id,
            full_name=c.user.full_name or "Unknown",
            specialization=c.specialization,
            bio=c.bio,
            email=c.user.email
        ))
    return result

@router.post("/coaches/{coach_id}/request")
def request_coach(coach_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "trainee":
        raise HTTPException(403, "Not a trainee")
        
    trainee = current_user.trainee_profile
    if not trainee:
        raise HTTPException(404, "Trainee profile not found")
        
    target_coach = db.query(Coach).filter(Coach.id == coach_id).first()
    if not target_coach:
        raise HTTPException(404, "Coach not found")
        
    trainee.requested_coach_id = target_coach.id
    db.commit()
    return {"message": "Coach requested successfully"}

from sqlalchemy import desc
from app.models.session import Session as TrainingSession

@router.get('/stats')
def get_my_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != 'trainee':
        raise HTTPException(403, 'Not a trainee')
        
    trainee = current_user.trainee_profile
    if not trainee:
        raise HTTPException(404, 'Trainee profile not found')
        
    sessions = db.query(TrainingSession).filter(TrainingSession.trainee_id == trainee.id).order_by(desc(TrainingSession.started_at).nulls_last()).limit(10).all()
    
    session_data = []
    
    for s in sessions:
        duration = 0
        if s.ended_at and s.started_at:
            duration = int((s.ended_at - s.started_at).total_seconds() / 60)
            
        score = 0
        moves = []
        for d in s.detections:
            if d.move_reference:
                moves.append(d.move_reference.display_name or d.move_reference.move_name)
            if d.confidence:
                score += d.confidence
                    
        avg_score = int((score / len(s.detections)) * 100) if s.detections else 0
        session_data.append({
            'id': s.id,
            'date': s.started_at.strftime('%Y-%m-%d') if s.started_at else 'Unknown',
            'duration': f'{max(1, duration)}m',
            'score': avg_score,
            'moves': list(set(moves))
        })
        
    return {
        'sessions': session_data
    }
