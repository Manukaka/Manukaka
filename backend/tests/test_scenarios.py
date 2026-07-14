"""End-to-end-ish scenario tests for the four MVP capabilities.

The Kotlin app can't run here, so `sim.virtual_phone` mirrors its observe -> decide
-> act loop against a scripted screen model. Two modes:

  * default (no key): Claude is replaced by a deterministic `mock_complete`, proving
    the whole loop (agent.decide -> parse -> harness -> transitions) reaches `done`.
  * live (MANU_LIVE=1 + ANTHROPIC_API_KEY): the exact same scenarios run through the
    real model, so you can confirm the prompt actually elicits the right actions.
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import pytest

from app import agent
from app.schema import Action
from sim.virtual_phone import Scenario, Screen, run_scenario

# --------------------------------------------------------------------------- #
# Scenario definitions (realistic-ish screens shared by mock and live modes)   #
# --------------------------------------------------------------------------- #


def _settings() -> Scenario:
    screens = {
        "home": Screen("home", "com.sec.android.app.launcher", "Home",
                       [("Phone", True, False), ("Settings", True, False), ("Chrome", True, False)]),
        "settings": Screen("settings", "com.android.settings", "Settings",
                            [("Network & internet", True, False), ("Battery", True, False)]),
    }

    def transition(phone, action: Action):
        if action.type.value == "open_app" and "settings" in (action.app or "").lower():
            return "settings"
        return None

    return Scenario("open_settings", "Settings उघड", "home", screens, transition)


def _whatsapp() -> Scenario:
    screens = {
        "home": Screen("home", "com.sec.android.app.launcher", "Home",
                       [("Phone", True, False), ("WhatsApp", True, False)]),
        "wa_main": Screen("wa_main", "com.whatsapp", "WhatsApp",
                          [("Search", True, False), ("Chats", False, False)]),
        "wa_search": Screen("wa_search", "com.whatsapp", "WhatsApp Search",
                            [("Search name", False, True)]),
        "wa_results": Screen("wa_results", "com.whatsapp", "WhatsApp Search",
                             [("आई", True, False), ("बाबा", True, False)]),
        "wa_chat": Screen("wa_chat", "com.whatsapp", "आई",
                          [("Type a message", False, True)]),
        "wa_chat_typed": Screen("wa_chat_typed", "com.whatsapp", "आई",
                                [("Type a message", False, True), ("Send", True, False)]),
        "wa_sent": Screen("wa_sent", "com.whatsapp", "आई",
                          [("hello aai", False, False), ("Type a message", False, True)]),
    }

    def transition(phone, action: Action):
        st = phone.state
        txt = (phone.node_text(action.node_id) or "").lower()
        if action.type.value == "open_app" and "whatsapp" in (action.app or "").lower():
            return "wa_main"
        if st == "wa_main" and action.type.value == "tap" and "search" in txt:
            return "wa_search"
        if st == "wa_search" and action.type.value == "type_text":
            return "wa_results"
        if st == "wa_results" and action.type.value == "tap" and "आई" in (phone.node_text(action.node_id) or ""):
            return "wa_chat"
        if st == "wa_chat" and action.type.value == "type_text":
            return "wa_chat_typed"
        if st == "wa_chat_typed" and action.type.value == "tap" and "send" in txt:
            phone.sent = True
            return "wa_sent"
        return None

    return Scenario("whatsapp_send", "WhatsApp वर आईला मेसेज कर hello aai",
                    "home", screens, transition)


def _web() -> Scenario:
    screens = {
        "home": Screen("home", "com.sec.android.app.launcher", "Home",
                       [("Chrome", True, False)]),
        "chrome": Screen("chrome", "com.android.chrome", "Chrome",
                         [("Search or type URL", True, True)]),
        "chrome_typing": Screen("chrome_typing", "com.android.chrome", "Chrome typing",
                                [("Search or type URL", False, True)]),
        "weather": Screen("weather", "com.android.chrome", "हवामान - Google",
                          [("आज: ३२°C सूर्यप्रकाश", False, False), ("उद्या: ३०°C", False, False)]),
    }

    def transition(phone, action: Action):
        st = phone.state
        if action.type.value == "open_app" and "chrome" in (action.app or "").lower():
            return "chrome"
        if st == "chrome" and action.type.value == "tap":
            return "chrome_typing"
        if st == "chrome_typing" and action.type.value == "type_text":
            return "weather"
        return None

    return Scenario("web_search", "आजचं हवामान शोध आणि सांग", "home", screens, transition)


def _read() -> Scenario:
    screens = {
        "note": Screen("note", "com.samsung.android.app.notes", "Notes",
                       [("उद्या ऑफिसला जायचं आहे", False, False), ("दूध आणायचं", False, False)]),
    }

    def transition(phone, action: Action):
        return None

    return Scenario("read_screen", "स्क्रीनवर काय आहे ते वाच", "note", screens, transition)


ALL_SCENARIOS = {s.name: s for s in (_settings(), _whatsapp(), _web(), _read())}


# --------------------------------------------------------------------------- #
# Deterministic mock policy (stands in for Claude when there's no key)         #
# --------------------------------------------------------------------------- #

def _node_id(user_turn: str, needle: str) -> int | None:
    for line in user_turn.splitlines():
        s = line.strip()
        if s.startswith("[") and needle in s:
            m = re.match(r"\[(\d+)\]", s)
            if m:
                return int(m.group(1))
    return None


def _field(user_turn: str, key: str) -> str:
    m = re.search(rf"{key}: (.+)", user_turn)
    return m.group(1).strip() if m else ""


def mock_complete(model: str, system: str, user_turn: str, screenshot_b64):
    goal = _field(user_turn, "User's instruction").lower()
    has = lambda t: t in user_turn
    app = _field(user_turn, r"app")  # from "app: <pkg> | screen: <title>"

    # ---- read screen ----
    if any(k in goal for k in ("वाच", "read", "काय आहे")):
        if has("read_aloud"):
            return '{"type": "done", "say": "एवढंच होतं."}'
        return '{"type": "read_aloud", "say": "स्क्रीनवर दोन नोंदी आहेत: उद्या ऑफिसला जायचं आणि दूध आणायचं."}'

    # ---- web search ----
    if any(k in goal for k in ("हवामान", "शोध", "search", "weather")):
        if "com.android.chrome" not in user_turn:
            return '{"type": "open_app", "app": "Chrome"}'
        if "Google" in user_turn or "३२" in user_turn:
            if has("read_aloud"):
                return '{"type": "done", "say": "झालं."}'
            return '{"type": "read_aloud", "say": "आज ३२ अंश, सूर्यप्रकाश आहे."}'
        if "typing" in user_turn:
            return '{"type": "type_text", "text": "आजचं हवामान"}'
        nid = _node_id(user_turn, "Search or type URL")
        return f'{{"type": "tap", "node_id": {nid}}}'

    # ---- whatsapp send ---- (use _node_id so goal text like "hello aai" isn't
    # mistaken for on-screen content — _node_id only scans element lines)
    if any(k in goal for k in ("मेसेज", "message", "whatsapp")):
        if "com.whatsapp" not in user_turn:
            return '{"type": "open_app", "app": "WhatsApp"}'
        if _node_id(user_turn, "hello aai") is not None:      # sent message is on screen
            return '{"type": "done", "say": "आईला मेसेज पाठवला."}'
        send_id = _node_id(user_turn, "Send")
        if send_id is not None:
            return f'{{"type": "tap", "node_id": {send_id}, "needs_confirmation": true, "say": "आईला hello aai पाठवू का?"}}'
        contact_id = _node_id(user_turn, "आई")
        if contact_id is not None:                            # results list
            return f'{{"type": "tap", "node_id": {contact_id}}}'
        input_id = _node_id(user_turn, "Type a message")
        if input_id is not None:
            return '{"type": "type_text", "text": "hello aai"}'
        if "WhatsApp Search" in user_turn:                    # search box, no results yet
            return '{"type": "type_text", "text": "आई"}'
        search_id = _node_id(user_turn, "Search")
        return f'{{"type": "tap", "node_id": {search_id}}}'

    # ---- open settings (fallback) ----
    if "com.android.settings" in user_turn:
        return '{"type": "done", "say": "Settings उघडलं."}'
    return '{"type": "open_app", "app": "Settings"}'


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #

@pytest.fixture
def mock_claude(monkeypatch):
    monkeypatch.setattr(agent, "_complete", mock_complete)


def test_open_settings(mock_claude):
    r = run_scenario(ALL_SCENARIOS["open_settings"])
    assert r.done and r.last_action == "done"


def test_whatsapp_send_with_confirm(mock_claude):
    r = run_scenario(ALL_SCENARIOS["whatsapp_send"])
    assert r.done
    assert r.sent is True
    assert any("hello" in t for t in r.typed)


def test_web_search_and_read(mock_claude):
    r = run_scenario(ALL_SCENARIOS["web_search"])
    assert r.done
    assert any("३२" in s for s in r.spoken)


def test_read_screen(mock_claude):
    r = run_scenario(ALL_SCENARIOS["read_screen"])
    assert r.done
    assert r.spoken and any("नोंदी" in s or "ऑफिस" in s for s in r.spoken)


# --------------------------------------------------------------------------- #
# Opt-in live run against the real model                                       #
# --------------------------------------------------------------------------- #

_LIVE = os.getenv("MANU_LIVE") == "1" and os.getenv("ANTHROPIC_API_KEY", "test-key") != "test-key"


@pytest.mark.skipif(not _LIVE, reason="set MANU_LIVE=1 and a real ANTHROPIC_API_KEY to run")
@pytest.mark.parametrize("name", list(ALL_SCENARIOS.keys()))
def test_live_scenarios(name):
    r = run_scenario(ALL_SCENARIOS[name], max_steps=30)
    assert r.done, f"{name} did not complete; last action = {r.last_action}"
