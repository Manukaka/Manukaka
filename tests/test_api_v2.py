"""Endpoint tests against fixture graph data. Ollama/whisper are never invoked:
chat needs Ollama up, so we only test the offline graph/photo endpoints here."""
from datetime import datetime

from fastapi.testclient import TestClient

from assistant import config, server
from assistant.graph import store
from assistant.ingestion.photos import PhotoRecord


def _seed():
    store.upsert_node("person", "Me")
    pid_node = store.upsert_node("person", "Aai", {"msg_count": 30})
    store.bump_edge(store.node_id("person", "Me"), pid_node, "talks_with", 30)
    store.upsert_session("whatsapp", "Aai", datetime(2024, 1, 1).timestamp(),
                         datetime(2024, 1, 1).timestamp(), 30, "Aai.txt")
    rec = PhotoRecord(rel_path="x.jpg", file_size=1, mtime=1.0,
                      taken_ts=datetime(2024, 6, 1).timestamp(), people=["Aai"],
                      lat=15.5, lon=73.7)
    photo_id = store.upsert_photo(rec, {"name": "Baga", "admin": "Goa", "cc": "IN",
                                        "label": "Baga, Goa, India"})
    store.link_photo_person(photo_id, pid_node)
    store.set_caption(photo_id, "family at the beach")
    return pid_node, photo_id


def test_graph_endpoint(tmp_data):
    _seed()
    c = TestClient(server.app)
    data = c.get("/api/graph").json()
    assert any(n["name"] == "Aai" for n in data["nodes"])
    assert any(l["type"] == "talks_with" for l in data["links"])


def test_timeline_and_people(tmp_data):
    _seed()
    c = TestClient(server.app)
    tl = c.get("/api/timeline?limit=10").json()
    assert tl["items"] and any(i["type"] == "photo" for i in tl["items"])
    people = c.get("/api/people").json()
    assert any(p["name"] == "Aai" for p in people)


def test_person_and_places(tmp_data):
    pid, _ = _seed()
    c = TestClient(server.app)
    person = c.get(f"/api/person/{pid}").json()
    assert person["name"] == "Aai" and person["photos"]
    assert c.get("/api/person/deadbeef").status_code == 404
    places = c.get("/api/places").json()
    assert places[0]["name"] == "Baga, Goa, India"


def test_thumb_path_containment(tmp_data):
    _seed()
    c = TestClient(server.app)
    # forged id with traversal must not escape the thumbs dir
    assert c.get("/api/thumb/..%2f..%2fetc%2fpasswd").status_code in (404, 400)
    # missing thumb file → 404
    assert c.get("/api/thumb/nonexistent").status_code == 404


def test_photo_endpoint_serves_real_file(tmp_data):
    _, photo_id = _seed()
    # create the actual photo file the row points to
    (config.INGEST_PHOTOS / "x.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    c = TestClient(server.app)
    assert c.get(f"/api/photo/{photo_id}").status_code == 200
    assert c.get("/api/photo/missing").status_code == 404
