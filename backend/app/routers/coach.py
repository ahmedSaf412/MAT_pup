from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User, Trainee, Coach
from app.services.auth import get_current_user
from app.schemas.user import UserOut

router = APIRouter(prefix="/api/coach", tags=["coach"])

class TraineeResponse(BaseModel):
    id: int
    user_id: int
    email: str
    full_name: str
    belt_level: str
    age: int | None
    
    model_config = {"from_attributes": True}

@router.get("/trainees", response_model=List[TraineeResponse])
def get_coach_trainees(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "coach":
        raise HTTPException(403, "Not a coach")
        
    coach = current_user.coach_profile
    if not coach:
        raise HTTPException(404, "Coach profile not found")
        
    result = []
    for trainee in coach.trainees:
        result.append(TraineeResponse(
            id=trainee.id,
            user_id=trainee.user_id,
            email=trainee.user.email,
            full_name=trainee.user.full_name or "Unknown",
            belt_level=trainee.belt_level or "white",
            age=trainee.age
        ))
    return result

@router.get("/requests", response_model=List[TraineeResponse])
def get_coach_requests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "coach":
        raise HTTPException(403, "Not a coach")
        
    coach = current_user.coach_profile
    if not coach:
        raise HTTPException(404, "Coach profile not found")
        
    result = []
    for trainee in coach.pending_trainees:
        result.append(TraineeResponse(
            id=trainee.id,
            user_id=trainee.user_id,
            email=trainee.user.email,
            full_name=trainee.user.full_name or "Unknown",
            belt_level=trainee.belt_level or "white",
            age=trainee.age
        ))
    return result

@router.post("/requests/{trainee_id}/accept")
def accept_trainee_request(trainee_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "coach":
        raise HTTPException(403, "Not a coach")
        
    coach = current_user.coach_profile
    if not coach:
        raise HTTPException(404, "Coach profile not found")
        
    trainee = db.query(Trainee).filter(Trainee.id == trainee_id, Trainee.requested_coach_id == coach.id).first()
    if not trainee:
        raise HTTPException(404, "Pending request not found")
        
    trainee.coach_id = coach.id
    trainee.requested_coach_id = None
    db.commit()
    return {"message": "Trainee accepted successfully"}

from sqlalchemy import desc
from app.models.session import Session as TrainingSession

@router.get("/trainees/{trainee_id}")
def get_trainee_details(trainee_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "coach":
        raise HTTPException(403, "Not a coach")
        
    coach = current_user.coach_profile
    trainee = db.query(Trainee).filter(Trainee.id == trainee_id, Trainee.coach_id == coach.id).first()
    if not trainee:
        raise HTTPException(404, "Trainee not found or not assigned to you")
        
    sessions = db.query(TrainingSession).filter(TrainingSession.trainee_id == trainee.id).order_by(desc(TrainingSession.started_at)).limit(10).all()
    
    session_data = []
    corrections_map = {}
    
    for s in sessions:
        duration = 0
        if s.ended_at and s.started_at:
            duration = int((s.ended_at - s.started_at).total_seconds() / 60)
            
        # Get detections for this session
        score = 0
        moves = []
        for d in s.detections:
            if d.move_reference:
                moves.append(d.move_reference.display_name or d.move_reference.move_name)
            if d.confidence:
                score += d.confidence
            if d.corrections:
                for c in d.corrections:
                    j = c.get('joint', 'unknown')
                    corrections_map[j] = corrections_map.get(j, 0) + 1
                    
        avg_score = int((score / len(s.detections)) * 100) if s.detections else 0
        session_data.append({
            "date": s.started_at.strftime('%Y-%m-%d') if s.started_at else 'Unknown',
            "duration": f"{max(1, duration)}m",
            "score": avg_score,
            "moves": list(set(moves))
        })
        
    # Format corrections
    sorted_corrections = sorted(corrections_map.items(), key=lambda x: x[1], reverse=True)[:4]
    colors = ['var(--accent-red)', 'var(--accent-orange)', 'var(--accent-yellow)', 'var(--accent-green)']
    corrections_list = []
    total_c = sum(corrections_map.values()) or 1
    
    for i, (joint, count) in enumerate(sorted_corrections):
        corrections_list.append({
            "joint": joint,
            "frequency": int((count / total_c) * 100),
            "color": colors[i % len(colors)]
        })
        
    return {
        "name": trainee.user.full_name or "Unknown",
        "email": trainee.user.email,
        "belt": trainee.belt_level or "white",
        "sessions": session_data,
        "corrections": corrections_list,
        "progressScores": [s["score"] for s in reversed(session_data)] if session_data else [0],
        "progressLabels": [f"S{i+1}" for i in range(len(session_data))] if session_data else ["None"],
        "moveAccuracy": {
            "labels": ["Mae Geri", "Gedan Barai", "Gyaku Zuki"],
            "scores": [80, 85, 90] # Mocked for now until per-move accuracy is tracked
        }
    }
