"""Parser for Telegram Desktop's JSON chat export (result.json).

Telegram → Settings → Advanced → Export Telegram data → JSON. A full export
has {"chats": {"list": [...]}}; exporting a single chat gives one chat object
directly. Both shapes are handled.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List

from .models import Message


def _flatten_text(text) -> str:
    """Telegram encodes formatting as a list of strings and entity dicts."""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        parts = []
        for piece in text:
            if isinstance(piece, str):
                parts.append(piece)
            elif isinstance(piece, dict):
                parts.append(str(piece.get("text", "")))
        return "".join(parts)
    return ""


def _parse_chat(chat: dict, source_file: str) -> List[Message]:
    contact = str(chat.get("name") or "Unknown chat")
    messages: List[Message] = []
    for msg in chat.get("messages", []):
        if msg.get("type") != "message":
            continue  # service events: calls started, pins, member joins…
        text = _flatten_text(msg.get("text")).strip()
        if not text:
            continue  # media without caption
        try:
            ts = datetime.fromisoformat(msg["date"])
        except (KeyError, ValueError, TypeError):
            continue
        messages.append(Message(
            timestamp=ts,
            sender=str(msg.get("from") or "Unknown"),
            text=text,
            contact=contact,
            source_type="telegram",
            source_file=source_file,
        ))
    return messages


def parse_telegram(path: Path) -> List[Message]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "chats" in data:  # full-account export
        chats = data["chats"].get("list", [])
    elif "messages" in data:  # single-chat export
        chats = [data]
    else:
        return []
    messages: List[Message] = []
    for chat in chats:
        # saved_messages has no name; personal/group chats do
        if chat.get("type") == "saved_messages":
            continue
        messages.extend(_parse_chat(chat, path.name))
    messages.sort(key=lambda m: (m.contact, m.timestamp))
    return messages
