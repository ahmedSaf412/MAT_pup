# =============================================================================
# backend/Dockerfile
# =============================================================================
#
# Multi-stage build:
#   Stage 1 "builder" — installs ALL Python packages + pre-downloads the
#                       HuggingFace embedding model (all-MiniLM-L6-v2 ~90 MB).
#   Stage 2 "runtime" — copies only what's needed so the final image is lean.
#
# WHY multi-stage?
#   Compiling packages (gcc, g++) produces intermediate files that bloat the
#   image.  We install in stage 1, copy the result to stage 2, and the
#   compiler tools never appear in the final image.
# =============================================================================

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /install

# System packages required to COMPILE some Python wheels:
#   gcc / g++       — needed by some C-extension packages
#   libgl1          — OpenCV runtime dependency
#   libglib2.0-0    — OpenCV / GLib dependency
#   libpq-dev       — compiles psycopg2 (PostgreSQL driver)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgl1 \
    libglib2.0-0 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker caches this layer.
# If requirements.txt doesn't change, pip install is SKIPPED on the next build.
COPY requirements.txt .

# ── tensorflow_intel fix ──────────────────────────────────────────────────────
# requirements.txt was written on Windows and includes tensorflow_intel==2.18.0
# That package is Windows-ONLY and will fail on Linux (which Docker uses).
# Solution: strip that single line out before installing.
# The plain tensorflow==2.18.0 line already provides everything we need on Linux.
RUN pip install --no-cache-dir --upgrade pip && \
    grep -v "tensorflow_intel" requirements.txt > requirements_linux.txt && \
    pip install --no-cache-dir -r requirements_linux.txt

# ── Pre-download HuggingFace embedding model ──────────────────────────────────
# retriever.py loads SentenceTransformer('all-MiniLM-L6-v2') at startup.
# Without this step, every container START would download ~90 MB from the internet.
# Baking it into the image means it downloads ONCE at build time and never again.
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2'); \
print('[Docker] HuggingFace model cached successfully')"


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Runtime-only system libraries (no compiler tools needed here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the HuggingFace model cache so no download happens at startup
COPY --from=builder /root/.cache /root/.cache

# Copy application source code
# NOTE: .dockerignore controls exactly what gets copied here.
# It excludes: training CSVs, old model runs, scratch/, uploads/, .env
COPY app/ ./app/

# Expose the port FastAPI listens on
EXPOSE 8000

# Health check — Docker will mark the container "unhealthy" if this fails.
# start_period=60s gives TensorFlow time to load models before checks begin.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start the FastAPI server
# --host 0.0.0.0 makes it reachable from outside the container
# --port 8000     matches EXPOSE above and docker-compose ports mapping
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
