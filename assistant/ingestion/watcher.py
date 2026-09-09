"""Watch the ingest folders and run ingestion automatically when new files settle.

Off by default (`app.auto_ingest` in config.yaml): auto-ingest of call
recordings unloads the chat LLM to free the GPU, which would be surprising
mid-conversation — turning it on is the user's call.
"""
import threading
import time

from .. import config
from ..log import get_logger
from . import audio as audio_mod

log = get_logger(__name__)

POLL_SECONDS = 10

_WATCHED = (
    ("INGEST_AUDIO", None),          # exts resolved at poll time; audio set is large
    ("INGEST_WHATSAPP", {".txt"}),
    ("INGEST_SMS", {".xml"}),
    ("INGEST_TELEGRAM", {".json"}),
)


def _snapshot() -> frozenset:
    snap = set()
    for attr, exts in _WATCHED:
        folder = getattr(config, attr)
        exts = exts or audio_mod.AUDIO_EXTS
        if not folder.exists():
            continue
        for p in folder.iterdir():
            if p.is_file() and p.name != ".gitkeep" and p.suffix.lower() in exts:
                st = p.stat()
                snap.add((str(p), st.st_size, int(st.st_mtime)))
    return frozenset(snap)


class FolderWatcher:
    """Two identical consecutive snapshots that differ from the last ingested
    state mean: files arrived and finished copying — safe to process.
    run_ingest's manifest makes a spurious trigger a cheap no-op."""

    def __init__(self):
        self._prev = None
        self._ingested = None  # first stable snapshot triggers a catch-up run

    def should_ingest(self) -> bool:
        snap = _snapshot()
        stable = snap == self._prev
        self._prev = snap
        return stable and snap != self._ingested

    def mark_ingested(self) -> None:
        self._ingested = self._prev


def start(state, run_ingest) -> threading.Thread:
    """Background polling loop; `state` is the server's IngestState so manual
    and automatic ingestion can never overlap."""
    watcher = FolderWatcher()

    def loop():
        while True:
            time.sleep(POLL_SECONDS)
            try:
                if watcher.should_ingest() and state.try_start():
                    try:
                        run_ingest(state.status_cb)
                    finally:
                        state.finish()
                    watcher.mark_ingested()
            except Exception:
                log.exception("Folder watcher iteration failed")

    thread = threading.Thread(target=loop, daemon=True, name="ingest-watcher")
    thread.start()
    return thread
