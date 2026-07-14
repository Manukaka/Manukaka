"""The brain: turn an observation + goal into the next Action via Claude.

The actual network call is isolated in `_complete` so tests can monkeypatch it
without hitting the API.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from .config import settings
from .prompts import build_user_turn, system_prompt
from .schema import Action, ActionType, Observation, StepResponse

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

# Signals that a routine text-only step should escalate to the smarter model.
_HARD_KEYWORDS = ("pay", "payment", "transfer", "upi", "delete", "book", "buy", "order")


def _looks_stuck(history: List[str]) -> bool:
    """Heuristic: two trailing failures, or the same action tried three+ times."""
    if not history:
        return False
    tail = history[-2:]
    if len(tail) == 2 and all(("fail" in h or "not found" in h) for h in tail):
        return True
    # same leading token (the action verb) repeated a lot
    verbs = [h.split()[0] for h in history if h.split()]
    if verbs and verbs.count(verbs[-1]) >= 3 and history[-1].startswith(verbs[-1]):
        # only treat as stuck if those repeats weren't clearly progressing
        recent = [h for h in history[-3:] if h.startswith(verbs[-1])]
        if len(recent) >= 3:
            return True
    return False


def choose_model(obs: Observation, goal: str, step_index: int) -> str:
    """Cheap-first model routing. Escalate for vision or high-stakes/complex steps."""
    if obs.screenshot_b64:
        return settings.model_smart
    lowered = goal.lower()
    if any(k in lowered for k in _HARD_KEYWORDS):
        return settings.model_smart
    if step_index >= 12:  # long tasks tend to need stronger reasoning to unstick
        return settings.model_smart
    return settings.model_fast


def _complete(model: str, system: str, user_turn: str, screenshot_b64: Optional[str]) -> str:
    """Single Claude call. Returns the raw text response. Monkeypatched in tests."""
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)

    content: list = [{"type": "text", "text": user_turn}]
    if screenshot_b64:
        content.insert(
            0,
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64},
            },
        )

    msg = client.messages.create(
        model=model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        # Cache the large, static system prompt to cut cost on every step.
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": content}],
    )
    return "".join(block.text for block in msg.content if getattr(block, "type", None) == "text")


def _parse_action(raw: str) -> Action:
    match = _JSON_RE.search(raw or "")
    if not match:
        return Action(
            type=ActionType.ask_user,
            say="माफ करा, मला नीट समजलं नाही. पुन्हा सांगाल का?",
        )
    try:
        data = json.loads(match.group(0))
        return Action.model_validate(data)
    except Exception:
        return Action(
            type=ActionType.ask_user,
            say="माफ करा, मला नीट समजलं नाही. पुन्हा सांगाल का?",
        )


def decide(
    goal: str,
    obs: Observation,
    history: List[str],
    step_index: int,
    user_reply: Optional[str],
) -> StepResponse:
    # Budget guard: stop cleanly instead of running up cost forever.
    if step_index >= settings.max_steps_per_task:
        return StepResponse(
            action=Action(
                type=ActionType.done,
                say="हे काम खूप मोठं झालं आहे, म्हणून मी थांबतो. काय पुढे करायचं ते सांगा.",
            ),
            model_used="none",
            forced_stop=True,
        )

    model = choose_model(obs, goal, step_index)
    if _looks_stuck(history):
        # Escalate reasoning and tell Claude to change tactics or ask the user.
        model = settings.model_smart
        history = history + [
            "NOTE: recent attempts failed or repeated. Change approach, swipe to reveal "
            "more, or use ask_user — do NOT repeat the same failing action."
        ]

    user_turn = build_user_turn(goal, obs, history, user_reply)
    raw = _complete(model, system_prompt(), user_turn, obs.screenshot_b64)
    action = _parse_action(raw)
    return StepResponse(action=action, model_used=model)
