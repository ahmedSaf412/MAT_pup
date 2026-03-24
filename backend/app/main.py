# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import classify  # ← ADD THIS

app = FastAPI(title="Martial Arts AI Trainer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    init_db()

app.include_router(classify.router)  # ← ADD THIS LINE

@app.get("/")
async def root():
    return {"message": "Martial Arts AI Trainer API is running!"}

@app.get("/health")
async def health():
    return {"status": "healthy"}