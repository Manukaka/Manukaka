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
def clean_state():
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
