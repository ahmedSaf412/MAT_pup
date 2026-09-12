# backend/app/rag/pg_retriever.py
# pgvector-based RAG retrieval — alternative/supplement to ChromaDB
#
# Usage:
#   results = pg_retrieve(query_text, move=move_id, top_k=3, db=db)
#
# Schema: rag_document (id, title, content, category, embedding vector(768))
# Similarity: cosine distance via pgvector <=> operator
#
# To populate: run scripts/seed_pg_rag.py (see below)

from __future__ import annotations

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text

# We load the embedding model lazily (same model as ChromaDB retriever)
_embedder = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-mpnet-base-v2")
        print("[pg_retriever] Embedding model loaded.")
    return _embedder


def pg_retrieve(
    query_text: str,
    move:       Optional[str] = None,
    top_k:      int           = 3,
    db:         Session       = None,
) -> List[dict]:
    """
    Embed query_text with sentence-transformers, then find the top_k most
    similar rows in rag_document using pgvector cosine distance.

    Returns list of dicts: {"text": ..., "metadata": {"topic": ..., "id": ...}}
    """
    if db is None:
        return []

    embedder   = _get_embedder()
    query_vec  = embedder.encode(query_text).tolist()   # 768-dim list

    # Build SQL — filter by category if a move is supplied
    where_clause = "WHERE category = :move" if move else ""
    sql = text(f"""
        SELECT id, title, content, category,
               1 - (embedding <=> CAST(:vec AS vector)) AS similarity
        FROM   rag_document
        {where_clause}
        ORDER  BY embedding <=> CAST(:vec AS vector)
        LIMIT  :top_k
    """)

    params = {"vec": str(query_vec), "top_k": top_k}
    if move:
        params["move"] = move

    try:
        rows = db.execute(sql, params).fetchall()
        return [
            {
                "text":     row.content,
                "metadata": {"topic": row.category or row.title, "id": row.id},
                "score":    float(row.similarity),
            }
            for row in rows
        ]
    except Exception as e:
        print(f"[pg_retriever] pgvector query failed: {e}")
        return []


def pg_log_query(
    user_id:       Optional[int],
    question:      str,
    answer:        str,
    source_doc_ids: List[int],
    db:            Session,
):
    """Persist a Q&A interaction to rag_query for analytics."""
    from app.models.rag import RagQuery
    rq = RagQuery(
        user_id        = user_id,
        question       = question,
        answer         = answer,
        source_doc_ids = source_doc_ids,
    )
    db.add(rq)
    db.commit()
