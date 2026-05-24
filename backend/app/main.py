# backend/app/main.py

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    Background pre-warm task.  Errors here are logged but never crash the server.
    The classify endpoint's model is already loaded lazily by classify.py on first
    request, but we trigger it early so the first real request feels instant.
    """
    loop = asyncio.get_event_loop()
    try:
        # Pre-load the Keras Bi-LSTM model (runs in thread pool to avoid blocking)
        await loop.run_in_executor(None, _load_model_cache)
        print("[startup] [OK] Bi-LSTM model pre-loaded")
    except Exception as e:
        print(f"[startup] [WARN] Model pre-load skipped: {e}")

    try:
        # Pre-warm MADS reference sequences + thresholds into memory
        await loop.run_in_executor(None, _load_dtw_caches)
        print("[startup] [OK] MADS P3 reference sequences loaded")
    except Exception as e:
        print(f"[startup] [WARN] DTW cache pre-load skipped: {e}")

    try:
        # Pre-load RAG Hugging Face model
        await loop.run_in_executor(None, _load_rag_model)
        print("[startup] [OK] RAG Model loaded into memory!")
    except Exception as e:
        print(f"[startup] [WARN] RAG Model pre-load skipped: {e}")

    try:
        # Pre-load Kata Mode models (Dual-Stem + Single V1 from Production_Best)
        await loop.run_in_executor(None, _load_kata_models)
        print("[startup] [OK] Kata models (Dual-Stem + Single V1) loaded!")
    except Exception as e:
        print(f"[startup] [WARN] Kata models pre-load skipped: {e}")


def _load_model_cache():
    """Trigger the classify router's lazy model load."""
    try:
        from app.routers.classify import load_model
        load_model()
    except Exception:
        pass   # model will still load on first request


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
@app.get("/")
async def root():
    return {"message": "Martial Arts AI Trainer API is running!", "version": "2.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}