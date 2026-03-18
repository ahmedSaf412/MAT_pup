from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    move_name = Column(String, nullable=False)
    score = Column(Integer, default=0)
    feedback = Column(String, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)