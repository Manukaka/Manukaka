from datetime import date

from assistant.memory import commitments


def test_parse_due_absolute_formats():
    today = date(2024, 5, 13)
    assert commitments.parse_due("20 May", today) == "2024-05-20"
    assert commitments.parse_due("20/05/2024", today) == "2024-05-20"
    assert commitments.parse_due("by 20th May", today) == "2024-05-20"  # fuzzy


def test_parse_due_rolls_past_dates_into_next_year():
    today = date(2024, 12, 20)
    assert commitments.parse_due("5 Jan", today) == "2025-01-05"


def test_parse_due_vague_text_is_none():
    today = date(2024, 5, 13)
    assert commitments.parse_due("soon", today) is None
    assert commitments.parse_due("after diwali", today) is None
    assert commitments.parse_due("", today) is None


def test_add_from_extraction_parses_and_dedupes(tmp_data_dirs):
    src = "SMS with MSEB, 13 May 2024"
    added = commitments.add_from_extraction(
        [{"what": "Pay electricity bill", "due": "20/05/2030", "with_whom": "MSEB"},
         {"what": "Call Rahul about Goa"},  # undated
         "book train tickets"],             # bare string form
        src,
    )
    assert added == 3
    # same extraction again → all duplicates
    assert commitments.add_from_extraction(
        [{"what": "pay electricity bill", "due": "20/05/2030"}], src) == 0

    items = commitments.load()
    bill = next(c for c in items if "electricity" in c["what"].lower())
    assert bill["due_date"] == "2030-05-20"
    assert bill["with_whom"] == "MSEB"
    assert bill["source"] == src


def test_upcoming_sorts_and_splits(tmp_data_dirs):
    commitments.save([
        {"what": "old done thing", "due_date": "2020-01-01", "due_text": "1 Jan"},
        {"what": "later", "due_date": "2031-03-01", "due_text": "March"},
        {"what": "sooner", "due_date": "2030-06-01", "due_text": "June"},
        {"what": "someday", "due_date": None, "due_text": "soon"},
        {"what": "recent idea", "due_date": None, "due_text": ""},
    ])
    up = commitments.upcoming(today=date(2030, 5, 13))
    assert [c["what"] for c in up["due"]] == ["sooner", "later"]  # past drops off
    assert [c["what"] for c in up["undated"]] == ["recent idea", "someday"]  # newest first
