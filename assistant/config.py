"""Loads config.yaml and exposes paths/settings used across the app."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

INGEST_DIR = ROOT / "ingest"
INGEST_AUDIO = INGEST_DIR / "audio"
INGEST_WHATSAPP = INGEST_DIR / "whatsapp"
INGEST_SMS = INGEST_DIR / "sms"
INGEST_PHOTOS = INGEST_DIR / "photos"

DATA_DIR = ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
THUMBS_DIR = DATA_DIR / "thumbs"
GRAPH_DB = DATA_DIR / "graph.db"
PROFILE_DIR = DATA_DIR / "profile"
PROFILE_JSON = PROFILE_DIR / "profile.json"
PROFILE_MD = PROFILE_DIR / "profile.md"
MANIFEST_PATH = DATA_DIR / "manifest.json"

UI_DIR = ROOT / "assistant" / "ui"


def _load() -> dict:
    with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG = _load()


def ensure_dirs() -> None:
    for d in (INGEST_AUDIO, INGEST_WHATSAPP, INGEST_SMS, INGEST_PHOTOS,
              CHROMA_DIR, TRANSCRIPTS_DIR, THUMBS_DIR, PROFILE_DIR):
        d.mkdir(parents=True, exist_ok=True)
