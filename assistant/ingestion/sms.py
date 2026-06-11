"""Parser for "SMS Backup & Restore" (Android app) XML exports.

Uses iterparse because real backups can be tens of MB. Only <sms> elements are
read in v1; <mms> is skipped.
"""
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List

from .models import Message

TYPE_RECEIVED = "1"
TYPE_SENT = "2"


def parse_sms_xml(path: Path) -> List[Message]:
    messages: List[Message] = []
    for _, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag != "sms":
            continue
        body = elem.get("body") or ""
        sms_type = elem.get("type")
        date_ms = elem.get("date")
        address = elem.get("address") or "Unknown"
        contact = elem.get("contact_name") or ""
        if not contact or contact == "(Unknown)":
            contact = address
        if body.strip() and date_ms and sms_type in (TYPE_RECEIVED, TYPE_SENT):
            try:
                ts = datetime.fromtimestamp(int(date_ms) / 1000)
            except (ValueError, OSError, OverflowError):
                elem.clear()
                continue
            sender = "Me" if sms_type == TYPE_SENT else contact
            messages.append(Message(
                timestamp=ts, sender=sender, text=body,
                contact=contact, source_type="sms", source_file=path.name,
            ))
        elem.clear()
    messages.sort(key=lambda m: (m.contact, m.timestamp))
    return messages
