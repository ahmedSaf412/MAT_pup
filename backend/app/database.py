# backend/app/database.py
# PostgreSQL via psycopg2 + pgvector extension registration

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

# ── Engine ────────────────────────────────────────────────────────────────────
# No check_same_thread needed for PostgreSQL (that's SQLite-specific)
_connect_args = {}
if "sqlite" in DATABASE_URL:
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,     # reconnect on stale connections
    pool_size=10,
    max_overflow=20,
)

# ── Register pgvector extension ───────────────────────────────────────────────
if "postgresql" in DATABASE_URL:
    try:
        from pgvector.sqlalchemy import Vector  # noqa: F401
    except ImportError:
        pass  # gracefully skip if package not installed yet

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and guarantees close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Import all models so Base.metadata knows about them, then create tables."""
    from app.models import user, session, move, rag  # noqa: F401
    # create_all is safe on an existing DB — it skips tables that already exist.
    Base.metadata.create_all(bind=engine)
