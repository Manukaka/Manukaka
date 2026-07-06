import time
from datetime import datetime

from assistant.rag import retriever


def _hit(similarity, end_ts, cid=None, contact="Aai", source_type="whatsapp",
         text="hello", source_file="f.txt"):
    return {
        "id": cid or text,
        "text": text,
        "similarity": similarity,
        "metadata": {
            "contact": contact,
            "source_type": source_type,
            "source_file": source_file,
            "start_ts": end_ts,
            "end_ts": end_ts,
        },
    }


def _vector_only(monkeypatch, hits):
    """Route retrieve() through a fake vector search with hybrid + rewrite off."""
    monkeypatch.setitem(retriever.config.CFG["rag"], "hybrid", False)
    monkeypatch.setitem(retriever.config.CFG["rag"], "query_rewrite", False)
    monkeypatch.setattr(retriever.embeddings, "embed_query", lambda q: [0.0])
    monkeypatch.setattr(retriever.store, "query",
                        lambda emb, k: [dict(h) for h in hits])


def test_recency_factor_bounds():
    now = time.time()
    assert retriever._recency_factor(now, now) == 1.0
    assert retriever._recency_factor(now - 400 * 86400, now) == 0.0  # >1 year old
    half = retriever._recency_factor(now - 182.5 * 86400, now)
    assert 0.4 < half < 0.6


def test_retrieve_boosts_recent_chunks(monkeypatch):
    now = time.time()
    year_old = now - 370 * 86400
    _vector_only(monkeypatch, [_hit(1.0, year_old, text="old"),
                               _hit(0.95, now, text="recent")])
    out = retriever.retrieve("anything")
    # ranks are close (RRF), so the fresh chunk's 1.1x recency boost wins
    assert [h["text"] for h in out] == ["recent", "old"]


def test_retrieve_keeps_top_k_use(monkeypatch):
    now = time.time()
    _vector_only(monkeypatch, [_hit(1.0 - i * 0.01, now, text=f"h{i}") for i in range(10)])
    assert len(retriever.retrieve("anything")) == 6  # config top_k_use


def test_hybrid_fusion_prefers_chunks_both_searches_agree_on(monkeypatch):
    now = time.time()
    a, b, c = (_hit(0.9, now, cid="A", text="A"),
               _hit(0.8, now, cid="B", text="B"),
               _hit(0.7, now, cid="C", text="C"))
    monkeypatch.setitem(retriever.config.CFG["rag"], "query_rewrite", False)
    monkeypatch.setattr(retriever.embeddings, "embed_query", lambda q: [0.0])
    monkeypatch.setattr(retriever.store, "query", lambda emb, k: [dict(a), dict(b)])
    monkeypatch.setattr(retriever.keyword, "search", lambda q, k: [dict(b), dict(c)])
    monkeypatch.setattr(retriever.keyword, "known_contacts", lambda: [])

    out = retriever.retrieve("anything")
    assert out[0]["text"] == "B"  # ranked by both lists → fused score wins


def test_contact_named_in_question_gets_boosted(monkeypatch):
    now = time.time()
    hits = [_hit(1.0, now, cid="1", text="aai chunk", contact="Aai"),
            _hit(0.9, now, cid="2", text="rahul chunk", contact="Rahul")]
    monkeypatch.setitem(retriever.config.CFG["rag"], "query_rewrite", False)
    monkeypatch.setattr(retriever.embeddings, "embed_query", lambda q: [0.0])
    monkeypatch.setattr(retriever.store, "query", lambda emb, k: [dict(h) for h in hits])
    monkeypatch.setattr(retriever.keyword, "search", lambda q, k: [])
    monkeypatch.setattr(retriever.keyword, "known_contacts", lambda: ["Aai", "Rahul"])

    out = retriever.retrieve("what did Rahul say about the trip?")
    assert out[0]["text"] == "rahul chunk"  # 1.3x contact boost beats one rank


def test_search_failures_degrade_not_crash(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("index broken")
    monkeypatch.setitem(retriever.config.CFG["rag"], "query_rewrite", False)
    monkeypatch.setattr(retriever.embeddings, "embed_query", boom)
    monkeypatch.setattr(retriever.keyword, "search", boom)
    monkeypatch.setattr(retriever.keyword, "known_contacts", boom)
    assert retriever.retrieve("anything") == []


def test_format_context_numbers_labels_and_dates():
    ts = datetime(2024, 5, 13, 9, 0).timestamp()
    hits = [
        _hit(1.0, ts, contact="Aai", source_type="whatsapp", text="line one"),
        _hit(0.9, ts, contact="Rahul", source_type="call", text="line two"),
    ]
    block = retriever.format_context(hits)
    assert "[1] WhatsApp with Aai, 13 May 2024\nline one" in block
    assert "[2] Call with Rahul, 13 May 2024\nline two" in block


def test_sources_match_context_numbering():
    ts = datetime(2024, 5, 13, 9, 0).timestamp()
    hits = [_hit(1.0, ts, contact="Aai", source_file="chat.txt")]
    assert retriever.sources(hits) == [
        {"n": 1, "label": "WhatsApp with Aai, 13 May 2024", "file": "chat.txt"}
    ]


def test_format_context_empty():
    assert retriever.format_context([]) == ""
    assert retriever.sources([]) == []
