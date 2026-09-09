"""Persistent chat history (SQLite) with multiple named conversations.

The conversation(s) survive restarts. One connection per call: calls come from
FastAPI worker threads and the volume (a few rows per turn) makes pooling
pointless. `conv_id=None` everywhere means "the current conversation" — the most
recently used one, created on demand — so callers that don't care about naming
(and the older tests) keep working unchanged.
"""
import sqlite3
from time import time
from typing import Dict, List, Optional

from .. import config

DEFAULT_TITLE = "New chat"


def _connect() -> sqlite3.Connection:
    config.CHAT_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.CHAT_DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS conversations ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " title TEXT,"
        " created REAL NOT NULL,"
        " updated REAL NOT NULL)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " conv_id INTEGER,"
        " ts REAL NOT NULL,"
        " role TEXT NOT NULL,"
        " content TEXT NOT NULL)"
    )
    _migrate(con)
    return con


def _migrate(con: sqlite3.Connection) -> None:
    """Upgrade a flat (pre-conversations) messages table in place: add the
    conv_id column and adopt any orphaned rows into one 'Earlier chat'."""
    cols = [r[1] for r in con.execute("PRAGMA table_info(messages)")]
    if "conv_id" not in cols:
        con.execute("ALTER TABLE messages ADD COLUMN conv_id INTEGER")
    orphans = con.execute(
        "SELECT COUNT(*) FROM messages WHERE conv_id IS NULL").fetchone()[0]
    if orphans:
        cid = _new_conversation(con, "Earlier chat")
        con.execute("UPDATE messages SET conv_id=? WHERE conv_id IS NULL", (cid,))


def _new_conversation(con: sqlite3.Connection, title: str) -> int:
    now = time()
    cur = con.execute(
        "INSERT INTO conversations (title, created, updated) VALUES (?, ?, ?)",
        (title, now, now))
    return cur.lastrowid


def _current_id(con: sqlite3.Connection) -> int:
    row = con.execute(
        "SELECT id FROM conversations ORDER BY updated DESC LIMIT 1").fetchone()
    return row[0] if row else _new_conversation(con, DEFAULT_TITLE)


def create_conversation(title: str = DEFAULT_TITLE) -> int:
    with _connect() as con:
        return _new_conversation(con, title)


def list_conversations() -> List[Dict]:
    """Every conversation, most-recently-used first, with its message count."""
    with _connect() as con:
        rows = con.execute(
            "SELECT c.id, c.title, c.updated, COUNT(m.id) "
            "FROM conversations c LEFT JOIN messages m ON m.conv_id = c.id "
            "GROUP BY c.id ORDER BY c.updated DESC").fetchall()
    return [{"id": i, "title": t or DEFAULT_TITLE, "updated": u, "count": n}
            for i, t, u, n in rows]


def rename(conv_id: int, title: str) -> None:
    with _connect() as con:
        con.execute("UPDATE conversations SET title=? WHERE id=?",
                    (title.strip() or DEFAULT_TITLE, conv_id))


def delete_conversation(conv_id: int) -> None:
    with _connect() as con:
        con.execute("DELETE FROM messages WHERE conv_id=?", (conv_id,))
        con.execute("DELETE FROM conversations WHERE id=?", (conv_id,))


def append(role: str, content: str, conv_id: Optional[int] = None) -> int:
    """Store one message; returns the conversation id it landed in. The first
    user message auto-titles an untitled conversation."""
    with _connect() as con:
        if conv_id is None:
            conv_id = _current_id(con)
        now = time()
        con.execute(
            "INSERT INTO messages (conv_id, ts, role, content) VALUES (?, ?, ?, ?)",
            (conv_id, now, role, content))
        con.execute("UPDATE conversations SET updated=? WHERE id=?", (now, conv_id))
        if role == "user":
            row = con.execute(
                "SELECT title FROM conversations WHERE id=?", (conv_id,)).fetchone()
            if row and (not row[0] or row[0] == DEFAULT_TITLE):
                title = " ".join(content.split())[:40] or DEFAULT_TITLE
                con.execute("UPDATE conversations SET title=? WHERE id=?",
                            (title, conv_id))
    return conv_id


def recent(limit: int = 40, conv_id: Optional[int] = None) -> List[Dict]:
    """Last `limit` messages of one conversation, chronological."""
    with _connect() as con:
        if conv_id is None:
            conv_id = _current_id(con)
        rows = con.execute(
            "SELECT role, content FROM messages WHERE conv_id=? "
            "ORDER BY id DESC LIMIT ?", (conv_id, limit)).fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]


def clear() -> None:
    """Wipe all history (every conversation)."""
    with _connect() as con:
        con.execute("DELETE FROM messages")
        con.execute("DELETE FROM conversations")
