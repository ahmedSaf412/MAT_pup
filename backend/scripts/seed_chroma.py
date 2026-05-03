"""
backend/scripts/seed_chroma.py
Run this ONCE to index coaching_chunks.json into ChromaDB.

Usage (from project root with cvEnv active):
    cd backend
    python scripts/seed_chroma.py
"""

import json
import sys
from pathlib import Path

# ── Make sure 'app' package is importable ────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    print("❌  chromadb not installed. Run:  pip install chromadb sentence-transformers")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR   = Path(__file__).resolve().parent.parent / "app" / "rag" / "data"
CHUNKS_FILE = DATA_DIR / "coaching_chunks.json"
CHROMA_DIR  = DATA_DIR / "chroma_db"

if not CHUNKS_FILE.exists():
    print(f"❌  coaching_chunks.json not found at {CHUNKS_FILE}")
    sys.exit(1)

# ── Load knowledge base ───────────────────────────────────────────────────────
with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)

print(f"📚  Loaded {len(chunks)} coaching chunks")

# ── Embedding function (runs locally, no API key needed) ─────────────────────
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"   # ~22 MB model, downloads on first run
)

# ── ChromaDB client ───────────────────────────────────────────────────────────
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
client = chromadb.PersistentClient(path=str(CHROMA_DIR))

# Wipe and recreate so re-running is safe
try:
    client.delete_collection("coaching_knowledge")
    print("🗑️   Deleted existing 'coaching_knowledge' collection")
except Exception:
    pass

collection = client.create_collection(
    name="coaching_knowledge",
    embedding_function=ef,
    metadata={"hnsw:space": "cosine"},   # cosine similarity
)

# ── Index chunks ──────────────────────────────────────────────────────────────
ids       = [str(i) for i in range(len(chunks))]
documents = [c["text"] for c in chunks]
metadatas = [
    {
        "move":       c.get("move", "general"),
        "joint":      c.get("joint", ""),
        "error_type": c.get("error_type", ""),
        "topic":      c.get("topic", ""),
    }
    for c in chunks
]

collection.add(ids=ids, documents=documents, metadatas=metadatas)

print(f"✅  Indexed {len(chunks)} chunks into ChromaDB at {CHROMA_DIR}")
print()
print("Move breakdown:")
from collections import Counter
counts = Counter(c.get("move", "general") for c in chunks)
for move, count in sorted(counts.items()):
    print(f"   {move:20s}  {count} chunks")
print()
print("🎉  Done! The RAG retriever is ready.")
