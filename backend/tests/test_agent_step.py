"""Unit tests for the agent proxy — no network, Claude is monkeypatched."""
from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import pytest
from fastapi.testclient import TestClient

from app import agent
from app.config import settings
from app.main import app
from app.schema import ActionType, Observation

client = TestClient(app)


SAMPLE_REQUEST = {
    "device_id": "test-device-1",
    "goal": "WhatsApp उघड",
    "step_index": 0,
    "history": [],
    "observation": {
        "app_package": "com.sec.android.app.launcher",
        "screen_title": "Home",
        "nodes": [
            {"id": 1, "text": "Phone", "cls": "TextView", "clickable": True},
            {"id": 2, "text": "Settings", "cls": "TextView", "clickable": True},
        ],
    },
}


def _fake_complete(action_json: str):
    def _inner(model, system, user_turn, screenshot_b64):
        return action_json

    return _inner


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_step_returns_schema_valid_action(monkeypatch):
    monkeypatch.setattr(
        agent, "_complete", _fake_complete('{"type": "open_app", "app": "WhatsApp"}')
    )
    r = client.post("/agent/step", json=SAMPLE_REQUEST)
    assert r.status_code == 200
    body = r.json()
    assert body["action"]["type"] == "open_app"
    assert body["action"]["app"] == "WhatsApp"
    assert body["model_used"]  # a model name was chosen


def test_step_tolerates_markdown_wrapped_json(monkeypatch):
    wrapped = 'Sure!\n```json\n{"type": "tap", "node_id": 2}\n```'
    monkeypatch.setattr(agent, "_complete", _fake_complete(wrapped))
    r = client.post("/agent/step", json=SAMPLE_REQUEST)
    assert r.status_code == 200
    assert r.json()["action"]["node_id"] == 2


def test_bad_model_output_becomes_ask_user(monkeypatch):
    monkeypatch.setattr(agent, "_complete", _fake_complete("not json at all"))
    r = client.post("/agent/step", json=SAMPLE_REQUEST)
    assert r.status_code == 200
    assert r.json()["action"]["type"] == "ask_user"


def test_budget_guard_forces_stop(monkeypatch):
    monkeypatch.setattr(agent, "_complete", _fake_complete('{"type": "wait"}'))
    req = dict(SAMPLE_REQUEST, step_index=settings.max_steps_per_task + 1)
    r = client.post("/agent/step", json=req)
    assert r.status_code == 200
    body = r.json()
    assert body["forced_stop"] is True
    assert body["action"]["type"] == "done"


def test_model_routing_escalates_on_screenshot():
    obs = Observation(screenshot_b64="deadbeef")
    assert agent.choose_model(obs, "read this", 0) == settings.model_smart


def test_model_routing_escalates_on_high_stakes_goal():
    obs = Observation()
    assert agent.choose_model(obs, "send UPI payment to Rahul", 0) == settings.model_smart


def test_model_routing_uses_fast_by_default():
    obs = Observation(nodes=[])
    assert agent.choose_model(obs, "open settings", 0) == settings.model_fast


def test_rate_limiter_unit():
    from app.ratelimit import RateLimiter

    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.allow("d") is True
    assert rl.allow("d") is True
    assert rl.allow("d") is False
    assert rl.allow("other") is True  # per-device, not global


def test_rate_limit_endpoint(monkeypatch):
    monkeypatch.setattr(agent, "_complete", _fake_complete('{"type": "wait"}'))
    from app import main
    from app.ratelimit import RateLimiter

    monkeypatch.setattr(main, "_limiter", RateLimiter(max_requests=3, window_seconds=60))
    req = dict(SAMPLE_REQUEST, device_id="rl-device")
    codes = [client.post("/agent/step", json=req).status_code for _ in range(5)]
    assert 429 in codes
