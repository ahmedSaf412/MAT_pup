# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import classify, video   # ← both routers imported AFTER FastAPI

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

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(classify.router)
app.include_router(video.router)

# ── Health endpoints ─────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "Martial Arts AI Trainer API is running!", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}