import threading

import pytest
from fastapi.testclient import TestClient

from assistant import server
from assistant.ingestion import runner
from assistant.llm import ollama_client


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def clean_state(tmp_data_dirs):
    # tmp_data_dirs keeps side effects (chat.db, profile files) out of the repo
    yield
    runner.GPU_BUSY.clear()
    server.STATE.finish()


def test_health_reports_degraded_but_never_crashes(client, monkeypatch):
    monkeypatch.setattr(ollama_client, "is_up", lambda: False)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ollama"] is False
    assert body["model_available"] is False
    assert body["ingesting"] is False
    assert isinstance(body["chunks"], int)


def test_chat_blocked_only_while_gpu_is_busy(client, monkeypatch):
    monkeypatch.setattr(ollama_client, "is_up", lambda: True)
    monkeypatch.setattr(ollama_client, "chat_stream", lambda messages: iter(["ok"]))

    runner.GPU_BUSY.set()
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 409

    runner.GPU_BUSY.clear()
    # CPU-only ingest phases must not block chat
    assert server.STATE.try_start()
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 200


def test_chat_requires_ollama(client, monkeypatch):
    monkeypatch.setattr(ollama_client, "is_up", lambda: False)
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 503


def test_chat_rejects_empty_message(client, monkeypatch):
    monkeypatch.setattr(ollama_client, "is_up", lambda: True)
    assert client.post("/api/chat", json={"message": "   "}).status_code == 400


def test_chat_streams_sse_deltas(client, monkeypatch):
    monkeypatch.setattr(ollama_client, "is_up", lambda: True)
    monkeypatch.setattr(ollama_client, "chat_stream",
                        lambda messages: iter(["Namaste", "!"]))
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert '"delta": "Namaste"' in r.text
    assert '"done": true' in r.text


def test_chat_emits_sources_event_before_done(client, monkeypatch):
    from assistant.rag import retriever
    hit = {"text": "excerpt", "score": 1.0,
           "metadata": {"contact": "Aai", "source_type": "whatsapp",
                        "source_file": "chat.txt", "start_ts": 0, "end_ts": 0}}
    monkeypatch.setattr(ollama_client, "is_up", lambda: True)
    monkeypatch.setattr(ollama_client, "chat_stream", lambda messages: iter(["hi [1]"]))
    monkeypatch.setattr(retriever, "retrieve", lambda q, h=None: [hit])

    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 200
    assert '"sources"' in r.text
    assert '"n": 1' in r.text
    assert r.text.index('"sources"') < r.text.index('"done"')


def test_chat_persists_turn_to_chatlog(client, monkeypatch, tmp_data_dirs):
    from assistant.memory import chatlog
    monkeypatch.setattr(ollama_client, "is_up", lambda: True)
    monkeypatch.setattr(ollama_client, "chat_stream", lambda messages: iter(["uttar"]))
    client.post("/api/chat", json={"message": "prashna"})
    msgs = chatlog.recent()
    assert [m["content"] for m in msgs] == ["prashna", "uttar"]


def test_history_endpoint_returns_persisted_messages(client, tmp_data_dirs):
    from assistant.memory import chatlog
    chatlog.append("user", "hello")
    chatlog.append("assistant", "namaste")
    body = client.get("/api/history").json()
    assert body["messages"] == [{"role": "user", "content": "hello"},
                                {"role": "assistant", "content": "namaste"}]


def test_conversations_crud_endpoints(client, tmp_data_dirs):
    created = client.post("/api/conversations", json={"title": "Goa trip"}).json()
    cid = created["id"]
    assert created["title"] == "Goa trip"

    listing = client.get("/api/conversations").json()["conversations"]
    assert any(c["id"] == cid and c["title"] == "Goa trip" for c in listing)

    client.post(f"/api/conversations/{cid}/rename", json={"title": "Goa 2026"})
    listing = client.get("/api/conversations").json()["conversations"]
    assert next(c for c in listing if c["id"] == cid)["title"] == "Goa 2026"

    assert client.delete(f"/api/conversations/{cid}").json() == {"ok": True}
    listing = client.get("/api/conversations").json()["conversations"]
    assert all(c["id"] != cid for c in listing)


def test_chat_appends_to_requested_conversation(client, monkeypatch, tmp_data_dirs):
    from assistant.memory import chatlog
    cid = chatlog.create_conversation("thread A")
    monkeypatch.setattr(ollama_client, "is_up", lambda: True)
    monkeypatch.setattr(ollama_client, "chat_stream", lambda messages: iter(["ans"]))

    r = client.post("/api/chat", json={"message": "q", "conv_id": cid})
    assert ('"conv_id": %d' % cid) in r.text
    assert [m["content"] for m in chatlog.recent(conv_id=cid)] == ["q", "ans"]


