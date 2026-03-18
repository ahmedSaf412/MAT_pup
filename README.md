# 🥋 AI Martial Arts Trainer

An AI-powered karate training platform that classifies and corrects trainee movements in real time, guiding them through structured kata courses aligned with belt progression.

---

## 📌 Project Overview

The AI Martial Arts Trainer is a senior graduation project that combines computer vision, deep learning (Bi-LSTM, CNN-LSTM, ST-GCN + Attention), and a full-stack web platform to help karate trainees learn and perfect their katas.

### Current Phase — Phase 1: Classification & Core Setup
- **AI Model Pipeline**: Training and evaluating movement classifiers on karate movements (e.g., `maegeri` front-kick, `gyaku-zuki` reverse-punch).
- **Backend API**: FastAPI server exposing REST endpoints for movement classification sessions.
- **Frontend**: Next.js application (scaffold ready), to be wired to the backend.
- **Goal**: Given a video/pose sequence of a trainee performing a core kata movement, classify what movement it is.

### Upcoming — Phase 2: Structured Kata Courses
Belt-based course system where trainees:
1. Select a course (belt level → kata, e.g., **Heian Nidan** as the starting point).
2. Watch warmup guidance for the kata.
3. Reach the **core movement segment** → AI classifies the performed technique.
4. Receive correction feedback based on the classification result.

**Starting kata: Heian Nidan** — chosen because it features `maegeri` and `gyaku-zuki`, which are well-suited for initial detection and classification.

---

## 🗂️ Project Structure

```
martial-arts-trainer/
├── backend/                  # FastAPI Python backend
│   ├── app/
│   │   ├── main.py           # App entry point & CORS config
│   │   ├── models/           # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── session.py
│   │   │   └── move.py
│   │   └── data/             # Training data (gitignored if large)
│   ├── requirements.txt
│   └── .env                  # Local secrets — DO NOT COMMIT
├── frontend/                 # Next.js frontend
│   ├── app/
│   ├── public/
│   └── package.json
├── docs/                     # Project documentation
├── presentation.html         # Project presentation
└── README.md
```

---

## ⚡ Getting Started

### Prerequisites
- Python 3.10+ with a virtual environment (`cvEnv` recommended) i was using 3.12.7
- Node.js LTS (v18+)
- ->https://nodejs.org/en/download -->scroll down to Windows Installer (.msi)
- Git

---

### 🔧 Backend Setup (FastAPI)

```bash
# 1. Activate your Python environment
# Windows:
.\cvEnv\Scripts\activate

# 2. Install Python dependencies
cd backend
pip install -r requirements.txt

# 3. Create your local .env (never commit this)
# backend/.env
DATABASE_URL=sqlite:///./martial_arts.db
SECRET_KEY=your-secret-key-here
FRONTEND_URL=http://localhost:3000

# 4. Run the development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend will be available at: **http://127.0.0.1:8000**  
API docs (Swagger): **http://127.0.0.1:8000/docs**

---

### 🎨 Frontend Setup (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at: **http://localhost:3000**

---

## 🧠 AI Models

Models are trained in Jupyter notebooks under `backend/app/models/`:

| Model | Notebook | Status |
|-------|----------|--------|
| Bi-LSTM | `01_BiLSTM_Tournament.ipynb` | ✅ In progress |
| CNN-LSTM | *(upcoming)* | 🔲 Planned |
| ST-GCN + Attention | *(upcoming)* | 🔲 Planned |

Evaluation metrics: **Accuracy**, **F1-Score**, **Latency**, **Model Size**

---

## 🔒 Security Notes

The following are **gitignored** and must never be committed:
- `backend/.env` — contains `SECRET_KEY` and database URL
- `*.db` / `*.sqlite` — local SQLite database files
- `venv/`, `cvEnv/`, `node_modules/` — local dependency folders

---

## 🤝 Team

Senior Graduation Project — Computer Science, 2026  
Branch: `Safwat_branch`
