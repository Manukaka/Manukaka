"""BGE-M3 embeddings (lazy singleton). Runs on CPU by default so the GPU stays
free for the LLM while chatting; pass device='cuda' for faster bulk ingestion."""
from typing import List

from .. import config

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        cfg = config.CFG["rag"]
        _model = SentenceTransformer(cfg["embedding_model"], device=cfg["embedding_device"])
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


def embed_query(query: str) -> List[float]:
    return embed_texts([query])[0]
