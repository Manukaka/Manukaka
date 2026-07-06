"""Persistent chat history (SQLite) — the conversation survives restarts.

One connection per call: calls come from FastAPI worker threads and the
volume (a few rows per chat turn) makes pooling pointless.
"""
import sqlite3
from time import time
from typing import Dict, List

from .. import config


def _connect() -> sqlite3.Connection:
    config.CHAT_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.CHAT_DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts REAL NOT NULL,"
        " role TEXT NOT NULL,"
        " content TEXT NOT NULL)"
    )
    return con


def append(role: str, content: str) -> None:
    with _connect() as con:
        con.execute("INSERT INTO messages (ts, role, content) VALUES (?, ?, ?)",
                    (time(), role, content))


def recent(limit: int = 40) -> List[Dict]:
    """Last `limit` messages in chronological order."""
    with _connect() as con:
        rows = con.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]


def clear() -> None:
    with _connect() as con:
        con.execute("DELETE FROM messages")
