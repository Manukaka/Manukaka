"""Cheap, deterministic hints mined from the question itself: which known
contacts it names, and whether it points at a recent time window.

These only *boost* matching chunks (never hard-filter) — a name or date in a
question is a strong signal, not a guarantee the answer lives there.
"""
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

# "recent past" phrases (English / Marathi / Hindi) → how many days back to
# stretch the window. Windows are deliberately generous: "last week" (7-14
# days ago) becomes 14 days so boundary chunks still get the boost.
_TIME_PHRASES = [
    (("today", "आज"), 1),
    (("yesterday", "काल", "कल"), 2),
    (("this week", "या आठवड्यात", "इस हफ्ते"), 7),
    (("last week", "गेल्या आठवड्यात", "मागच्या आठवड्यात", "पिछले हफ्ते", "पिछले सप्ताह"), 14),
    (("this month", "या महिन्यात", "इस महीने"), 31),
    (("last month", "गेल्या महिन्यात", "मागच्या महिन्यात", "पिछले महीने"), 62),
]


@dataclass
class QueryHints:
    contacts: List[str]
    date_range: Optional[Tuple[float, float]]  # (start, end) epoch seconds


def detect_contacts(question: str, known_contacts: List[str]) -> List[str]:
    q = question.lower()
    found = []
    for contact in known_contacts:
        c = contact.lower().strip()
        if not c:
            continue
        # Full name anywhere, or the first name as a whole word
        # ("rahul" should hit contact "Rahul Sharma", but "art" must not hit "Aarti")
        first = re.escape(c.split()[0])
        if c in q or re.search(rf"(?<!\w){first}(?!\w)", q):
            found.append(contact)
    return found


def detect_date_range(question: str, now: Optional[float] = None) -> Optional[Tuple[float, float]]:
    q = question.lower()
    now = now if now is not None else time.time()
    best_days = 0
    for phrases, days in _TIME_PHRASES:
        for phrase in phrases:
            if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", q):
                best_days = max(best_days, days)
    if not best_days:
        return None
    return (now - best_days * 86400, now)


def analyze(question: str, known_contacts: List[str]) -> QueryHints:
    return QueryHints(
        contacts=detect_contacts(question, known_contacts),
        date_range=detect_date_range(question),
    )
