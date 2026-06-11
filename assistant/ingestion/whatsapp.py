"""Parser for WhatsApp "Export chat" .txt files (Android and iOS formats).

Handles the Unicode quirks of real exports: left-to-right marks, the narrow
no-break space before am/pm in newer exports, and multiline messages.
"""
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dateutil import parser as dateparser

from .models import Message

# Android: "13/05/24, 9:41 pm - Aai: message"  (also dd/mm/yyyy, 24h, AM/PM)
ANDROID_RE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s(\d{1,2}:\d{2})(?:\s?([apAP][mM]))?\s-\s(.*)$"
)
# iOS: "[13/05/24, 9:41:07 PM] Aai: message"
IOS_RE = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s(\d{1,2}:\d{2}(?::\d{2})?)\s?([apAP][mM])?\]\s(.*)$"
)

SKIP_BODIES = (
    "<Media omitted>",
    "This message was deleted",
    "You deleted this message",
    "Missed voice call",
    "Missed video call",
    "null",
)
SKIP_SUBSTRINGS = (
    "Messages and calls are end-to-end encrypted",
    "image omitted",
    "video omitted",
    "audio omitted",
    "sticker omitted",
    "GIF omitted",
    "document omitted",
)


def _clean_line(line: str) -> str:
    # LRM/RLM marks break the regexes; narrow no-break space appears before am/pm
    return line.replace("‎", "").replace("‏", "").replace(" ", " ").rstrip("\n")


def _parse_ts(date_s: str, time_s: str, ampm: Optional[str]) -> datetime:
    stamp = f"{date_s} {time_s}"
    if ampm:
        stamp += f" {ampm}"
    # Indian exports are day-first (13/05/24 = 13 May)
    return dateparser.parse(stamp, dayfirst=True)


def contact_from_filename(path: Path) -> str:
    name = path.stem
    m = re.match(r"WhatsApp Chat with (.+)", name, re.IGNORECASE)
    return m.group(1).strip() if m else name


def parse_whatsapp(path: Path) -> List[Message]:
    contact = contact_from_filename(path)
    messages: List[Message] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    # Lock the format using the first lines that match either regex
    fmt = None
    for line in lines[:50]:
        line = _clean_line(line)
        if ANDROID_RE.match(line):
            fmt = ANDROID_RE
            break
        if IOS_RE.match(line):
            fmt = IOS_RE
            break
    if fmt is None:
        return []

    for raw in lines:
        line = _clean_line(raw)
        if not line.strip():
            continue
        m = fmt.match(line)
        if not m:
            # Continuation of a multiline message
            if messages:
                messages[-1].text += "\n" + line
            continue
        date_s, time_s, ampm, rest = m.groups()
        # "Sender: text" — no colon means a system message (group created, etc.)
        if ": " not in rest:
            continue
        sender, text = rest.split(": ", 1)
        if text.strip() in SKIP_BODIES or any(s in text for s in SKIP_SUBSTRINGS):
            continue
        try:
            ts = _parse_ts(date_s, time_s, ampm)
        except (ValueError, OverflowError):
            continue
        messages.append(Message(
            timestamp=ts, sender=sender.strip(), text=text,
            contact=contact, source_type="whatsapp", source_file=path.name,
        ))
    return messages
