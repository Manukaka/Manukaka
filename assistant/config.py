"""Loads and validates config.yaml, and exposes paths/settings used across the app.

Validation happens once at import time so a typo in config.yaml fails fast with
a readable message instead of a cryptic KeyError deep inside the stack.
"""
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

ROOT = Path(__file__).resolve().parent.parent

INGEST_DIR = ROOT / "ingest"
INGEST_AUDIO = INGEST_DIR / "audio"
INGEST_WHATSAPP = INGEST_DIR / "whatsapp"
INGEST_SMS = INGEST_DIR / "sms"
INGEST_TELEGRAM = INGEST_DIR / "telegram"

DATA_DIR = ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
PROFILE_DIR = DATA_DIR / "profile"
PROFILE_BACKUP_DIR = PROFILE_DIR / "backups"
PROFILE_JSON = PROFILE_DIR / "profile.json"
PROFILE_MD = PROFILE_DIR / "profile.md"
COMMITMENTS_JSON = PROFILE_DIR / "commitments.json"
MANIFEST_PATH = DATA_DIR / "manifest.json"
CHAT_DB = DATA_DIR / "chat.db"
LOG_DIR = DATA_DIR / "logs"

UI_DIR = ROOT / "assistant" / "ui"


class _Strict(BaseModel):
    """extra="forbid" turns config.yaml typos into named errors instead of silence."""
    model_config = ConfigDict(extra="forbid")


class LLMConfig(_Strict):
    model: str
    ollama_url: str = "http://127.0.0.1:11434"
    num_ctx: int = 8192
    temperature: float = 0.4
    chat_history_turns: int = 8


class SttConfig(_Strict):
    whisper_model: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "int8_float16"
    language: Optional[str] = None


class DiarizationConfig(_Strict):
    enabled: bool = True
    model: str = "pyannote/speaker-diarization-3.1"
    num_speakers: Optional[int] = 2


class RagConfig(_Strict):
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    chunk_chars: int = 1800
    chunk_overlap_messages: int = 2
    session_gap_hours: float = 3
    top_k_fetch: int = 10
    top_k_use: int = 6
    recency_boost: float = 0.1
    hybrid: bool = True            # BM25 keyword search fused with vector search
    rrf_k: int = 60                # reciprocal-rank-fusion constant
    contact_boost: float = 0.3     # boost when the question names the chunk's contact
    date_boost: float = 0.3        # boost when the question points at the chunk's time window
    query_rewrite: bool = True     # LLM-rewrite follow-up questions into standalone queries


class ProfileConfig(_Strict):
    max_facts_before_merge: int = 150
    profile_md_max_chars: int = 6000


class AppConfig(_Strict):
    host: str = "127.0.0.1"
    port: int = 8765
    window_title: str = "Manu — Personal Assistant"


class Config(_Strict):
    llm: LLMConfig
    stt: SttConfig = SttConfig()
    diarization: DiarizationConfig = DiarizationConfig()
    rag: RagConfig = RagConfig()
    profile: ProfileConfig = ProfileConfig()
    app: AppConfig = AppConfig()


def _format_errors(err: ValidationError) -> str:
    lines = []
    for e in err.errors():
        where = ".".join(str(p) for p in e["loc"]) or "(top level)"
        lines.append(f"  - {where}: {e['msg']}")
    return "\n".join(lines)


def load_config(path: Path) -> dict:
    """Parse and validate a config.yaml; exits with a readable message on errors."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {path}")
    except yaml.YAMLError as e:
        raise SystemExit(f"config.yaml is not valid YAML:\n{e}")
    try:
        return Config.model_validate(raw).model_dump()
    except ValidationError as e:
        raise SystemExit(
            f"config.yaml has invalid or unknown settings:\n{_format_errors(e)}\n"
            "Fix the lines above (see README section 5) and start Manu again."
        )


CFG = load_config(ROOT / "config.yaml")


def ensure_dirs() -> None:
    for d in (INGEST_AUDIO, INGEST_WHATSAPP, INGEST_SMS, INGEST_TELEGRAM,
              CHROMA_DIR, TRANSCRIPTS_DIR, PROFILE_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
