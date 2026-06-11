from datetime import datetime, timedelta
from pathlib import Path

from assistant.ingestion import chunking
from assistant.ingestion.models import Message
from assistant.ingestion.sms import parse_sms_xml
from assistant.ingestion.whatsapp import parse_whatsapp

FIXTURES = Path(__file__).parent / "fixtures"


def test_whatsapp_android():
    msgs = parse_whatsapp(FIXTURES / "WhatsApp Chat with Aai.txt")
    # system line, media, deleted message are skipped → 4 real messages
    assert len(msgs) == 4
    assert msgs[0].sender == "Aai"
    assert msgs[0].contact == "Aai"
    assert "जेवायला" in msgs[0].text
    # day-first parsing: 13/05/24 = 13 May 2024, 9:41 am
    assert msgs[0].timestamp == datetime(2024, 5, 13, 9, 41)
    # multiline continuation collapsed into one message
    multiline = msgs[2]
    assert "dawai" in multiline.text and "kal subah" in multiline.text
    # narrow no-break space before "pm" still parses, as 20:00
    assert msgs[3].timestamp == datetime(2024, 5, 14, 20, 0)


def test_whatsapp_ios():
    msgs = parse_whatsapp(FIXTURES / "WhatsApp Chat with Rahul.txt")
    assert len(msgs) == 3  # "image omitted" is skipped
    assert msgs[0].sender == "Rahul"
    assert msgs[0].timestamp == datetime(2024, 5, 13, 21, 41, 7)
    assert msgs[-1].text == "Goa, June first week"


def test_sms_xml():
    msgs = parse_sms_xml(FIXTURES / "sms_backup.xml")
    assert len(msgs) == 3  # the empty-body sms is skipped
    mseb = [m for m in msgs if m.contact == "MSEB"]
    assert len(mseb) == 2
    assert mseb[0].sender == "MSEB"      # received
    assert mseb[1].sender == "Me"        # sent
    # "(Unknown)" contact falls back to the phone number
    unknown = [m for m in msgs if m.contact == "+918888777666"]
    assert len(unknown) == 1


def _mk(ts, sender="A", text="hello", contact="A"):
    return Message(timestamp=ts, sender=sender, text=text,
                   contact=contact, source_type="whatsapp", source_file="f.txt")


def test_sessionize_splits_on_gap():
    t0 = datetime(2024, 5, 13, 9, 0)
    msgs = [_mk(t0), _mk(t0 + timedelta(minutes=5)), _mk(t0 + timedelta(hours=7))]
    sessions = chunking.sessionize(msgs, gap_hours=3)
    assert [len(s) for s in sessions] == [2, 1]


def test_chunking_packs_and_never_splits_messages():
    t0 = datetime(2024, 5, 13, 9, 0)
    msgs = [_mk(t0 + timedelta(minutes=i), text=f"message number {i} " + "x" * 200)
            for i in range(20)]
    chunks = chunking.build_chunks(msgs, chunk_chars=1000, overlap_messages=2)
    assert len(chunks) > 1
    for c in chunks:
        assert c["text"].startswith("WhatsApp chat with A, 13 May 2024:")
        assert c["metadata"]["contact"] == "A"
    # every message appears in at least one chunk
    joined = "\n".join(c["text"] for c in chunks)
    for i in range(20):
        assert f"message number {i} " in joined
    # deterministic ids → idempotent upserts
    again = chunking.build_chunks(msgs, chunk_chars=1000, overlap_messages=2)
    assert [c["id"] for c in chunks] == [c["id"] for c in again]


def test_messages_to_chunks_groups_by_contact():
    t0 = datetime(2024, 5, 13, 9, 0)
    msgs = [_mk(t0, contact="A"), _mk(t0, contact="B", sender="B")]
    chunks = chunking.messages_to_chunks(msgs)
    contacts = sorted(c["metadata"]["contact"] for c in chunks)
    assert contacts == ["A", "B"]
