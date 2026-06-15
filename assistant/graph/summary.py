"""AI relationship summary for a person, generated on demand and cached in
nodes.attrs (not during ingest — keeps ingest time bounded)."""
import json
import time
from typing import Optional

from ..llm import ollama_client
from . import store

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}

SYSTEM = (
    "You write a short, warm summary (4-6 sentences, English) of the user's "
    "relationship with one person, based on conversation stats, recent chats and "
    "shared photos. Mention how they know each other, what they usually talk "
    "about, and anything notable. Do not invent details."
)


def generate(person_id: str) -> Optional[str]:
    payload = store.person_payload(person_id)
    if not payload:
        return None
    parts = [
        f"Person: {payload['name']}",
        f"Conversations: {payload['session_count']} "
        f"({payload['message_count']} messages)",
    ]
    for s in payload["recent_sessions"][:5]:
        parts.append(f"- {s['source_type']} session, {s['msg_count']} messages")
    captions = [p["caption"] for p in payload["photos"] if p.get("caption")][:8]
    if captions:
        parts.append("Shared photos: " + " | ".join(captions))
    # Pull a few retrieved conversation excerpts for grounding
    try:
        from ..rag import retriever
        hits = retriever.retrieve(f"conversations with {payload['name']}")
        for h in hits[:3]:
            parts.append("Excerpt: " + h["text"][:500])
    except Exception:
        pass
    result = ollama_client.extract("\n".join(parts), SUMMARY_SCHEMA, system=SYSTEM)
    if not result or not result.get("summary"):
        return None
    summary = result["summary"].strip()
    db = store.get_db()
    row = db.execute("SELECT attrs FROM nodes WHERE id=?", (person_id,)).fetchone()
    if row:
        attrs = json.loads(row["attrs"])
        attrs["summary"] = summary
        attrs["summary_ts"] = time.time()
        db.execute("UPDATE nodes SET attrs=? WHERE id=?", (json.dumps(attrs), person_id))
        db.commit()
    return summary
