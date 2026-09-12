# 🐳 Docker Containerization — What Was Done & Why

> This document explains every file created during containerization, the reasoning behind each decision, and how all the pieces fit together. Written so you can study it and understand Docker from this real project.

---

## What Was Created

| File | Type |
|------|------|
| `backend/.dockerignore` | Tells Docker what NOT to copy into the image |
| `frontend/.dockerignore` | Same, for frontend |
| `backend/Dockerfile` | Recipe to build the Python/FastAPI container image |
| `frontend/Dockerfile` | Recipe to build the Next.js container image |
| `docker-compose.yml` | Orchestrates all 3 services together |
| `.env.example` | Template for secrets (the user fills this in) |
| `frontend/next.config.mjs` | Modified: added `output: 'standalone'` |

---

## Concept: What is a Docker Image vs Container?

```
Dockerfile  →  (docker build)  →  Image  →  (docker run)  →  Container
  "recipe"                      "snapshot"                   "running app"
```

- **Image** = a frozen snapshot of the filesystem (code + dependencies + OS libs)
- **Container** = a running instance of an image
- **docker-compose.yml** = runs multiple containers at once and wires them together

---

## File 1: `backend/.dockerignore`

**What it is:** Like `.gitignore` but for Docker. When Docker copies files into the image during `docker build`, it skips everything listed here.

**Why we need it:**
Without it, Docker would copy:
- 62 MB of training CSV files (not used at runtime)
- 9 old model training run folders (~90 MB of `.keras` files)
- Python `__pycache__` directories
- Your `.env` file (would bake your secrets into a shareable image — dangerous!)

**Key decisions:**
```
uploads/        → excluded because it's a runtime volume (created by users)
*.db / *.sqlite → excluded because Docker uses PostgreSQL, not SQLite
app/data/karate_*.csv → not needed at runtime (training data only)
app/models/Results/Run_*/ → old experiments, code only loads Production_Best/
scratch/        → one-off scripts that already ran
.env            → NEVER bake secrets into an image
```

---

## File 2: `frontend/.dockerignore`

**Key decisions:**
```
node_modules/  → excluded because Docker will run `npm ci` and install fresh
                 (sharing node_modules across OS boundaries causes subtle bugs)
.next/         → excluded because Docker will run `next build` fresh
```

---

## File 3: `backend/Dockerfile`

### Multi-stage builds — the core concept

```dockerfile
FROM python:3.11-slim AS builder   # Stage 1: "builder"
...install everything...

FROM python:3.11-slim              # Stage 2: "runtime"
...copy only the result...
```

**Why two stages?**
Compiling Python C extensions (like psycopg2, tensorflow) needs `gcc`, `g++`. These compiler tools are ~200 MB. The compiled result (the `.so` files) is only a few MB. Multi-stage lets us compile in stage 1 and throw away the compilers in stage 2.

**Final image has:** Python packages + compiled libs + your code + HuggingFace model cache.  
**Final image does NOT have:** gcc, g++, pip cache, __pycache__, .env, training data.

### The tensorflow_intel fix

```dockerfile
grep -v "tensorflow_intel" requirements.txt > requirements_linux.txt
pip install -r requirements_linux.txt
```

**Why:** `requirements.txt` was written on Windows and includes `tensorflow_intel==2.18.0`. That package is Windows-only — it crashes on Linux. Docker always runs Linux containers. The fix is to filter that line out before installing. Plain `tensorflow==2.18.0` (already in the file) handles everything on Linux.

### Baking the HuggingFace model

```dockerfile
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

**Why:** `retriever.py` uses this model to embed text into vectors for ChromaDB search. Without this step, every time someone runs `docker compose up` from scratch it would download ~90 MB. By running this during `docker build`, the model is stored in `/root/.cache` inside the builder, then copied to the runtime image. Download happens once at build time, never at runtime.

### HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
```

**Why `start_period=60s`:** TensorFlow loads 3 ML models at startup (~15-30 seconds). Docker needs to know not to start checking immediately, otherwise the container would be marked "unhealthy" while models are still loading.

---

## File 4: `frontend/Dockerfile`

### Why Next.js needs `output: 'standalone'`

Next.js has different output modes:
- **Default:** Requires `node_modules` + `next` CLI to serve (`next start`)
- **Standalone:** Bundles everything into a single `server.js` + minimal `node_modules`

Without standalone mode, the production container would need all ~600 MB of `node_modules`. With standalone mode, the runtime image only needs ~30-50 MB of minimal runtime dependencies.

```dockerfile
# Stage 1: Build
npm run build   → produces .next/standalone/server.js

# Stage 2: Runtime
COPY .next/standalone  ./       ← the self-contained server
COPY .next/static      ./.next/static   ← CSS, JS chunks (not in standalone)
COPY public            ./public          ← favicon, images
CMD ["node", "server.js"]       ← plain Node.js, no next CLI
```

