"""Environment-driven configuration for the Satya backend.

Nothing secret is hard-coded. The Claude API key is read by the Anthropic SDK
from ANTHROPIC_API_KEY; everything else has a safe default so the app boots
even before deployment is fully configured.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # satya/backend
SHARED_DIR = ROOT.parent / "shared"                     # satya/shared

# ---- Claude / model ----
# Default to the most capable Opus-tier model. Override per environment.
MODEL = os.getenv("SATYA_MODEL", "claude-opus-4-8")
EFFORT = os.getenv("SATYA_EFFORT", "medium")            # low | medium | high | xhigh | max
MAX_TOKENS = int(os.getenv("SATYA_MAX_TOKENS", "2000"))
WEB_SEARCH_MAX_USES = int(os.getenv("SATYA_WEB_SEARCH_MAX_USES", "5"))

# ---- Cache ----
CACHE_DB = os.getenv("SATYA_CACHE_DB", str(ROOT / "satya_cache.sqlite3"))
CACHE_TTL_HOURS = int(os.getenv("SATYA_CACHE_TTL_HOURS", "72"))

# ---- App ----
HOST = os.getenv("SATYA_HOST", "0.0.0.0")
PORT = int(os.getenv("SATYA_PORT", "8000"))
# Comma-separated list of allowed CORS origins; "*" for any (dev only).
CORS_ORIGINS = [o.strip() for o in os.getenv("SATYA_CORS_ORIGINS", "*").split(",") if o.strip()]

# Languages the app exposes today; the AI can answer in any of them.
SUPPORTED_LANGS = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}
DEFAULT_LANG = "en"


def load_shared_json(name: str) -> dict:
    """Read a file from satya/shared (verdict taxonomy, Indian sources)."""
    path = SHARED_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


VERDICT_TAXONOMY = load_shared_json("verdict_taxonomy.json")
INDIAN_SOURCES = load_shared_json("indian_sources.json")

VERDICT_CODES = [v["code"] for v in VERDICT_TAXONOMY["verdicts"]]
