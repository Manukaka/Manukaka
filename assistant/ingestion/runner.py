"""Ingestion orchestrator.

Phase order is the whole point on an 8GB GPU:
  0. Photos prep (CPU): extract Takeout zips, read metadata, geocode, thumbnails
  1. Unload the Ollama LLM (frees VRAM)
  2. Transcribe + diarize ALL new audio in one batch (whisper+pyannote on GPU)
  3. Free whisper/pyannote VRAM
  4. Parse text sources, chunk everything, embed on CPU, build the life-graph
  5a. Vision captions via Ollama (GPU is free again), embedding as it goes
  5b. Profile + graph extraction via the text LLM

A sha256 manifest makes re-running over the same drop folders a no-op for
audio/chat files; photo idempotency lives in the photos table (per-photo,
resumable — cheaper than hashing a 30GB library every run).
"""
import hashlib
import json
import traceback
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .. import config, geo
from ..graph import build as graph_build
from ..graph import store as graph_store
from ..llm import ollama_client
from ..memory import profile as memory_profile
from . import audio as audio_mod
from . import captions, chunking, photos as photos_mod, sms, whatsapp
from .models import Message

StatusCb = Callable[[str], None]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _load_manifest() -> Dict[str, str]:
    if config.MANIFEST_PATH.exists():
        return json.loads(config.MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _save_manifest(manifest: Dict[str, str]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _new_files(folder: Path, exts: Optional[set], manifest: Dict[str, str]) -> List[Path]:
    files = []
    for p in sorted(folder.iterdir()) if folder.exists() else []:
        if not p.is_file() or p.name == ".gitkeep":
            continue
        if exts and p.suffix.lower() not in exts:
            continue
        if _sha256(p) not in manifest:
            files.append(p)
    return files


def _prepare_photos(status: StatusCb, counters: Dict[str, int]) -> None:
    """Phase 0 (CPU): zips → metadata → geocode → thumbnails → graph links."""
    photos_mod.extract_takeout_zips(status)
    all_photos, videos = photos_mod.discover_photos()
    if videos:
        status(f"Skipped {videos} videos (not supported yet).")
    new = []
    for p in all_photos:
        stat = p.stat()
        rel = str(p.relative_to(config.INGEST_PHOTOS))
        if not graph_store.photo_is_known(rel, stat.st_size, stat.st_mtime):
            new.append(p)
    if not new:
        return
    status(f"Reading {len(new)} new photos (dates, places, people tags)…")

    records, coords = [], []
    sidecar_cache: Dict[Path, Dict] = {}
    for p in new:
        if p.parent not in sidecar_cache:
            sidecar_cache[p.parent] = photos_mod._index_sidecars(p.parent)
        try:
            rec = photos_mod.scan_photo(p, sidecar_cache[p.parent])
            records.append(rec)
            coords.append((rec.lat, rec.lon) if rec.lat is not None else None)
        except Exception:
            counters["errors"] += 1

    # Batch reverse-geocode every photo that has GPS
    have_gps = [c for c in coords if c]
    geo_results = iter(geo.lookup_many(have_gps))
    for i, (rec, c) in enumerate(zip(records, coords), 1):
        place = None
        if c:
            g = next(geo_results, None)
            if g:
                place = dict(g, label=geo.place_label(g["name"], g["admin"], g["country"]))
        pid = graph_store.upsert_photo(rec, place)
        src = config.INGEST_PHOTOS / rec.rel_path
        if photos_mod.make_thumbnail(src, pid):
            graph_store.mark(pid, "thumb_done", 1)
        graph_build.add_photo_links(pid, rec.people, (place or {}).get("label", ""))
        counters["photos"] += 1
        if i % 200 == 0:
            status(f"Prepared {i}/{len(records)} photos…")
    status(f"Added {counters['photos']} photos.")


def run_ingest(status: StatusCb = print) -> Dict[str, int]:
    """Process everything new in the ingest/ folders. Returns simple counters."""
    config.ensure_dirs()
    manifest = _load_manifest()
    counters = {"audio": 0, "whatsapp": 0, "sms": 0, "photos": 0,
                "captions": 0, "chunks": 0, "errors": 0}
    all_messages: List[Message] = []
    sessions_for_profile: List[tuple] = []  # (source_label, text, contact)

    # One-time: rebuild graph/timeline from v1 data ingested before this version
    try:
        graph_build.backfill_from_chroma(status)
    except Exception:
        pass

    # ---- Phase 0: photos prep (CPU) ----
    try:
        _prepare_photos(status, counters)
    except Exception:
        counters["errors"] += 1
        status(f"Photo preparation failed:\n{traceback.format_exc(limit=2)}")

    audio_files = _new_files(config.INGEST_AUDIO, audio_mod.AUDIO_EXTS, manifest)
    wa_files = _new_files(config.INGEST_WHATSAPP, {".txt"}, manifest)
    sms_files = _new_files(config.INGEST_SMS, {".xml"}, manifest)
    pending_caps = len(graph_store.pending_captions()) if config.CFG["photos"].get("captions", True) else 0

    if not (audio_files or wa_files or sms_files or counters["photos"] or pending_caps):
        status("No new files found in the ingest folders.")
        return counters

    # ---- Phase 1-3: audio (GPU) ----
    if audio_files:
        status("Freeing GPU memory (unloading LLM)…")
        ollama_client.unload()
        status("Loading speech models (first time can take a few minutes)…")
        pipeline = audio_mod.AudioPipeline()
        try:
            for i, f in enumerate(audio_files, 1):
                status(f"Transcribing call {i}/{len(audio_files)}: {f.name}")
                try:
                    wav = audio_mod.to_wav(f)
                    utterances = pipeline.transcribe(wav)
                    wav.unlink(missing_ok=True)
                    audio_mod.save_transcript(f, utterances)
                    msgs = audio_mod.utterances_to_messages(f, utterances)
                    all_messages.extend(msgs)
                    contact = audio_mod.contact_from_filename(f)
                    convo = "\n".join(f"{u.speaker}: {u.text}" for u in utterances)
                    sessions_for_profile.append(
                        (f"Call with {contact} ({f.name})", convo, contact))
                    manifest[_sha256(f)] = f.name
                    counters["audio"] += 1
                except Exception:
                    counters["errors"] += 1
                    status(f"FAILED on {f.name}:\n{traceback.format_exc(limit=2)}")
        finally:
            status("Releasing speech models from GPU…")
            pipeline.close()

    # ---- Phase 4a: parse text sources (CPU) ----
    for f in wa_files:
        status(f"Reading WhatsApp export: {f.name}")
        try:
            all_messages.extend(whatsapp.parse_whatsapp(f))
            manifest[_sha256(f)] = f.name
            counters["whatsapp"] += 1
        except Exception:
            counters["errors"] += 1
            status(f"FAILED on {f.name}:\n{traceback.format_exc(limit=2)}")

    for f in sms_files:
        status(f"Reading SMS backup: {f.name}")
        try:
            all_messages.extend(sms.parse_sms_xml(f))
            manifest[_sha256(f)] = f.name
            counters["sms"] += 1
        except Exception:
            counters["errors"] += 1
            status(f"FAILED on {f.name}:\n{traceback.format_exc(limit=2)}")

    # ---- Phase 4b: chunk + embed (CPU) + store + life-graph ----
    if all_messages:
        cfg = config.CFG["rag"]
        chunks = chunking.messages_to_chunks(
            all_messages, cfg["chunk_chars"], cfg["chunk_overlap_messages"],
            cfg["session_gap_hours"],
        )
        counters["chunks"] = len(chunks)
        if chunks:
            from ..rag import embeddings, store
            status(f"Indexing {len(chunks)} conversation chunks (embedding on CPU)…")
            batch = 32
            for i in range(0, len(chunks), batch):
                part = chunks[i:i + batch]
                embs = embeddings.embed_texts([c["text"] for c in part])
                store.upsert_chunks(part, embs)
                status(f"Indexed {min(i + batch, len(chunks))}/{len(chunks)} chunks…")

        # Sessionize per contact: feeds both the life-graph and profile extraction
        by_contact: Dict[str, List[Message]] = {}
        for m in all_messages:
            by_contact.setdefault(m.contact, []).append(m)
        all_sessions: List[List[Message]] = []
        for contact, msgs in by_contact.items():
            msgs.sort(key=lambda m: m.timestamp)
            for sess in chunking.sessionize(msgs, cfg["session_gap_hours"]):
                all_sessions.append(sess)
                if sess[0].source_type != "call" and len(sess) >= 3:
                    convo = "\n".join(f"{m.sender}: {m.text}" for m in sess)
                    when = sess[0].timestamp.strftime("%d %b %Y")
                    label = f"{sess[0].source_type} with {contact}, {when}"
                    sessions_for_profile.append((label, convo, contact))
        status("Updating the life-graph…")
        graph_build.add_sessions_and_people(all_sessions)

    _save_manifest(manifest)

    # ---- Phase 5a: vision captions (GPU via Ollama) ----
    try:
        counters["captions"] = captions.run_captions(status)
    except Exception:
        counters["errors"] += 1
        status(f"Photo captioning failed:\n{traceback.format_exc(limit=2)}")

    # ---- Phase 5b: profile + graph extraction (text LLM) ----
    if sessions_for_profile:
        if ollama_client.is_up():
            for i, (label, convo, contact) in enumerate(sessions_for_profile, 1):
                status(f"Updating life profile {i}/{len(sessions_for_profile)}…")
                try:
                    extraction = memory_profile.extract_from_conversation(label, convo)
                    graph_build.add_extracted(extraction, contact)
                except Exception:
                    counters["errors"] += 1
        else:
            status("Ollama is not running — skipping profile update (data is still indexed).")

    status(
        f"Done. Calls: {counters['audio']}, WhatsApp files: {counters['whatsapp']}, "
        f"SMS files: {counters['sms']}, photos: {counters['photos']}, "
        f"photo descriptions: {counters['captions']}, chunks indexed: {counters['chunks']}, "
        f"errors: {counters['errors']}."
    )
    return counters
