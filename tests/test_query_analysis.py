import time

from assistant.rag import query_analysis as qa

KNOWN = ["Rahul Sharma", "Aai", "Aarti", "MSEB"]


def test_full_name_and_first_name_match():
    assert qa.detect_contacts("what did rahul sharma say", KNOWN) == ["Rahul Sharma"]
    assert qa.detect_contacts("Rahul ke saath Goa trip?", KNOWN) == ["Rahul Sharma"]


def test_substring_of_longer_word_does_not_match():
    # "aarti" the contact must not fire on the word "art"; nor "Aai" on "chai"
    assert qa.detect_contacts("looking at art galleries", KNOWN) == []
    assert qa.detect_contacts("cutting chai break", KNOWN) == []


def test_multiple_contacts():
    found = qa.detect_contacts("did aai tell rahul about the trip?", KNOWN)
    assert found == ["Rahul Sharma", "Aai"]


def test_date_range_english():
    now = time.time()
    rng = qa.detect_date_range("what commitments did I make last week?", now=now)
    assert rng is not None
    start, end = rng
    assert end == now
    assert 13 * 86400 < end - start <= 14 * 86400


def test_date_range_marathi_hindi():
    assert qa.detect_date_range("गेल्या आठवड्यात आईशी काय बोलणं झालं?") is not None
    assert qa.detect_date_range("पिछले महीने क्या हुआ था?") is not None


def test_widest_window_wins():
    rng = qa.detect_date_range("today and last month combined", now=1_000_000_000.0)
    start, end = rng
    assert end - start == 62 * 86400


def test_no_time_phrase_means_no_range():
    assert qa.detect_date_range("what is the Goa plan?") is None


def test_analyze_combines_both():
    hints = qa.analyze("what did Rahul say last week?", KNOWN)
    assert hints.contacts == ["Rahul Sharma"]
    assert hints.date_range is not None