def test_history_endpoint_scopes_to_conv_id(client, tmp_data_dirs):
    from assistant.memory import chatlog
    a = chatlog.create_conversation("A")
    b = chatlog.create_conversation("B")
    chatlog.append("user", "in A", a)
    chatlog.append("user", "in B", b)
    msgs = client.get(f"/api/history?conv_id={a}").json()["messages"]
    assert [m["content"] for m in msgs] == ["in A"]


def test_upcoming_endpoint(client, tmp_data_dirs):
    from assistant.memory import commitments
    commitments.save([{"what": "pay bill", "due_date": "2030-01-01",
                       "due_text": "1 Jan", "with_whom": ""}])
    body = client.get("/api/upcoming").json()
    assert body["due"][0]["what"] == "pay bill"
    assert body["undated"] == []


def test_contacts_endpoint_aggregates_index_and_profile(client, monkeypatch, tmp_data_dirs):
    from assistant import server
    docs = [
        {"id": "1", "text": "x", "metadata": {"contact": "Rahul", "end_ts": 200.0,
                                              "source_type": "whatsapp"}},
        {"id": "2", "text": "y", "metadata": {"contact": "Rahul", "end_ts": 100.0,
                                              "source_type": "call"}},
        {"id": "3", "text": "z", "metadata": {"contact": "Aai", "end_ts": 50.0,
                                              "source_type": "sms"}},
    ]
    monkeypatch.setattr(server, "_index_docs", lambda: docs)
    monkeypatch.setattr(server.memory_profile, "load_profile", lambda: {
        "people": [{"fact": {"name": "Rahul", "relation": "friend",
                             "notes": "planning Goa trip"}}],
    })
    contacts = client.get("/api/contacts").json()["contacts"]
    assert [c["name"] for c in contacts] == ["Rahul", "Aai"]  # most recent first
    rahul = contacts[0]
    assert rahul["chunks"] == 2
    assert rahul["sources"] == ["call", "whatsapp"]
    assert any("Goa" in f for f in rahul["facts"])


def test_transcripts_list_and_read(client, tmp_data_dirs):
    from assistant import config
    config.TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.TRANSCRIPTS_DIR / "Call with Aai_240513.txt").write_text(
        "[SPEAKER_00] नमस्कार\n[SPEAKER_01] बोला", encoding="utf-8")

    listing = client.get("/api/transcripts").json()["transcripts"]
    assert [t["stem"] for t in listing] == ["Call with Aai_240513"]

    body = client.get("/api/transcripts/Call%20with%20Aai_240513").json()
    assert "नमस्कार" in body["text"]


def test_transcript_traversal_and_missing_are_404(client, tmp_data_dirs):
    assert client.get("/api/transcripts/nope").status_code == 404
    assert client.get("/api/transcripts/..%2F..%2Fconfig").status_code == 404


def test_digest_endpoint_summarizes_recent_chunks(client, monkeypatch):
    import time as _time

    from assistant import server
    now = _time.time()
    docs = [{"id": "1", "text": "Goa trip finalized with Rahul",
             "metadata": {"end_ts": now - 3600}},
            {"id": "2", "text": "ancient news",
             "metadata": {"end_ts": now - 90 * 86400}}]
    seen = {}

    def fake_chat_once(messages):
        seen["prompt"] = messages[-1]["content"]
        return "**Trips**: Goa plan is on."

    monkeypatch.setattr(server, "_index_docs", lambda: docs)
    monkeypatch.setattr(ollama_client, "is_up", lambda: True)
    monkeypatch.setattr(ollama_client, "chat_once", fake_chat_once)

    body = client.post("/api/digest", json={"days": 7}).json()
    assert body["digest"] == "**Trips**: Goa plan is on."
    assert "Goa trip finalized" in seen["prompt"]
    assert "ancient news" not in seen["prompt"]  # outside the window


def test_digest_with_no_recent_data(client, monkeypatch):
    from assistant import server
    monkeypatch.setattr(server, "_index_docs", lambda: [])
    monkeypatch.setattr(ollama_client, "is_up", lambda: True)
    body = client.post("/api/digest", json={"days": 7}).json()
    assert body["digest"] is None
    assert "No conversations" in body["message"]


def test_digest_requires_ollama(client, monkeypatch):
    monkeypatch.setattr(ollama_client, "is_up", lambda: False)
    assert client.post("/api/digest", json={"days": 7}).status_code == 503


def test_ingest_rejects_concurrent_runs(client, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(runner, "run_ingest", lambda status: release.wait(timeout=5))

    assert client.post("/api/ingest").json() == {"started": True}
    assert client.post("/api/ingest").status_code == 409  # already running
    assert client.get("/api/status").json()["running"] is True

    release.set()
    for _ in range(100):
        if not server.STATE.running:
            break
        threading.Event().wait(0.02)
    assert server.STATE.running is False
