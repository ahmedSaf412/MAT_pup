# 🥋 AI Martial Arts Trainer

An AI-powered karate training platform that uses real-time pose detection to classify techniques, display animated 3D skeleton references, and deliver personalized coaching feedback via a RAG pipeline.

**Tech Stack:** FastAPI · Next.js 16 · PostgreSQL · ChromaDB · TensorFlow · MediaPipe · Groq (Llama-3.3-70b)

---

## ⚡ Quick Start (Docker — Recommended)

> **Requires:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free) + Git

### 1. Clone the repository

```bash
git clone https://github.com/mohamedaboelenin617-web/martial-arts-trainer.git
cd martial-arts-trainer
```

### 2. Download large assets from Google Drive

> 📦 **Google Drive:** https://drive.google.com/drive/folders/1v1A7Pvya5DbgVy2Opws-EgFH3vIyVTpX

Download and place the files exactly like this:

```
backend/
└── app/
    ├── models/
    │   └── Results/
    │       └── Production_Best/           ← download this folder from Drive
    │           ├── best_dual_stem_fusion.keras
    │           ├── best_single_bilstmV1.keras
    │           ├── best_single_bilstmV2.keras
    │           ├── model_xgboost.pkl
    │           └── model_random_forest.pkl
    ├── rag/
    │   └── data/                          ← download this folder from Drive
    │       ├── chroma_db/                 ← pre-built vector store (no setup needed)
    │       ├── coaching_chunks.json
    │       ├── exampler_sequences.json
    │       ├── mads_reference_sequences.json
    │       └── pro_reference_angles.json
    └── data/                              ← download this folder from Drive
        ├── Animation/
        │   ├── GedanBarai/
        │   │   ├── GedanBarai_front_001_0165.mov
        │   │   ├── GedanBarai_front_001_0165.json
        │   │   ├── GedanBarai_side_001_0166.mov
        │   │   └── GedanBarai_side_001_0166.json
        │   ├── Gyakudzuki/
        │   │   ├── Gyakudzuki_Front.mov
        │   │   ├── Gyakudzuki_Front.json
        │   │   ├── Gyakudzuki_Side.mov
        │   │   └── Gyakudzuki_Side.json
        │   └── Maegeri/
        │       ├── MaeGeri_Front.mov
        │       ├── MaeGeri_Front.json
        │       ├── MaeGeri_Side.mov
        │       └── MaeGeri_Side.json
        └── Examplers/
            ├── GedanBarai_side_003_0153.mp4
            ├── Gyakudzuki_Front.mp4
            └── MaeGeri_side_003_0057.mp4
```

### 3. Create the `.env` file at the project root

```env
# PostgreSQL password — Docker creates the DB with this, pick anything
DB_PASSWORD=YourStrongPassword123

# JWT secret — generate any long random string
SECRET_KEY=some-very-long-random-secret-key-here

# Groq API Key — get a FREE key at https://console.groq.com
# If you skip this, the app still works with built-in rule-based coaching
GROQ_API_KEY=gsk_your_key_here

ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### 4. Run

```bash
docker compose up --build
```

⏳ First build takes **10–15 minutes** (downloads Python + Node dependencies once).
All subsequent starts are fast: `docker compose up`

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **Backend API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |

---

## 🐳 Docker Management

```bash
# Run in the background
docker compose up --build -d

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop all services
docker compose down

# Stop and wipe the database (full fresh start)
docker compose down -v

# Rebuild only the backend after a code change
docker compose up --build backend
```

---

## 🖥️ Manual Setup (Without Docker)

Only needed if you want to run or develop without Docker.

### Prerequisites

- Python 3.12
- Node.js v18+
- PostgreSQL 17 with pgvector extension

### Backend

```powershell
# From project root — create and activate virtual environment
python -m venv cvEnv
.\cvEnv\Scripts\activate

pip install -r backend/requirements.txt
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/martial_arts_db
SECRET_KEY=your-secret-key-change-this
FRONTEND_URL=http://localhost:3000
GROQ_API_KEY=gsk_your_key_here
```

Start backend:

```powershell
cd backend
uvicorn app.main:app --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

### PostgreSQL Setup (manual only)

