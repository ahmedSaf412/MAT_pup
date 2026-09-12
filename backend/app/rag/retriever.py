import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

CHROMA_DB_DIR = Path(__file__).resolve().parent / "data" / "chroma_db"

# Initialize singletons for performance
_client = None
_collection = None

def get_collection():
    global _client, _collection
    if _client is None:
        if not CHROMA_DB_DIR.exists():
            print(f"Warning: ChromaDB dir not found at {CHROMA_DB_DIR}")
            return None
        _client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        try:
            _collection = _client.get_collection(name="coaching_knowledge", embedding_function=sentence_transformer_ef)
        except ValueError:
            print("Warning: Collection 'coaching_knowledge' does not exist.")
            return None
    return _collection

def retrieve(query: str, move: str = None, top_k: int = 3) -> list[dict]:
    """Retrieve top-k relevant coaching chunks for a given error query."""
    collection = get_collection()
    if collection is None:
        return []

    # Prepare where filter
    where_filter = None
    if move:
        where_filter = {"move": {"$eq": move}}

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),   # guard: can't request > docs that exist
        where=where_filter,
        include=["metadatas", "documents", "distances"]
    )

    if not results or not results['documents'] or not results['documents'][0]:
        return []

    docs = results['documents'][0]
    metas = results['metadatas'][0]
    
    retrieved_chunks = []
    for doc, meta in zip(docs, metas):
        retrieved_chunks.append({
            "text": doc,
            "metadata": meta
        })
        
    return retrieved_chunks
