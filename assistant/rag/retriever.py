"""Query flow: (rewritten) question → vector + BM25 searches → reciprocal-rank
fusion → recency/contact/date boosts → numbered context block + source list."""
import time
from datetime import datetime
from typing import Dict, List, Optional

from .. import config
from ..log import get_logger
from . import embeddings, keyword, query_analysis, rewrite, store

log = get_logger(__name__)

SOURCE_NAMES = {"whatsapp": "WhatsApp with", "sms": "SMS with",
                "call": "Call with", "telegram": "Telegram with"}


def _recency_factor(end_ts: float, now: float) -> float:
    """1.0 for today, fading to 0.0 at ~one year old."""
    age_days = max(0.0, (now - end_ts) / 86400)
    return max(0.0, 1.0 - age_days / 365)


def _search_queries(question: str, history: Optional[List[Dict]]) -> List[str]:
    queries = [question]
    try:
        queries += [q for q in rewrite.rewrite(question, history or []) if q not in queries]
    except Exception:
        log.exception("Query rewrite failed; searching the raw question only")
    return queries


def _ranked_lists(queries: List[str], top_k: int, hybrid: bool) -> List[List[Dict]]:
    """One ranked hit list per (query × search mode). Either mode may fail or be
    empty — the other still contributes."""
    lists: List[List[Dict]] = []
    for q in queries:
        try:
            lists.append(store.query(embeddings.embed_query(q), top_k))
        except Exception:
            log.exception("Vector search failed for %r", q)
        if hybrid:
            try:
                lists.append(keyword.search(q, top_k))
            except Exception:
                log.exception("Keyword search failed for %r", q)
    return lists


def _fuse(ranked_lists: List[List[Dict]], rrf_k: int) -> List[Dict]:
    """Reciprocal-rank fusion: chunks ranked well by several lists win."""
    fused: Dict[str, Dict] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits):
            cid = hit.get("id") or hit["text"][:80]
            entry = fused.setdefault(cid, {"hit": hit, "score": 0.0})
            entry["score"] += 1.0 / (rrf_k + rank + 1)
    return [{"text": e["hit"]["text"], "metadata": e["hit"]["metadata"],
             "score": e["score"]} for e in fused.values()]


def retrieve(question: str, history: Optional[List[Dict]] = None) -> List[Dict]:
    cfg = config.CFG["rag"]
    queries = _search_queries(question, history)
    ranked = _ranked_lists(queries, cfg["top_k_fetch"], cfg["hybrid"])
    hits = _fuse(ranked, cfg["rrf_k"])
    if not hits:
        return []

    try:
        known = keyword.known_contacts() if cfg["hybrid"] else []
    except Exception:
        known = []
    hints = query_analysis.analyze(question, known)

    now = time.time()
    for h in hits:
        meta = h["metadata"]
        boost = 1 + cfg["recency_boost"] * _recency_factor(meta.get("end_ts", 0), now)
        if hints.contacts and meta.get("contact") in hints.contacts:
            boost *= 1 + cfg["contact_boost"]
        if hints.date_range:
            start, end = hints.date_range
            if start <= meta.get("end_ts", 0) <= end:
                boost *= 1 + cfg["date_boost"]
        h["score"] *= boost
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[: cfg["top_k_use"]]


def _label(meta: Dict) -> str:
    name = SOURCE_NAMES.get(meta.get("source_type"), "From")
    when = datetime.fromtimestamp(meta.get("start_ts", 0)).strftime("%d %b %Y")
    return f"{name} {meta.get('contact', '?')}, {when}"


def format_context(hits: List[Dict]) -> str:
    """Numbered excerpts; the numbers let the model cite sources as [1], [2]…"""
    blocks = []
    for n, h in enumerate(hits, 1):
        blocks.append(f"[{n}] {_label(h['metadata'])}\n{h['text']}")
    return "\n\n".join(blocks)


def sources(hits: List[Dict]) -> List[Dict]:
    """What the UI shows under the answer, in the same order as the [n] markers.
    `type` lets the UI link call sources to their transcript."""
    return [{"n": n, "label": _label(h["metadata"]),
             "file": h["metadata"].get("source_file", ""),
             "type": h["metadata"].get("source_type", "")}
            for n, h in enumerate(hits, 1)]