1. Install [PostgreSQL 17](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)
2. Install pgvector — download `vector.v0.8.2-pg17.zip` from the Google Drive link above or from the [pgvector releases page](https://github.com/andreiramani/pgvector_pgsql_windows/releases)
3. In pgAdmin, create a database named `martial_arts_db` and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. The backend auto-creates all tables on first start via SQLAlchemy

---

## 🧠 System Architecture

```
User (Browser)
    │
    │  HTTP / WebSocket
    ▼
┌──────────────────┐     ┌──────────────────────────────────────────┐
│   Next.js 16     │────▶│            FastAPI Backend               │
│   (port 3000)    │     │            (port 8000)                   │
│                  │     │                                          │
│  MediaPipe Pose  │     │  ┌─────────────┐  ┌──────────────────┐  │
│  (in browser)    │     │  │  TensorFlow │  │   RAG Pipeline   │  │
│                  │     │  │  Classifiers│  │                  │  │
│  Pages:          │     │  │  · XGBoost  │  │  ChromaDB        │  │
│  · /train        │     │  │  · BiLSTM   │  │  → Groq LLM      │  │
│  · /kata         │     │  │  · DualStem │  │  (Llama-3.3-70b) │  │
│  · /dashboard    │     │  └─────────────┘  └──────────────────┘  │
│  · /coach        │     │                         │                │
└──────────────────┘     └─────────────────────────┼────────────────┘
                                                    │
                                             ┌──────▼──────┐
                                             │  PostgreSQL  │
                                             │  (port 5432) │
                                             └─────────────┘
```

### RAG Coaching Pipeline

```
User performs a rep (30 frames auto-captured)
        ↓
Landmarks → 14 joint angles computed
        ↓
DTW aligns user sequence to master Exemplar frame-by-frame
        ↓
Joints with mean deviation > 12° are flagged
        ↓
Error descriptions queried in ChromaDB (semantic search)
        ↓
Groq Llama-3.3-70b generates friendly coaching text
        ↓
"🤖 AI Sensei" panel shows feedback on the Train page
```

### Kata Real-Time Mode

```
Camera → 30-frame sliding window → WebSocket → DualStem + BiLSTM (concurrent)
                                             → Real-time confidence feedback
```

---

## 📁 Project Structure

```
martial-arts-trainer/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                     ← FastAPI app entry point
│       ├── config.py                   ← Reads from .env
│       ├── database.py                 ← SQLAlchemy (PostgreSQL)
│       ├── models/                     ← ORM models + ML model files
│       │   └── Results/Production_Best/← 5 trained models (from Drive)
│       ├── routers/                    ← 12 API route files
│       │   ├── classify.py             ← POST /api/classify
│       │   ├── kata.py                 ← WS  /api/kata/ws
│       │   ├── rag_feedback.py         ← POST /api/rag/feedback & /chat
│       │   ├── auth.py                 ← JWT auth
│       │   ├── coach.py                ← Coach management
│       │   └── ...
│       └── rag/
│           ├── angle_calculator.py     ← 14 joint angles from landmarks
│           ├── dtw_comparator.py       ← DTW alignment + error extraction
│           ├── pipeline.py             ← RAG orchestration
│           ├── retriever.py            ← ChromaDB semantic search
│           ├── llm_client.py           ← Groq API (Llama-3.3-70b)
│           └── data/                   ← ChromaDB + JSON files (from Drive)
└── frontend/
    ├── Dockerfile
    └── app/
        ├── train/page.js               ← Training page (auto-trigger + RAG)
        ├── kata/page.js                ← Kata real-time WebSocket mode
        ├── dashboard/                  ← User dashboard
        ├── coach/                      ← Coach live session view
        ├── components/
        │   ├── ChatBot.js              ← AI Sensei chatbot → /api/rag/chat
        │   ├── MoveSkeletonPreview.js  ← 3D front/side animated skeleton
        │   └── PoseCanvas.js           ← Live webcam pose overlay
        └── services/api.js             ← Axios instance (auto-injects JWT)
```

---

## 🔌 Key API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET`  | `/health` | Health check |
| `POST` | `/api/auth/login` | Login → JWT token |
| `POST` | `/api/auth/register` | Register new user |
| `POST` | `/api/classify` | 30 frames → move classification |
| `GET`  | `/api/video/{move}/{view}` | Stream reference video |
| `POST` | `/api/rag/feedback` | 30 frames → DTW → Groq coaching |
| `POST` | `/api/rag/chat` | Question → RAG → Groq answer |
| `WS`   | `/api/kata/ws` | Real-time sliding window inference |
| `POST` | `/api/sessions` | Create training session |
| `GET`  | `/api/recordings` | List session recordings |

Full interactive docs: **http://localhost:8000/docs**

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| Build fails with `tensorflow_intel` error | The Dockerfile already strips this Windows-only package. Make sure you're using the Dockerfile, not pip directly on Linux. |
| `FileNotFoundError: model_xgboost.pkl` | Download `Production_Best/` from Google Drive and place in `backend/app/models/Results/Production_Best/` |
| `Warning: ChromaDB dir not found` | Download the `data/` folder from Google Drive and place in `backend/app/rag/data/` |
| `GROQ_API_KEY missing` | Add `GROQ_API_KEY=gsk_...` to your `.env`. App still works without it (uses rule-based coaching fallback). |
| Frontend shows `Network Error` | Backend is not running or still starting. Wait ~30 seconds after `docker compose up`. |
| Camera won't start | Allow camera permission in browser for `localhost:3000`. |
| Armed overlay times out, never triggers | Open DevTools → Console and check `[AutoTrigger] energy=X.XXX`. If always 0, MediaPipe isn't detecting the pose. If low (< 0.2), lower `ENERGY_THRESHOLD` in `frontend/app/train/page.js`. |
| `docker compose down -v` to reset | This wipes the PostgreSQL volume. Use only for a clean slate. |

---

## 🎓 About This Project

**Martial Arts AI Trainer** is a graduation project implementing an end-to-end sports AI coaching system for Kyokushin Karate. The system classifies 3 fundamental techniques in real time:

| Move | Japanese | Key Joints |
|------|----------|------------|
| Downward Block | Gedan Barai | Arms, shoulders, hips |
| Reverse Punch | Gyaku Zuki | Arms, torso rotation |
| Front Kick | Mae Geri | Legs, hips, knee chamber |

**Models:**
- **XGBoost** — flat feature vector, fastest inference
- **Single BiLSTM** — sequential temporal modeling
- **Dual-Stem Fusion BiLSTM** — upper/lower body streams merged (best accuracy)

**Published:** IEEE Conference Paper — *"Applying Deep Learning and Computer Vision Techniques for an e-Sport and Smart Coaching System"*
