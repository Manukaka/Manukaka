import time
from datetime import datetime

from assistant.rag import retriever


def _hit(similarity, end_ts, contact="Aai", source_type="whatsapp", text="hello"):
    return {
        "text": text,
        "similarity": similarity,
        "metadata": {
            "contact": contact,
            "source_type": source_type,
            "start_ts": end_ts,
            "end_ts": end_ts,
        },
    }


def test_recency_factor_bounds():
    now = time.time()
    assert retriever._recency_factor(now, now) == 1.0
    assert retriever._recency_factor(now - 400 * 86400, now) == 0.0  # >1 year old
    half = retriever._recency_factor(now - 182.5 * 86400, now)
    assert 0.4 < half < 0.6


def test_retrieve_boosts_recent_chunks(monkeypatch):
    now = time.time()
    year_old = now - 370 * 86400
    hits = [_hit(1.0, year_old, text="old"), _hit(0.95, now, text="recent")]
    monkeypatch.setattr(retriever.embeddings, "embed_query", lambda q: [0.0])
    monkeypatch.setattr(retriever.store, "query", lambda emb, k: [dict(h) for h in hits])

    out = retriever.retrieve("anything")
    # 0.95 * 1.1 (fresh) > 1.0 * 1.0 (stale) → the recent chunk wins
    assert [h["text"] for h in out] == ["recent", "old"]


def test_retrieve_keeps_top_k_use(monkeypatch):
    now = time.time()
    hits = [_hit(1.0 - i * 0.01, now, text=f"h{i}") for i in range(10)]
    monkeypatch.setattr(retriever.embeddings, "embed_query", lambda q: [0.0])
    monkeypatch.setattr(retriever.store, "query", lambda emb, k: [dict(h) for h in hits])

    out = retriever.retrieve("anything")
    assert len(out) == 6  # config top_k_use


def test_format_context_labels_and_dates():
    ts = datetime(2024, 5, 13, 9, 0).timestamp()
    hits = [
        _hit(1.0, ts, contact="Aai", source_type="whatsapp", text="line one"),
        _hit(0.9, ts, contact="Rahul", source_type="call", text="line two"),
    ]
    block = retriever.format_context(hits)
    assert "[WhatsApp with Aai, 13 May 2024]\nline one" in block
    assert "[Call with Rahul, 13 May 2024]\nline two" in block


def test_format_context_empty():
    assert retriever.format_context([]) == ""
