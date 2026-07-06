import json
from datetime import datetime
from pathlib import Path

from assistant.ingestion.telegram import parse_telegram

FIXTURES = Path(__file__).parent / "fixtures"


def test_full_export_skips_service_media_and_saved_messages():
    msgs = parse_telegram(FIXTURES / "telegram_result.json")
    # saved_messages chat, service event, and captionless photo are all skipped
    assert len(msgs) == 2
    assert all(m.contact == "Priya" for m in msgs)
    assert all(m.source_type == "telegram" for m in msgs)
    assert msgs[0].sender == "Priya"
    assert "Passport renewal" in msgs[0].text
    assert msgs[0].timestamp == datetime(2024, 5, 13, 21, 41, 7)


def test_entity_list_text_is_flattened():
    msgs = parse_telegram(FIXTURES / "telegram_result.json")
    assert msgs[1].text == "https://example.com/form ha form bhara"


def test_single_chat_export_shape(tmp_path):
    single = {
        "name": "Rahul", "type": "personal_chat",
        "messages": [{"type": "message", "date": "2024-05-14T10:00:00",
                      "from": "Rahul", "text": "single chat export works"}],
    }
    p = tmp_path / "result.json"
    p.write_text(json.dumps(single), encoding="utf-8")
    msgs = parse_telegram(p)
    assert len(msgs) == 1
    assert msgs[0].contact == "Rahul"


def test_unknown_shape_returns_empty(tmp_path):
    p = tmp_path / "result.json"
    p.write_text(json.dumps({"something": "else"}), encoding="utf-8")
    assert parse_telegram(p) == []
