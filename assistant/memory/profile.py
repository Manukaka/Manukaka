"""Long-term memory: extract durable facts from each new conversation into
profile.json, and render a compact profile.md that is injected into every chat."""
import json
from datetime import date, datetime
from typing import Dict, List

from .. import config
from ..llm import ollama_client, prompts
from ..log import get_logger

log = get_logger(__name__)

CATEGORIES = ("people", "commitments", "finances", "health", "work", "preferences")
KEEP_BACKUPS = 10


def load_profile() -> Dict:
    if config.PROFILE_JSON.exists():
        return json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))
    return {c: [] for c in CATEGORIES}


def save_profile(profile: Dict) -> None:
    config.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    config.PROFILE_JSON.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    config.PROFILE_MD.write_text(render_md(profile), encoding="utf-8")


def load_profile_md() -> str:
    if config.PROFILE_MD.exists():
        return config.PROFILE_MD.read_text(encoding="utf-8")
    return ""


def extract_from_conversation(source_label: str, conversation_text: str) -> None:
    """One LLM call per session/transcript (map step). Failures are non-fatal."""
    # Very long calls are truncated; durable facts repeat enough that this is fine
    text = conversation_text[:12000]
    result = ollama_client.extract(
        prompts.build_extraction_prompt(source_label, text),
        prompts.PROFILE_EXTRACTION_SCHEMA,
        system=prompts.PROFILE_EXTRACTION_SYSTEM,
    )
    if not result:
        return
    profile = load_profile()
    today = date.today().isoformat()
    for cat in CATEGORIES:
        for item in result.get(cat, []) or []:
            entry = {"fact": item, "source": source_label, "date": today}
            profile.setdefault(cat, []).append(entry)
    profile = _maybe_merge(profile)
    save_profile(profile)


def _fact_text(entry: Dict) -> str:
    fact = entry.get("fact", entry)
    if isinstance(fact, dict):
        return ", ".join(f"{k}: {v}" for k, v in fact.items() if v)
    return str(fact)


def _backup_profile() -> None:
    """Snapshot profile.json before an LLM merge rewrites it — a bad merge must
    never be able to silently erase months of memory."""
    if not config.PROFILE_JSON.exists():
        return
    config.PROFILE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = config.PROFILE_BACKUP_DIR / f"profile-{stamp}.json"
    dest.write_bytes(config.PROFILE_JSON.read_bytes())
    backups = sorted(config.PROFILE_BACKUP_DIR.glob("profile-*.json"))
    for old in backups[:-KEEP_BACKUPS]:
        old.unlink(missing_ok=True)


def _maybe_merge(profile: Dict) -> Dict:
    """When the profile grows too big, ask the LLM to dedupe and compact it."""
    total = sum(len(profile.get(c, [])) for c in CATEGORIES)
    if total <= config.CFG["profile"]["max_facts_before_merge"]:
        return profile
    _backup_profile()
    log.info("Profile reached %d facts; asking the LLM to compact it", total)
    listing = json.dumps(profile, ensure_ascii=False)[:20000]
    merged = ollama_client.extract(
        "Here is the current profile as JSON. Merge duplicates, keep the newest "
        "version of conflicting facts, drop trivia, and return a compact profile:\n"
        + listing,
        prompts.PROFILE_EXTRACTION_SCHEMA,
        system=prompts.PROFILE_MERGE_SYSTEM,
    )
    if not merged:
        return profile
    today = date.today().isoformat()
    out: Dict[str, List] = {c: [] for c in CATEGORIES}
    for cat in CATEGORIES:
        for item in merged.get(cat, []) or []:
            out[cat].append({"fact": item, "source": "merged", "date": today})
    return out


def render_md(profile: Dict) -> str:
    max_chars = config.CFG["profile"]["profile_md_max_chars"]
    titles = {
        "commitments": "Commitments & upcoming things",
        "people": "People in the user's life",
        "work": "Work",
        "finances": "Finances",
        "health": "Health",
        "preferences": "Preferences",
    }
    lines: List[str] = []
    # Commitments first (most actionable), newest entries first within a section
    for cat in ("commitments", "people", "work", "finances", "health", "preferences"):
        entries = profile.get(cat, [])
        if not entries:
            continue
        lines.append(f"### {titles[cat]}")
        for entry in reversed(entries):
            lines.append(f"- {_fact_text(entry)}")
        lines.append("")
    text = "\n".join(lines)
    return text[:max_chars]
