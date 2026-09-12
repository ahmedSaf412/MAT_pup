# backend/app/models/rag.py
# Tables: rag_document (with pgvector), rag_query, feedback

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base

# ── Try to import pgvector Vector type ───────────────────────────────────────
try:
    from pgvector.sqlalchemy import Vector
    _VECTOR_TYPE = Vector(768)
except ImportError:
    # Fallback: store as text (will not support similarity search)
    from sqlalchemy import Text as _TextType
    _VECTOR_TYPE = _TextType()
    print("⚠️  pgvector not installed — rag_document.embedding stored as TEXT. "
          "Run: pip install pgvector")


class RagDocument(Base):
    """Coaching knowledge base. Embedding indexed for cosine similarity search."""
    __tablename__ = "rag_document"

    id         = Column(Integer, primary_key=True, index=True)
    title      = Column(Text, nullable=True)
    content    = Column(Text, nullable=False)
    category   = Column(String(100), nullable=True)   # e.g. 'mae_geri'
    embedding  = Column(_VECTOR_TYPE, nullable=True)  # vector(768) via pgvector
    indexed_at = Column(DateTime, server_default=func.now())


class RagQuery(Base):
    """Log of user chatbot Q&A — for future fine-tuning / analytics."""
    __tablename__ = "rag_query"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=True)
    question       = Column(Text, nullable=True)
    answer         = Column(Text, nullable=True)
    source_doc_ids = Column(JSONB, nullable=True)  # [1, 3, 7] — which RagDocument rows were used
    asked_at       = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="rag_queries")


class Feedback(Base):
    """Coach feedback left on a recording."""
    __tablename__ = "feedback"

    id           = Column(Integer, primary_key=True, index=True)
    recording_id = Column(Integer, ForeignKey("recording.id", ondelete="CASCADE"), nullable=True)
    coach_id     = Column(Integer, ForeignKey("coach.id"),    nullable=True)
    message      = Column(Text, nullable=True)
    created_at   = Column(DateTime, server_default=func.now())

    recording = relationship("Recording", back_populates="feedbacks")
    coach     = relationship("Coach",     back_populates="feedbacks")
