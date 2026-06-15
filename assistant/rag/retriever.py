"""Query flow: embed the question, fetch top-k, boost recent chunks, format context."""
import time
from datetime import datetime
from typing import Dict, List

from .. import config
from . import embeddings, store

SOURCE_NAMES = {"whatsapp": "WhatsApp with", "sms": "SMS with", "call": "Call with",
                "photo": "Photo with"}


def _recency_factor(end_ts: float, now: float) -> float:
    """1.0 for today, fading to 0.0 at ~one year old."""
    age_days = max(0.0, (now - end_ts) / 86400)
    return max(0.0, 1.0 - age_days / 365)


def retrieve(question: str) -> List[Dict]:
    cfg = config.CFG["rag"]
    emb = embeddings.embed_query(question)
    hits = store.query(emb, cfg["top_k_fetch"])
    now = time.time()
    boost = cfg["recency_boost"]
    for h in hits:
        end_ts = h["metadata"].get("end_ts", 0)
        h["score"] = h["similarity"] * (1 + boost * _recency_factor(end_ts, now))
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[: cfg["top_k_use"]]


def format_context(hits: List[Dict]) -> str:
    blocks = []
    for h in hits:
        meta = h["metadata"]
        label = SOURCE_NAMES.get(meta.get("source_type"), "From")
        when = datetime.fromtimestamp(meta.get("start_ts", 0)).strftime("%d %b %Y")
        contact = meta.get("contact") or ""
        who = f" {contact}" if contact else ""
        if not contact and label.endswith(" with"):
            label = label[:-5]
        blocks.append(f"[{label}{who}, {when}]\n{h['text']}")
    return "\n\n".join(blocks)
