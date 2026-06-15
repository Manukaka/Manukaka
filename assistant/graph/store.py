"""SQLite life-graph store: photos (with ingest-resume flags), nodes, edges,
photo↔people links, and conversation sessions (the timeline backbone)."""
import hashlib
import json
import re
import sqlite3
import threading
from typing import Dict, List, Optional

from .. import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
  photo_id    TEXT PRIMARY KEY,
  rel_path    TEXT UNIQUE,
  file_size   INTEGER,
  mtime       REAL,
  taken_ts    REAL,
  lat REAL, lon REAL,
  place_name TEXT, place_admin TEXT, place_cc TEXT, place_label TEXT,
  people_json TEXT DEFAULT '[]',
  caption     TEXT,
  width INTEGER, height INTEGER,
  thumb_done   INTEGER DEFAULT 0,
  caption_done INTEGER DEFAULT 0,
  embedded     INTEGER DEFAULT 0,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_photos_taken ON photos(taken_ts);
CREATE INDEX IF NOT EXISTS idx_photos_caption ON photos(caption_done);

CREATE TABLE IF NOT EXISTS nodes (
  id TEXT PRIMARY KEY,
  type TEXT,
  name TEXT,
  norm_name TEXT,
  attrs TEXT DEFAULT '{}',
  UNIQUE(type, norm_name)
);
CREATE TABLE IF NOT EXISTS edges (
  src TEXT, dst TEXT, type TEXT,
  weight REAL DEFAULT 1,
  attrs TEXT DEFAULT '{}',
  PRIMARY KEY (src, dst, type)
);
CREATE TABLE IF NOT EXISTS photo_people (
  photo_id TEXT, person_id TEXT,
  PRIMARY KEY (photo_id, person_id)
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  source_type TEXT, contact TEXT,
  start_ts REAL, end_ts REAL, msg_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_ts);
