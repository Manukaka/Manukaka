"""Backend tests with the Claude call mocked — no API key or network needed."""
import base64
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Use a throwaway cache DB so tests don't touch a real one.
os.environ.setdefault("SATYA_CACHE_DB", os.path.join(tempfile.gettempdir(), "satya_test_cache.sqlite3"))

from app import cache, claude_client  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

FAKE_VERDICT = {
    "verdict": "FALSE",
    "confidence": "high",
    "claim": "The government is depositing Rs 15 lakh in every bank account.",
    "summary": "Yeh dava jhootha hai. No such scheme exists.",
    "evidence": ["PIB Fact Check has repeatedly debunked this forward."],
    "sources": [{"title": "PIB Fact Check", "url": "https://pib.gov.in", "publisher": "PIB"}],
}


@pytest.fixture(autouse=True)
def _clear_cache(tmp_path, monkeypatch):
    db = tmp_path / "cache.sqlite3"
    monkeypatch.setattr(cache.config, "CACHE_DB", str(db))
    yield


@pytest.fixture
def mock_check(monkeypatch):
    calls = {"n": 0}

    def fake_check(kind, **kwargs):
        calls["n"] += 1
        from app import verdict
        return verdict.decorate(dict(FAKE_VERDICT))

    monkeypatch.setattr(claude_client, "check", fake_check)
    return calls


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_taxonomy_has_five_verdicts():
    r = client.get("/api/taxonomy")
    assert r.status_code == 200
    assert len(r.json()["verdicts"]) == 5


def test_check_text_returns_decorated_verdict(mock_check):
    r = client.post("/v1/check/text", json={"text": "Govt is giving Rs 15 lakh to all!", "lang": "hinglish"})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "FALSE"
    assert body["verdict_label_hi"] == "झूठ"
    assert body["verdict_color"] == "#D32F2F"
    assert body["cached"] is False


def test_identical_forward_is_served_from_cache(mock_check):
    payload = {"text": "  Govt is giving Rs 15 LAKH to ALL!! ", "lang": "en"}
    first = client.post("/v1/check/text", json=payload)
    # Whitespace/case differences should still hit the same cache key.
    second = client.post("/v1/check/text", json={"text": "govt is giving rs 15 lakh to all!!", "lang": "en"})
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert mock_check["n"] == 1  # model called only once


def test_image_rejects_bad_type(mock_check):
    r = client.post(
        "/v1/check/image",
        files={"file": ("x.txt", b"hello", "text/plain")},
        data={"lang": "en"},
    )
    assert r.status_code == 415


def test_image_accepts_png(mock_check):
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    r = client.post(
        "/v1/check/image",
        files={"file": ("x.png", png_bytes, "image/png")},
        data={"lang": "hi"},
    )
    assert r.status_code == 200
    assert r.json()["verdict"] == "FALSE"


def test_text_check_error_maps_to_422(monkeypatch):
    def boom(kind, **kwargs):
        raise RuntimeError("refused")

    monkeypatch.setattr(claude_client, "check", boom)
    r = client.post("/v1/check/text", json={"text": "something", "lang": "en"})
    assert r.status_code == 422
