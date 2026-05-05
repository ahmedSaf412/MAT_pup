# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import classify, video, rag_feedback
from app.routers import auth, sessions, recordings, live_session

app = FastAPI(
    title="Martial Arts AI Trainer",
    description="AI-powered karate movement classification and correction API",
    version="1.0.0",
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
    init_db()

# ── Core AI routers ───────────────────────────────────────────────────────────
app.include_router(classify.router)
app.include_router(video.router)
app.include_router(rag_feedback.router)

# ── Auth + User management ────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(auth.users_router)   # /api/users/me alias

# ── Session + Detection + Recording ──────────────────────────────────────────
app.include_router(sessions.router)
app.include_router(recordings.router)

# ── WebSocket (coach live session) ────────────────────────────────────────────
app.include_router(live_session.router)

# ── Health endpoints ──────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "Martial Arts AI Trainer API is running!", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}