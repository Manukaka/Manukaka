from assistant.rag import keyword, store
from assistant.rag.keyword import BM25Index


def _doc(cid, text, contact="Aai"):
    return {"id": cid, "text": text, "metadata": {"contact": contact}}


DOCS = [
    _doc("1", "Rahul ke saath Goa trip ka plan hai June first week", contact="Rahul"),
    _doc("2", "Aai ने विचारलं जेवायला काय करू, dawai kal subah ghyaychi aahe"),
    _doc("3", "MSEB electricity bill 1431 rupees due on 20 May", contact="MSEB"),
    _doc("4", "random chit chat about weather and cricket match"),
]


def test_exact_name_and_amount_win():
    idx = BM25Index(DOCS)
    assert idx.search("Goa trip Rahul", 4)[0]["id"] == "1"
    assert idx.search("electricity bill 1431", 4)[0]["id"] == "3"


def test_devanagari_and_hinglish_tokens_match():
    idx = BM25Index(DOCS)
    assert idx.search("जेवायला काय", 4)[0]["id"] == "2"
    assert idx.search("dawai subah", 4)[0]["id"] == "2"


def test_no_match_returns_empty():
    idx = BM25Index(DOCS)
    assert idx.search("zzz unknown term", 4) == []


def test_empty_index_is_safe():
    idx = BM25Index([])
    assert idx.search("anything", 5) == []
    assert idx.contacts() == []


def test_contacts_are_unique_and_sorted():
    assert BM25Index(DOCS).contacts() == ["Aai", "MSEB", "Rahul"]


def test_index_cache_rebuilds_when_count_changes(monkeypatch):
    calls = {"builds": 0}
    docs = [DOCS[0]]

    def fake_get_all():
        calls["builds"] += 1
        return list(docs)

    monkeypatch.setattr(store, "count", lambda: len(docs))
    monkeypatch.setattr(store, "get_all", fake_get_all)
    monkeypatch.setattr(keyword, "_index", None)
    monkeypatch.setattr(keyword, "_index_count", -1)

    keyword.get_index()
    keyword.get_index()
    assert calls["builds"] == 1  # cached while count is stable

    docs.append(DOCS[2])  # ingest happened
    keyword.get_index()
    assert calls["builds"] == 2
    assert keyword.known_contacts() == ["MSEB", "Rahul"]
