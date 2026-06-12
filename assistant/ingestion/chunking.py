"""Conversation-aware chunking shared by all sources.

Messages are grouped into sessions (a long silence starts a new session), then
packed into ~1800-char chunks without ever splitting a message. Each chunk's
embedded text starts with a header ("WhatsApp chat with Aai, 13 May 2024:")
because that context materially improves multilingual retrieval.
"""
import hashlib
from datetime import datetime
from typing import Dict, List

from .models import Message

SOURCE_LABELS = {"whatsapp": "WhatsApp chat with", "sms": "SMS with", "call": "Phone call with"}


def sessionize(messages: List[Message], gap_hours: float = 3.0) -> List[List[Message]]:
    """Split one contact's chronologically-sorted messages on long gaps."""
    sessions: List[List[Message]] = []
    current: List[Message] = []
    for msg in messages:
        if current and (msg.timestamp - current[-1].timestamp).total_seconds() > gap_hours * 3600:
            sessions.append(current)
            current = []
        current.append(msg)
    if current:
        sessions.append(current)
    return sessions


def _fmt_date(ts: datetime) -> str:
    return ts.strftime("%d %b %Y")


def _header(session: List[Message]) -> str:
    first, last = session[0], session[-1]
    label = SOURCE_LABELS.get(first.source_type, "Conversation with")
    date_range = _fmt_date(first.timestamp)
    if _fmt_date(last.timestamp) != date_range:
        date_range += f" – {_fmt_date(last.timestamp)}"
    return f"{label} {first.contact}, {date_range}:"


def _chunk_id(source_file: str, chunk_index: int, start_ts: datetime) -> str:
    raw = f"{source_file}|{chunk_index}|{start_ts.isoformat()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_chunks(session: List[Message], chunk_chars: int = 1800,
                 overlap_messages: int = 2) -> List[Dict]:
    """Pack a session's messages into chunks of dicts ready for the vector store."""
    if not session:
        return []
    header = _header(session)
    chunks: List[Dict] = []
    i = 0
    chunk_index = 0
    while i < len(session):
        lines: List[str] = []
        size = len(header)
        j = i
        while j < len(session):
            line = f"{session[j].sender}: {session[j].text}"
            if lines and size + len(line) > chunk_chars:
                break
            lines.append(line)
            size += len(line) + 1
            j += 1
        part = session[i:j]
        text = header + "\n" + "\n".join(lines)
        first = part[0]
        chunks.append({
            "id": _chunk_id(first.source_file, chunk_index, first.timestamp),
            "text": text,
            "metadata": {
                "source_type": first.source_type,
                "contact": first.contact,
                "source_file": first.source_file,
                "start_ts": part[0].timestamp.timestamp(),
                "end_ts": part[-1].timestamp.timestamp(),
                "chunk_index": chunk_index,
            },
        })
        chunk_index += 1
        if j >= len(session):
            break
        # Step back a couple of messages so context carries across chunk borders
        i = max(j - overlap_messages, i + 1)
    return chunks


def messages_to_chunks(messages: List[Message], chunk_chars: int = 1800,
                       overlap_messages: int = 2, gap_hours: float = 3.0) -> List[Dict]:
    """Group a flat message list by contact, sessionize, and chunk everything."""
    by_contact: Dict[str, List[Message]] = {}
    for m in messages:
        by_contact.setdefault(m.contact, []).append(m)
    chunks: List[Dict] = []
    for contact_msgs in by_contact.values():
        contact_msgs.sort(key=lambda m: m.timestamp)
        for session in sessionize(contact_msgs, gap_hours):
            chunks.extend(build_chunks(session, chunk_chars, overlap_messages))
    return chunks
