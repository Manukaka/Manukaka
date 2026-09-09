"""Structured commitments with real due dates.

The profile extractor already pulls commitments out of every conversation as
{what, with_whom, due}. This module keeps them as structured records with a
parsed ISO due date, so "what should I not forget?" is answered from data
instead of vibes.
"""
import json
from datetime import date, datetime
from typing import Dict, List, Optional

from dateutil import parser as dateparser

from .. import config
from ..log import get_logger

log = get_logger(__name__)

MAX_UNDATED = 15       # undated commitments shown, newest first
PAST_GRACE_DAYS = 7    # keep just-missed items visible instead of hiding them


def parse_due(text: str, today: Optional[date] = None) -> Optional[str]:
    """'20 May' / '20/05/2024' → ISO date; vague text ('soon', 'diwali') → None."""
    text = (text or "").strip()
    if not text:
        return None
    today = today or date.today()
    try:
        parsed = dateparser.parse(
            text, dayfirst=True, fuzzy=True,
            default=datetime(today.year, today.month, today.day),
        )
    except (ValueError, OverflowError, TypeError):
        return None
    if parsed is None:
        return None
    if (parsed.date() == today and not any(ch.isdigit() for ch in text)
            and text.lower() not in ("today", "आज")):
        # fuzzy parse found no real date tokens and just echoed the default
        return None
    due = parsed.date()
    # "20 May" said in December almost always means next year's 20 May
    if due < today and due.replace(year=due.year + 1) >= today:
        due = due.replace(year=due.year + 1)
    return due.isoformat()


def load() -> List[Dict]:
    if config.COMMITMENTS_JSON.exists():
        return json.loads(config.COMMITMENTS_JSON.read_text(encoding="utf-8"))
    return []


def save(items: List[Dict]) -> None:
    config.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    config.COMMITMENTS_JSON.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add_from_extraction(extracted: List, source: str) -> int:
    """Merge one conversation's extracted commitments; returns how many were new."""
    if not extracted:
        return 0
    items = load()
    seen = {(c.get("what", "").lower(), c.get("due_date")) for c in items}
    added = 0
    for entry in extracted:
        if isinstance(entry, str):
            entry = {"what": entry}
        if not isinstance(entry, dict):
            continue
        what = str(entry.get("what", "")).strip()
        if not what:
            continue
        due_text = str(entry.get("due", "") or "").strip()
        due_date = parse_due(due_text)
        key = (what.lower(), due_date)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "what": what,
            "with_whom": str(entry.get("with_whom", "") or "").strip(),
            "due_text": due_text,
            "due_date": due_date,
            "source": source,
            "added": date.today().isoformat(),
        })
        added += 1
    if added:
        save(items)
    return added


def upcoming(today: Optional[date] = None) -> Dict[str, List[Dict]]:
    """{'due': dated items from (today - grace) onward, soonest first;
        'undated': newest undated items}."""
    today = today or date.today()
    floor = today.toordinal() - PAST_GRACE_DAYS
    items = load()
    dated = [c for c in items if c.get("due_date")
             and date.fromisoformat(c["due_date"]).toordinal() >= floor]
    dated.sort(key=lambda c: c["due_date"])
    undated = [c for c in items if not c.get("due_date")]
    undated.reverse()  # stored oldest-first; show newest extractions first
    return {"due": dated, "undated": undated[:MAX_UNDATED]}
