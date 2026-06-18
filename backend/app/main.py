# backend/app/main.py

import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import classify, video, rag_feedback, skeleton
from app.routers import auth, sessions, recordings, live_session
from app.routers import kata

app = FastAPI(
    title="Martial Arts AI Trainer",
    description="AI-powered karate movement classification and correction API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"],
)


@app.on_event("startup")
async def startup_event():
    # 1. Create DB tables synchronously (fast — just schema check)
    init_db()

    # 2. Pre-warm caches in the background so the server is responsive immediately
    #    Model loading (~5 s) and reference data loading run concurrently
    asyncio.create_task(_preload_heavy_resources())


async def _preload_heavy_resources():
    """
    Background pre-warm task.  All four heavy loads run CONCURRENTLY via
    asyncio.gather so the slowest one (RAG HuggingFace download) does not
    delay the Kata Dual-Stem model from becoming available.
    """
    loop = asyncio.get_event_loop()

    async def _run(label: str, fn):
        try:
            await loop.run_in_executor(None, fn)
            print(f"[startup] [OK] {label}")
        except Exception as e:
            print(f"[startup] [WARN] {label} skipped: {e}")

    await asyncio.gather(
        _run("Bi-LSTM model pre-loaded",              _load_model_cache),
        _run("MADS P3 reference sequences loaded",    _load_dtw_caches),
        _run("RAG Model loaded into memory!",         _load_rag_model),
        _run("Kata model (Dual-Stem) loaded!",        _load_kata_models),
    )



def _load_model_cache():
    """Pre-warm all three classifiers at startup so switching is instant."""
    from app.routers.classify import load_model
    for key in ("xgb", "single_bilstm", "dual_stem"):
        try:
            load_model(key)
        except Exception as e:
            print(f"[startup] [WARN] Could not preload model '{key}': {e}")



def _load_dtw_caches():
    """Trigger DTW reference data into memory."""
    from app.rag.dtw_comparator import get_reference_sequences, _load_thresholds
    get_reference_sequences()
    _load_thresholds()


def _load_rag_model():
    """Trigger the RAG embedding model lazy load."""
    try:
        from app.rag.retriever import get_collection
        get_collection()
    except Exception:
        pass


def _load_kata_models():
    """Pre-load Production_Best Keras models for Kata Mode."""
    from app.routers.kata import load_kata_models
    load_kata_models()


# ── Core AI routers ────────────────────────────────────────────────────────────
app.include_router(classify.router)
app.include_router(video.router)
app.include_router(rag_feedback.router)
app.include_router(skeleton.router)

# ── Auth + User management ─────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(auth.users_router)   # /api/users/me alias

# ── Coach + Trainee management ────────────────────────────────────────────────
from app.routers import coach, trainee
app.include_router(coach.router)
app.include_router(trainee.router)

# ── Session + Detection + Recording ───────────────────────────────────────────
app.include_router(sessions.router)
app.include_router(recordings.router)

# ── WebSocket (coach live session) ─────────────────────────────────────────────
app.include_router(live_session.router)

# ── Kata (real-time full kata WebSocket) ──────────────────────────────────────────
app.include_router(kata.router)

# ── Health endpoints ───────────────────────────────────────────────────────────

# Serve uploaded video recordings so the coach player can stream them
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.get("/")
async def root():
    return {"message": "Martial Arts AI Trainer API is running!", "version": "2.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}