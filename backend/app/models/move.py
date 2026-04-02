from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class Move(Base):
    __tablename__ = "moves"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    difficulty = Column(String, default="beginner")  # beginner/intermediate/advanced