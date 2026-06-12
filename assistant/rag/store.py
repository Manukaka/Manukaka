"""ChromaDB persistent vector store (cosine similarity, idempotent upserts)."""
from typing import Dict, List

from .. import config

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        import chromadb
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        _collection = client.get_or_create_collection(
            name="life", metadata={"hnsw:space": "cosine"}
        )
    return _collection


def upsert_chunks(chunks: List[Dict], embeddings: List[List[float]]) -> None:
    if not chunks:
        return
    col = _get_collection()
    col.upsert(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
        embeddings=embeddings,
    )


def query(embedding: List[float], top_k: int) -> List[Dict]:
    col = _get_collection()
    if col.count() == 0:
        return []
    res = col.query(query_embeddings=[embedding], n_results=min(top_k, col.count()))
    out = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"text": doc, "metadata": meta, "similarity": 1.0 - dist})
    return out


def count() -> int:
    return _get_collection().count()
