"""Tests for usage/cost tracking, per-app recipes, and the dashboard endpoints."""
from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from fastapi.testclient import TestClient

from app import agent
from app.agent import CompletionResult
from app.main import app
from app.recipes import recipe_for
from app.usage import estimate_cost_usd, tracker

client = TestClient(app)


def test_cost_estimate_by_model():
    # 1M input + 1M output at the haiku rate (1, 5) = 6.0
    assert round(estimate_cost_usd("claude-haiku-4-5", 1_000_000, 1_000_000), 2) == 6.0
    # sonnet (3, 15) = 18.0
    assert round(estimate_cost_usd("claude-sonnet-5", 1_000_000, 1_000_000), 2) == 18.0


def test_tracker_records_per_device():
    tracker.record("dev-A", "claude-haiku-4-5", 100, 50)
    tracker.record("dev-A", "claude-haiku-4-5", 100, 50)
    u = tracker.for_device("dev-A")
    assert u.requests == 2
    assert u.input_tokens == 200 and u.output_tokens == 100
    assert u.est_cost_usd > 0
    # other device is isolated
    assert tracker.for_device("dev-B").requests == 0


def test_recipes():
    assert "WhatsApp" in (recipe_for("com.whatsapp") or "")
    assert "Chrome" in (recipe_for("com.android.chrome") or "")
    assert recipe_for("com.unknown.app") is None
    assert recipe_for(None) is None


def test_step_records_usage(monkeypatch):
    def fake(model, system, user_turn, screenshot_b64):
        return CompletionResult(text='{"type": "wait"}', usage=(30, 8))

    monkeypatch.setattr(agent, "_complete", fake)
    req = {
        "device_id": "usage-dev-1",
        "goal": "काहीतरी",
        "step_index": 0,
        "observation": {"nodes": [{"id": 1, "text": "X", "clickable": True}]},
    }
    r = client.post("/agent/step", json=req)
    assert r.status_code == 200

    r2 = client.get("/usage/usage-dev-1")
    assert r2.status_code == 200
    body = r2.json()
    assert body["input_tokens"] == 30
    assert body["output_tokens"] == 8
    assert body["requests"] == 1


def test_usage_and_dashboard_endpoints():
    assert client.get("/usage").status_code == 200
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Manu" in r.text