"""


def get_db() -> sqlite3.Connection:
    db = getattr(_local, "db", None)
    if db is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(config.GRAPH_DB))
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA)
        _local.db = db
    return db


def norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def node_id(type_: str, name: str) -> str:
    return hashlib.sha1(f"{type_}|{norm_name(name)}".encode("utf-8")).hexdigest()[:16]


def photo_id_for(rel_path: str) -> str:
    return hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------- nodes/edges

def upsert_node(type_: str, name: str, attrs_update: Optional[Dict] = None) -> str:
    db = get_db()
    nid = node_id(type_, name)
    row = db.execute("SELECT attrs FROM nodes WHERE id=?", (nid,)).fetchone()
    attrs = json.loads(row["attrs"]) if row else {}
    if attrs_update:
        attrs.update(attrs_update)
    db.execute(
        "INSERT INTO nodes(id, type, name, norm_name, attrs) VALUES(?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET attrs=excluded.attrs",
        (nid, type_, name.strip(), norm_name(name), json.dumps(attrs)),
    )
    db.commit()
    return nid


def set_edge(src: str, dst: str, type_: str, weight: float) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO edges(src, dst, type, weight) VALUES(?,?,?,?) "
        "ON CONFLICT(src, dst, type) DO UPDATE SET weight=excluded.weight",
        (src, dst, type_, weight),
    )
    db.commit()


def bump_edge(src: str, dst: str, type_: str, delta: float = 1.0) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO edges(src, dst, type, weight) VALUES(?,?,?,?) "
        "ON CONFLICT(src, dst, type) DO UPDATE SET weight=weight+?",
        (src, dst, type_, delta, delta),
    )
    db.commit()


# ------------------------------------------------------------------- photos

def upsert_photo(rec, place: Optional[Dict] = None) -> str:
    """Insert/update a photo row from a photos.PhotoRecord. Preserves resume flags."""
    db = get_db()
    pid = photo_id_for(rec.rel_path)
    place = place or {}
    db.execute(
        """INSERT INTO photos(photo_id, rel_path, file_size, mtime, taken_ts, lat, lon,
             place_name, place_admin, place_cc, place_label, people_json, width, height)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(photo_id) DO UPDATE SET
             file_size=excluded.file_size, mtime=excluded.mtime,
             taken_ts=excluded.taken_ts, lat=excluded.lat, lon=excluded.lon,
             place_name=excluded.place_name, place_admin=excluded.place_admin,
             place_cc=excluded.place_cc, place_label=excluded.place_label,
             people_json=excluded.people_json, width=excluded.width, height=excluded.height""",
        (pid, rec.rel_path, rec.file_size, rec.mtime, rec.taken_ts, rec.lat, rec.lon,
         place.get("name"), place.get("admin"), place.get("cc"), place.get("label"),
         json.dumps(rec.people, ensure_ascii=False), rec.width, rec.height),
    )
    db.commit()
    return pid


def photo_is_known(rel_path: str, file_size: int, mtime: float) -> bool:
    db = get_db()
    row = db.execute(
        "SELECT file_size, mtime FROM photos WHERE rel_path=?", (rel_path,)
    ).fetchone()
    return bool(row and row["file_size"] == file_size and abs(row["mtime"] - mtime) < 1)


def link_photo_person(photo_id: str, person_id: str) -> None:
    db = get_db()
    db.execute("INSERT OR IGNORE INTO photo_people VALUES(?,?)", (photo_id, person_id))
    db.commit()


def mark(photo_id: str, column: str, value: int = 1, error: Optional[str] = None) -> None:
    assert column in ("thumb_done", "caption_done", "embedded")
    db = get_db()
    db.execute(f"UPDATE photos SET {column}=?, error=? WHERE photo_id=?",
               (value, error, photo_id))
    db.commit()


def set_caption(photo_id: str, caption: str) -> None:
    db = get_db()
    db.execute("UPDATE photos SET caption=?, caption_done=1 WHERE photo_id=?",
               (caption, photo_id))
    db.commit()


def pending_captions(limit: Optional[int] = None) -> List[sqlite3.Row]:
    db = get_db()
    q = "SELECT * FROM photos WHERE caption_done=0 ORDER BY taken_ts DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    return db.execute(q).fetchall()


def pending_embeds() -> List[sqlite3.Row]:
    db = get_db()
    return db.execute(
        "SELECT * FROM photos WHERE caption_done=1 AND embedded=0").fetchall()


def get_photo(photo_id: str) -> Optional[sqlite3.Row]:
    return get_db().execute(
        "SELECT * FROM photos WHERE photo_id=?", (photo_id,)).fetchone()


# ------------------------------------------------------------------- sessions

def upsert_session(source_type: str, contact: str, start_ts: float,
                   end_ts: float, msg_count: int, source_file: str) -> str:
    db = get_db()
    sid = hashlib.sha1(f"{source_file}|{contact}|{start_ts}".encode()).hexdigest()[:16]
    db.execute(
        "INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?)",
        (sid, source_type, contact, start_ts, end_ts, msg_count),
    )
    db.commit()
    return sid


# ------------------------------------------------------------------- queries

def graph_payload() -> Dict:
    """Node/link lists shaped for force-graph / 3d-force-graph."""
    db = get_db()
    photo_counts: Dict[str, int] = {}
    for r in db.execute("SELECT person_id, COUNT(*) c FROM photo_people GROUP BY person_id"):
        photo_counts[r["person_id"]] = r["c"]
    nodes = []
    for r in db.execute("SELECT * FROM nodes"):
        attrs = json.loads(r["attrs"])
        nodes.append({
            "id": r["id"], "type": r["type"], "name": r["name"],
            "msg_count": attrs.get("msg_count", 0),
            "photo_count": photo_counts.get(r["id"], 0),
            "val": max(1, (attrs.get("msg_count", 0) ** 0.5)
                       + photo_counts.get(r["id"], 0) ** 0.5),
        })
    node_ids = {n["id"] for n in nodes}
    links = [
        {"source": r["src"], "target": r["dst"], "type": r["type"], "weight": r["weight"]}
        for r in db.execute("SELECT * FROM edges")
        if r["src"] in node_ids and r["dst"] in node_ids
    ]
    return {"nodes": nodes, "links": links}


def timeline(before_ts: Optional[float], limit: int) -> List[Dict]:
    db = get_db()
    before = before_ts if before_ts else 9e12
    items: List[Dict] = []
    for r in db.execute(
        "SELECT * FROM photos WHERE taken_ts < ? ORDER BY taken_ts DESC LIMIT ?",
        (before, limit),
    ):
        people = json.loads(r["people_json"])
        sub = r["caption"] or (("With " + ", ".join(people)) if people else "")
        items.append({
            "type": "photo", "ts": r["taken_ts"],
            "title": "Photo" + (f" — {r['place_label']}" if r["place_label"] else ""),
            "subtitle": sub, "photo_id": r["photo_id"],
            "thumb": f"/api/thumb/{r['photo_id']}",
        })
    for r in db.execute(
        "SELECT * FROM sessions WHERE start_ts < ? ORDER BY start_ts DESC LIMIT ?",
        (before, limit),
    ):
        kind = "call" if r["source_type"] == "call" else "chat"
        items.append({
            "type": kind, "ts": r["start_ts"],
            "title": ("Call with " if kind == "call" else "Chat with ") + r["contact"],
            "subtitle": f"{r['msg_count']} messages" if kind == "chat" else "",
            "contact": r["contact"], "msg_count": r["msg_count"],
        })
    items.sort(key=lambda x: x["ts"] or 0, reverse=True)
    return items[:limit]


def person_payload(person_id: str) -> Optional[Dict]:
    db = get_db()
    node = db.execute("SELECT * FROM nodes WHERE id=?", (person_id,)).fetchone()
    if not node:
        return None
    attrs = json.loads(node["attrs"])
    photos = [
        {"photo_id": r["photo_id"], "thumb": f"/api/thumb/{r['photo_id']}",
         "ts": r["taken_ts"], "caption": r["caption"], "place": r["place_label"]}
        for r in db.execute(
            """SELECT p.* FROM photos p JOIN photo_people pp ON p.photo_id=pp.photo_id
               WHERE pp.person_id=? ORDER BY p.taken_ts DESC LIMIT 60""", (person_id,))
    ]
    sessions = [
        dict(r) for r in db.execute(
            "SELECT * FROM sessions WHERE contact=? ORDER BY start_ts DESC LIMIT 10",
            (node["name"],))
    ]
    stats = db.execute(
        "SELECT COUNT(*) n, SUM(msg_count) m FROM sessions WHERE contact=?",
        (node["name"],)).fetchone()
    return {
        "id": node["id"], "type": node["type"], "name": node["name"],
        "relation": attrs.get("relation", ""),
        "summary": attrs.get("summary", ""),
        "session_count": stats["n"] or 0,
        "message_count": stats["m"] or 0,
        "photos": photos, "recent_sessions": sessions,
    }


def people_list() -> List[Dict]:
    db = get_db()
    out = []
    for r in db.execute("SELECT * FROM nodes WHERE type='person' AND norm_name != 'me'"):
        attrs = json.loads(r["attrs"])
        pc = db.execute("SELECT COUNT(*) c FROM photo_people WHERE person_id=?",
                        (r["id"],)).fetchone()["c"]
        out.append({"id": r["id"], "name": r["name"],
                    "msg_count": attrs.get("msg_count", 0), "photo_count": pc})
    out.sort(key=lambda p: (p["msg_count"], p["photo_count"]), reverse=True)
    return out


def places_payload() -> List[Dict]:
    db = get_db()
    out = []
    for r in db.execute(
        """SELECT place_label, AVG(lat) lat, AVG(lon) lon, COUNT(*) c,
                  MIN(taken_ts) first_ts, MAX(taken_ts) last_ts
           FROM photos WHERE lat IS NOT NULL AND place_label IS NOT NULL
           GROUP BY place_label"""
    ):
        ids = [row["photo_id"] for row in db.execute(
            "SELECT photo_id FROM photos WHERE place_label=? ORDER BY taken_ts DESC LIMIT 24",
            (r["place_label"],))]
        out.append({"name": r["place_label"], "lat": r["lat"], "lon": r["lon"],
                    "count": r["c"], "first_ts": r["first_ts"], "last_ts": r["last_ts"],
                    "photo_ids": ids})
    out.sort(key=lambda p: p["count"], reverse=True)
    return out


def contacts() -> List[str]:
    db = get_db()
    return [r["name"] for r in db.execute(
        "SELECT name FROM nodes WHERE type='person' AND norm_name != 'me'")]


def close() -> None:
    db = getattr(_local, "db", None)
    if db is not None:
        db.close()
        _local.db = None