**Why copy `.next/static` separately?** Next.js standalone doesn't include the static assets folder. They must be placed exactly at `.next/static` relative to `server.js` or the browser will get 404s on all CSS and JavaScript.

---

## File 5: `docker-compose.yml`

### Service: `db`

```yaml
image: pgvector/pgvector:pg17
```

**Why this image instead of plain `postgres:17`?**  
`pgvector/pgvector:pg17` is the official PostgreSQL 17 image with the pgvector extension pre-installed. The old manual setup required downloading a `.zip` from GitHub and copying DLLs. With this image, `CREATE EXTENSION vector;` works out of the box — no manual step needed.

### Service networking — why `@db:5432` not `@localhost:5432`

```yaml
DATABASE_URL: postgresql://postgres:...@db:5432/martial_arts_db
```

Inside Docker Compose, containers talk to each other using **service names** as hostnames. The `db` service is reachable at hostname `db` from the `backend` service. `localhost` inside the backend container refers to the backend container itself, not the database.

### `depends_on` with healthcheck condition

```yaml
depends_on:
  db:
    condition: service_healthy
```

**Why not just `depends_on: db`?**  
`depends_on: db` only waits for the container to START, not for PostgreSQL to be READY. PostgreSQL takes a few seconds to initialize after the container starts. Without `condition: service_healthy`, FastAPI would try to connect before PostgreSQL is accepting connections and crash. The `service_healthy` condition waits for `pg_isready` to succeed.

### `start_period: 90s` on backend healthcheck

TensorFlow loads at startup: XGBoost (~0.3s), Single-BiLSTM (~5s), Dual-Stem (~5s), plus the RAG model warming. The total startup is 10-30 seconds. We give 90 seconds grace period so Docker doesn't kill the container as "unhealthy" during model loading.

### Named volumes

```yaml
volumes:
  postgres_data:   # persists across docker compose down
  uploads_data:    # user recordings persist
```

`docker compose down` stops containers and removes them. Volumes survive.  
`docker compose down -v` ALSO deletes volumes → fresh database.

---

## File 6: `frontend/next.config.mjs` change

Added `output: 'standalone'` at the top of `nextConfig`. This is the only change to an existing file. It tells `next build` to produce the `.next/standalone/server.js` that the frontend Dockerfile uses.

---

## How the Build Flow Works End-to-End

```
docker compose up --build
        │
        ├─── builds backend image ───────────────────────────────────────┐
        │     1. python:3.11-slim (builder stage)                        │
        │     2. apt-get: gcc, g++, libgl1, libpq-dev                   │
        │     3. pip install (tensorflow_intel stripped)                  │
        │     4. download HuggingFace model → /root/.cache               │
        │     5. python:3.11-slim (runtime stage)                        │
        │     6. copy packages + cache + /app code                       │
        │                                                                 │
        ├─── builds frontend image ──────────────────────────────────────┤
        │     1. node:20-alpine (builder stage)                          │
        │     2. npm ci                                                   │
        │     3. next build → .next/standalone/server.js                 │
        │     4. node:20-alpine (runtime stage)                          │
        │     5. copy standalone + static + public                       │
        │                                                                 │
        └─── starts 3 containers ────────────────────────────────────────┘
              db         → PostgreSQL 17 + pgvector (port 5432 internal)
              backend    → FastAPI (port 8000) — waits for db healthcheck
              frontend   → Next.js (port 3000) — waits for backend
```

---

## What Happens When Someone New Clones & Runs

```
git clone <repo>
          ↓
Download Drive assets → Production_Best/, rag/data/, data/Animation/, data/Examplers/
          ↓
cp .env.example .env  →  fill in DB_PASSWORD, SECRET_KEY, GROQ_API_KEY
          ↓
docker compose up --build
          ↓
  Docker builds images (10-15 min first time, then cached)
          ↓
  PostgreSQL starts → FastAPI connects → init_db() creates all tables
          ↓
  TensorFlow loads 3 models → ChromaDB loads from chroma_db/ → HuggingFace loads from cache
          ↓
  Frontend builds and serves
          ↓
  http://localhost:3000  ✅
```

**No manual database restore.** No `pip install`. No `npm install`. No seed scripts (ChromaDB is already populated in the repo's `rag/data/chroma_db/`).

---

## Quick Reference Commands

```bash
# First time or after code change:
docker compose up --build

# Subsequent starts (fast, uses cached images):
docker compose up

# Run in background:
docker compose up -d

# Watch logs:
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db

# Stop (keeps database):
docker compose down

# Stop + wipe database (full reset):
docker compose down -v

# Rebuild only one service after a code change:
docker compose up --build backend
docker compose up --build frontend

# Open a shell inside a running container:
docker exec -it martial_arts_backend bash
docker exec -it martial_arts_db psql -U postgres martial_arts_db
```
