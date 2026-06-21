"""Content-hash dedupe cache for viral forwards.

The same WhatsApp message checked by thousands of people should be verified
once and served from cache afterwards — instant for the user, cheap for us.
Keyed by a SHA-256 of the normalised content; rows expire after a TTL.
"""
import hashlib
import json
import sqlite3
import time
from typing import Optional

from . import config

_TTL_SECONDS = config.CACHE_TTL_HOURS * 3600


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.CACHE_DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS verdicts (
               key TEXT PRIMARY KEY,
               result TEXT NOT NULL,
               created_at REAL NOT NULL
           )"""
    )
    return conn


def make_key(kind: str, payload: bytes) -> str:
    """Stable cache key for a check of a given kind (text/image/url)."""
    h = hashlib.sha256()
    h.update(kind.encode("utf-8"))
    h.update(b"\x00")
    h.update(payload)
    return h.hexdigest()


def normalise_text(text: str) -> bytes:
    """Collapse whitespace and lowercase so trivial edits still hit cache."""
    return " ".join(text.lower().split()).encode("utf-8")


def get(key: str) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT result, created_at FROM verdicts WHERE key = ?", (key,)
        ).fetchone()
        if not row:
            return None
        result_json, created_at = row
        if time.time() - created_at > _TTL_SECONDS:
            conn.execute("DELETE FROM verdicts WHERE key = ?", (key,))
            conn.commit()
            return None
        return json.loads(result_json)
    finally:
        conn.close()


def put(key: str, result: dict) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO verdicts (key, result, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(result, ensure_ascii=False), time.time()),
        )
        conn.commit()
    finally:
        conn.close()
