from datetime import datetime, timedelta

from assistant.graph import build, store
from assistant.ingestion import chunking
from assistant.ingestion.models import Message
from assistant.ingestion.photos import PhotoRecord


def _msg(ts, sender, contact, text="hi", source="whatsapp"):
    return Message(timestamp=ts, sender=sender, text=text, contact=contact,
                   source_type=source, source_file=f"{contact}.txt")


def test_sessions_and_people_build(tmp_data):
    t0 = datetime(2024, 5, 13, 9, 0)
    msgs = ([_msg(t0 + timedelta(minutes=i), "Me", "Aai") for i in range(5)] +
            [_msg(t0 + timedelta(minutes=i), "Aai", "Aai") for i in range(5)])
    sessions = chunking.sessionize(sorted(msgs, key=lambda m: m.timestamp), 3)
    build.add_sessions_and_people(sessions)
    payload = store.graph_payload()
    names = {n["name"] for n in payload["nodes"]}
    assert "Me" in names and "Aai" in names
    # there is a talks_with edge from Me to Aai
    me = store.node_id("person", "Me")
    aai = store.node_id("person", "Aai")
    assert any(l["source"] == me and l["target"] == aai and l["type"] == "talks_with"
               for l in payload["links"])


def test_photo_links_fuzzy_and_places(tmp_data):
    # seed a contact "Rahul" so the "Rahul Sharma" tag fuzzy-matches it
    store.upsert_node("person", "Rahul", {"msg_count": 10})
    rec = PhotoRecord(rel_path="a.jpg", file_size=10, mtime=1.0, taken_ts=1686566400.0,
                      lat=15.5, lon=73.7, people=["Rahul Sharma"])
    pid = store.upsert_photo(rec, {"name": "Baga", "admin": "Goa", "cc": "IN",
                                   "label": "Baga, Goa, India"})
    build.add_photo_links(pid, rec.people, "Baga, Goa, India")
    # photo linked to the existing Rahul node, not a new "Rahul Sharma" node
    rahul = store.node_id("person", "Rahul")
    person = store.person_payload(rahul)
    assert person["photos"] and person["photos"][0]["photo_id"] == pid
    # a place node + a place in places_payload
    places = store.places_payload()
    assert places and places[0]["name"] == "Baga, Goa, India"


def test_timeline_orders_photos_and_sessions(tmp_data):
    store.upsert_session("whatsapp", "Aai", datetime(2024, 1, 1).timestamp(),
                         datetime(2024, 1, 1).timestamp(), 12, "Aai.txt")
    rec = PhotoRecord(rel_path="b.jpg", file_size=1, mtime=1.0,
                      taken_ts=datetime(2024, 6, 1).timestamp())
    pid = store.upsert_photo(rec)
    store.set_caption(pid, "a beach at sunset")
    items = store.timeline(None, 50)
    assert [i["type"] for i in items][0] == "photo"   # newer first
    assert items[0]["subtitle"] == "a beach at sunset"
    assert any(i["type"] == "chat" for i in items)


def test_idempotent_rebuild(tmp_data):
    t0 = datetime(2024, 5, 13, 9, 0)
    msgs = [_msg(t0 + timedelta(minutes=i), "Me", "Aai") for i in range(6)]
    sessions = chunking.sessionize(msgs, 3)
    build.add_sessions_and_people(sessions)
    n1 = len(store.graph_payload()["nodes"])
    e1 = len(store.graph_payload()["links"])
    # running the same build again must not duplicate nodes/edges
    build.add_sessions_and_people(sessions)
    assert len(store.graph_payload()["nodes"]) == n1
    assert len(store.graph_payload()["links"]) == e1


def test_extracted_events_topics(tmp_data):
    store.upsert_node("person", "Rahul")
    build.add_extracted({"events": [{"name": "Goa trip", "with_whom": ["Rahul"],
                                     "where": "Goa", "when": "June"}],
                         "topics": ["travel plans"]}, "Rahul")
    payload = store.graph_payload()
    types = {n["type"] for n in payload["nodes"]}
    assert "event" in types and "topic" in types
