"""Batch photo captioning with a local vision model via Ollama.

Resumable by design: each caption commits caption_done per photo, and every
EMBED_BATCH captions get embedded (CPU) and pushed to Chroma immediately, so
closing the app mid-way through a 10k-photo library loses almost nothing.
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .. import config
from ..graph import store as graph_store
from ..llm import ollama_client, prompts
from . import photos as photos_mod

EMBED_BATCH = 32


def _photo_chunk(row) -> dict:
    """Render one captioned photo as a Chroma chunk (source_type 'photo')."""
    import hashlib
    import json
    people = json.loads(row["people_json"])
    when = datetime.fromtimestamp(row["taken_ts"]).strftime("%d %b %Y") if row["taken_ts"] else ""
    bits = ["Photo", when]
    if row["place_label"]:
        bits.append(row["place_label"])
    header = ", ".join(b for b in bits if b)
    if people:
        header += f" (with {', '.join(people)})"
    return {
        "id": hashlib.sha1(f"photo|{row['photo_id']}".encode()).hexdigest(),
        "text": f"{header}: {row['caption']}",
        "metadata": {
            "source_type": "photo",
            "contact": people[0] if people else "",
            "photo_id": row["photo_id"],
            "source_file": row["rel_path"],
            "start_ts": row["taken_ts"] or 0,
            "end_ts": row["taken_ts"] or 0,
            "chunk_index": 0,
        },
    }


def embed_pending(status: Callable[[str], None]) -> int:
    """Embed all captioned-but-unembedded photos into Chroma (CPU)."""
    rows = graph_store.pending_embeds()
    if not rows:
        return 0
    from ..rag import embeddings
    from ..rag import store as rag_store
    for i in range(0, len(rows), EMBED_BATCH):
        part = rows[i:i + EMBED_BATCH]
        chunks = [_photo_chunk(r) for r in part]
        embs = embeddings.embed_texts([c["text"] for c in chunks])
        rag_store.upsert_chunks(chunks, embs)
        for r in part:
            graph_store.mark(r["photo_id"], "embedded", 1)
    status(f"Indexed {len(rows)} photo descriptions for search.")
    return len(rows)


def run_captions(status: Callable[[str], None]) -> int:
    """Caption every pending photo. Returns the number captioned this run."""
    cfg = config.CFG["photos"]
    if not cfg.get("captions", True):
        return 0
    rows = graph_store.pending_captions()
    if not rows:
        return 0
    model = cfg["caption_model"]
    status(f"Describing {len(rows)} photos with the vision AI ({model})…")
    done = 0
    t0 = time.time()
    import json
    for row in rows:
        path = config.INGEST_PHOTOS / row["rel_path"]
        if not path.exists():
            graph_store.mark(row["photo_id"], "caption_done", -1, "file missing")
            continue
        b64 = photos_mod.downscaled_jpeg_b64(path)
        if not b64:
            graph_store.mark(row["photo_id"], "caption_done", -1, "unreadable image")
            continue
        people = json.loads(row["people_json"])
        hint = f" People in this photo: {', '.join(people)}." if people else ""
        caption = ollama_client.caption(
            b64, prompts.CAPTION_PROMPT + hint, model=model
        )
        if caption:
            graph_store.set_caption(row["photo_id"], caption.strip()[:500])
            done += 1
        else:
            graph_store.mark(row["photo_id"], "caption_done", -1, "caption failed")
        if done and done % 10 == 0:
            rate = (time.time() - t0) / done
            remaining = (len(rows) - done) * rate
            hrs = remaining / 3600
            eta = f"~{hrs:.1f} h" if hrs >= 1 else f"~{remaining / 60:.0f} min"
            status(f"Described {done}/{len(rows)} photos — {eta} remaining. "
                   "(You can close Manu anytime; it continues next run.)")
        if done and done % EMBED_BATCH == 0:
            embed_pending(status)
    embed_pending(status)
    ollama_client.unload(model)
    return done
