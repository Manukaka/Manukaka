"""Shared message shape produced by every parser (WhatsApp, SMS, call transcripts)."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    timestamp: datetime
    sender: str        # "Me", a contact name, or "SPEAKER_00"/"SPEAKER_01" for calls
    text: str
    contact: str       # the person/chat this message belongs to
    source_type: str   # "whatsapp" | "sms" | "call"
    source_file: str   # original file name, for traceability
