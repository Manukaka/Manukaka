"""Builders that turn ingested data into life-graph nodes and edges.

Deterministic parts (contacts, message volume, photo people, places) are pure
CPU and rerun-safe; LLM-extracted events/topics arrive via add_extracted().
"""
from collections import Counter
from typing import Dict, List

from ..ingestion.models import Message
from ..ingestion import photos as photos_mod
from . import store


def me_id() -> str:
    return store.upsert_node("person", "Me")


def add_sessions_and_people(sessions: List[List[Message]]) -> None:
    """Person nodes + talks_with edges + sessions rows from chunked sessions."""
    me = me_id()
    msg_counts: Counter = Counter()
    for sess in sessions:
        if not sess:
            continue
        first, last = sess[0], sess[-1]
        store.upsert_session(
            first.source_type, first.contact,
            first.timestamp.timestamp(), last.timestamp.timestamp(),
            len(sess), first.source_file,
        )
        msg_counts[first.contact] += len(sess)
    for contact, count in msg_counts.items():
        pid = store.upsert_node("person", contact)
        # accumulate msg_count in node attrs
        from .store import get_db
        import json
        row = get_db().execute("SELECT attrs FROM nodes WHERE id=?", (pid,)).fetchone()
        attrs = json.loads(row["attrs"]) if row else {}
        attrs["msg_count"] = attrs.get("msg_count", 0) + count
        store.upsert_node("person", contact, attrs)
        store.bump_edge(me, pid, "talks_with", float(count))


def add_photo_links(photo_id: str, people_tags: List[str], place_label: str) -> None:
    """photographed_with + was_at edges for one photo, fuzzy-matching tags to contacts."""
    me = me_id()
    known = store.contacts()
    person_ids = []
    for tag in people_tags:
        matched = photos_mod.match_person(tag, known)
        name = matched or tag  # unknown tagged people still become graph nodes
        pid = store.upsert_node("person", name)
        person_ids.append(pid)
        store.link_photo_person(photo_id, pid)
        store.bump_edge(me, pid, "photographed_with", 1.0)
    # co-occurrence between tagged people
    for i, a in enumerate(person_ids):
        for b in person_ids[i + 1:]:
            store.bump_edge(a, b, "photographed_with", 1.0)
    if place_label:
        place_id = store.upsert_node("place", place_label)
        for pid in person_ids or [me]:
            store.bump_edge(pid, place_id, "was_at", 1.0)


def add_extracted(extraction: Dict, contact: str) -> None:
    """Events/topics from the LLM extraction pass → event/topic nodes + discussed edges."""
    if not extraction:
        return
    me = me_id()
    contact_id = store.upsert_node("person", contact) if contact else me
    for ev in extraction.get("events", []) or []:
        name = ev.get("name") if isinstance(ev, dict) else str(ev)
        if not name:
            continue
        eid = store.upsert_node("event", name, {"where": (ev.get("where") if isinstance(ev, dict) else "") or "",
                                                "when": (ev.get("when") if isinstance(ev, dict) else "") or ""})
        store.bump_edge(contact_id, eid, "discussed", 1.0)
        store.bump_edge(me, eid, "discussed", 1.0)
        if isinstance(ev, dict):
            for who in ev.get("with_whom", []) or []:
                if who and store.norm_name(who) != "me":
                    wid = store.upsert_node("person", who)
                    store.bump_edge(wid, eid, "discussed", 1.0)
    for topic in extraction.get("topics", []) or []:
        if not topic or len(str(topic)) > 60:
            continue
        tid = store.upsert_node("topic", str(topic))
        store.bump_edge(contact_id, tid, "discussed", 1.0)


def backfill_from_chroma(status=print) -> int:
    """One-time reconstruction of sessions/person nodes from v1 Chroma metadata,
    so users who ingested before v2 see their data in the graph and timeline.
    Chunk overlap makes session boundaries approximate — fine for a timeline."""
    from .store import get_db
    db = get_db()
    if db.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"] > 0:
        return 0
    try:
        from ..rag import store as rag_store
        col = rag_store._get_collection()
        if col.count() == 0:
            return 0
        res = col.get(include=["metadatas"])
    except Exception:
        return 0
    # Group chunks by (source_file, contact, day-of-start) ≈ one session
    groups: Dict[tuple, Dict] = {}
    for meta in res["metadatas"]:
        if meta.get("source_type") == "photo":
            continue
        key = (meta.get("source_file", ""), meta.get("contact", ""),
               int(meta.get("start_ts", 0) // 86400))
        g = groups.setdefault(key, {"meta": meta, "start": meta.get("start_ts", 0),
                                    "end": meta.get("end_ts", 0), "chunks": 0})
        g["start"] = min(g["start"], meta.get("start_ts", 0))
        g["end"] = max(g["end"], meta.get("end_ts", 0))
        g["chunks"] += 1
    me = me_id()
    counts: Counter = Counter()
    for (source_file, contact, _day), g in groups.items():
        if not contact:
            continue
        est_msgs = g["chunks"] * 8  # rough: ~8 messages per chunk
        store.upsert_session(g["meta"].get("source_type", "whatsapp"), contact,
                             g["start"], g["end"], est_msgs, source_file)
        counts[contact] += est_msgs
    import json
    for contact, count in counts.items():
        pid = store.upsert_node("person", contact, {"msg_count": count})
        store.bump_edge(me, pid, "talks_with", float(count))
    status(f"Rebuilt {len(groups)} past conversations into the life-graph.")
    return len(groups)
