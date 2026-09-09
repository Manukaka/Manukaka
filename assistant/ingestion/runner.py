"""Ingestion orchestrator.

Phase order is the whole point on an 8GB GPU:
  1. Unload the Ollama LLM (frees VRAM)
  2. Transcribe + diarize ALL new audio in one batch (whisper+pyannote on GPU)
  3. Free whisper/pyannote VRAM
  4. Parse text sources, chunk everything, embed on CPU, store in Chroma
  5. Profile extraction via Ollama (LLM reloads now that the GPU is free)

A sha256 manifest makes re-running over the same drop folders a no-op.
"""
import hashlib
import json
import threading
import traceback
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .. import config
from ..llm import ollama_client
from ..log import get_logger
from ..memory import profile as memory_profile
from . import audio as audio_mod
from . import chunking, sms, telegram, whatsapp
from .models import Message

StatusCb = Callable[[str], None]

log = get_logger(__name__)

# Set while whisper/pyannote own the GPU (chatting then would OOM the card).
# The server only blocks chat during this window, not the whole ingest run.
GPU_BUSY = threading.Event()


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


def run_ingest(status: StatusCb = print) -> Dict[str, int]:
    """Process everything new in the ingest/ folders. Returns simple counters."""
    config.ensure_dirs()
    manifest = _load_manifest()
    counters = {"audio": 0, "whatsapp": 0, "sms": 0, "telegram": 0, "chunks": 0, "errors": 0}
    all_messages: List[Message] = []
    sessions_for_profile: List[tuple] = []  # (source_label, text)

    audio_files = _new_files(config.INGEST_AUDIO, audio_mod.AUDIO_EXTS, manifest)
    wa_files = _new_files(config.INGEST_WHATSAPP, {".txt"}, manifest)
    sms_files = _new_files(config.INGEST_SMS, {".xml"}, manifest)
    tg_files = _new_files(config.INGEST_TELEGRAM, {".json"}, manifest)

    if not (audio_files or wa_files or sms_files or tg_files):
        status("No new files found in the ingest folders.")
        return counters

    # ---- Phase 1-3: audio (GPU) ----
    if audio_files:
        GPU_BUSY.set()
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
                    convo = "\n".join(f"{u.speaker}: {u.text}" for u in utterances)
                    label = f"Call with {audio_mod.contact_from_filename(f)} ({f.name})"
                    sessions_for_profile.append((label, convo))
                    manifest[_sha256(f)] = f.name
                    counters["audio"] += 1
                except Exception:
                    counters["errors"] += 1
                    log.exception("Transcription failed for %s", f.name)
                    status(f"FAILED on {f.name}:\n{traceback.format_exc(limit=2)}")
        finally:
            status("Releasing speech models from GPU…")
            pipeline.close()
            GPU_BUSY.clear()

    # ---- Phase 4a: parse text sources (CPU) ----
    for f in wa_files:
        status(f"Reading WhatsApp export: {f.name}")
        try:
            msgs = whatsapp.parse_whatsapp(f)
            all_messages.extend(msgs)
            manifest[_sha256(f)] = f.name
            counters["whatsapp"] += 1
        except Exception:
            counters["errors"] += 1
            log.exception("WhatsApp parse failed for %s", f.name)
            status(f"FAILED on {f.name}:\n{traceback.format_exc(limit=2)}")

    for f in sms_files:
        status(f"Reading SMS backup: {f.name}")
        try:
            msgs = sms.parse_sms_xml(f)
            all_messages.extend(msgs)
            manifest[_sha256(f)] = f.name
            counters["sms"] += 1
        except Exception:
            counters["errors"] += 1
            log.exception("SMS parse failed for %s", f.name)
            status(f"FAILED on {f.name}:\n{traceback.format_exc(limit=2)}")

    for f in tg_files:
        status(f"Reading Telegram export: {f.name}")
        try:
            msgs = telegram.parse_telegram(f)
            all_messages.extend(msgs)
            manifest[_sha256(f)] = f.name
            counters["telegram"] += 1
        except Exception:
            counters["errors"] += 1
            log.exception("Telegram parse failed for %s", f.name)
            status(f"FAILED on {f.name}:\n{traceback.format_exc(limit=2)}")

    # ---- Phase 4b: chunk + embed (CPU) + store ----
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

        # Collect text sessions for profile extraction (largest sessions first)
        text_msgs = [m for m in all_messages if m.source_type != "call"]
        by_contact: Dict[str, List[Message]] = {}
        for m in text_msgs:
            by_contact.setdefault(m.contact, []).append(m)
        for contact, msgs in by_contact.items():
            msgs.sort(key=lambda m: m.timestamp)
            for sess in chunking.sessionize(msgs, config.CFG["rag"]["session_gap_hours"]):
                if len(sess) < 3:
                    continue  # tiny sessions rarely contain durable facts
                convo = "\n".join(f"{m.sender}: {m.text}" for m in sess)
                when = sess[0].timestamp.strftime("%d %b %Y")
                label = f"{sess[0].source_type} with {contact}, {when}"
                sessions_for_profile.append((label, convo))

    _save_manifest(manifest)

    # ---- Phase 5: profile extraction (LLM, GPU is free again) ----
    if sessions_for_profile:
        if ollama_client.is_up():
            for i, (label, convo) in enumerate(sessions_for_profile, 1):
                status(f"Updating life profile {i}/{len(sessions_for_profile)}…")
                try:
                    memory_profile.extract_from_conversation(label, convo)
                except Exception:
                    counters["errors"] += 1
                    log.exception("Profile extraction failed for %s", label)
        else:
            status("Ollama is not running — skipping profile update (data is still indexed).")

    status(
        f"Done. Calls: {counters['audio']}, WhatsApp files: {counters['whatsapp']}, "
        f"SMS files: {counters['sms']}, Telegram files: {counters['telegram']}, "
        f"chunks indexed: {counters['chunks']}, errors: {counters['errors']}."
    )
    return counters
