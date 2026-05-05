"""
backend/scripts/seed_pg_rag.py

Reads coaching_chunks.json (already used by ChromaDB) and inserts
the same documents into the rag_document table with embeddings.

Usage (from backend/ with cvEnv active):
    python scripts/seed_pg_rag.py

Requires:
    - PostgreSQL running with pgvector enabled
    - DATABASE_URL in backend/.env
    - pip install pgvector sentence-transformers
"""

import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.database import engine, SessionLocal
from app.models.rag import RagDocument
from sentence_transformers import SentenceTransformer

CHUNKS_PATH = Path(__file__).resolve().parent.parent / "app" / "rag" / "data" / "coaching_chunks.json"

print("📚  Loading coaching chunks …")
with open(CHUNKS_PATH) as f:
    chunks = json.load(f)

print("🔢  Loading embedding model (all-mpnet-base-v2) …")
model = SentenceTransformer("all-mpnet-base-v2")

db = SessionLocal()

existing = db.query(RagDocument).count()
if existing > 0:
    print(f"ℹ️   rag_document already has {existing} rows — skipping (delete them first to re-seed).")
    db.close()
    sys.exit(0)

print(f"🔄  Embedding {len(chunks)} chunks …")
for i, chunk in enumerate(chunks):
    text     = chunk.get("text", "")
    category = chunk.get("metadata", {}).get("topic", "general")
    vector   = model.encode(text).tolist()

    db.add(RagDocument(
        title    = category,
        content  = text,
        category = category,
        embedding = vector,
    ))
    if (i + 1) % 10 == 0:
        db.commit()
        print(f"   … {i + 1}/{len(chunks)}")

db.commit()
db.close()
print(f"\n✅  Seeded {len(chunks)} documents into rag_document with pgvector embeddings.")
