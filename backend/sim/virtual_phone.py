"""A tiny scripted 'phone' plus a runner that mirrors the Kotlin AgentLoop.

This lets us exercise the whole observe -> decide -> act loop without a device:
the runner asks the real backend (`agent.decide`) for the next action, applies it to
an in-memory screen model, and repeats until `done`, `ask_user` runs out, or a step
budget is hit. In tests the Claude call is either mocked (deterministic, no key) or
real (opt-in, `MANU_LIVE=1`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app import agent
from app.schema import Action, ActionType, Observation, UiNode


@dataclass
class Screen:
    key: str
    app_package: str
    title: str
    # each element: (text, clickable, editable)
    elements: List[tuple]


@dataclass
class Scenario:
    name: str
    goal: str
    initial: str
    screens: Dict[str, Screen]
    # (phone, action) -> next screen key (or None to stay put)
    transition: Callable[["VirtualPhone", Action], Optional[str]]
    scripted_reply: Optional[str] = None  # answer used if the agent calls ask_user


class VirtualPhone:
    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.state = scenario.initial
        self.typed: List[str] = []
        self.sent = False
        self.spoken: List[str] = []

    @property
    def screen(self) -> Screen:
        return self.scenario.screens[self.state]

    def observe(self) -> Observation:
        s = self.screen
        nodes = [
            UiNode(
                id=i + 1,
                text=text,
                desc=None,
                cls="View",
                clickable=clickable,
                editable=editable,
            )
            for i, (text, clickable, editable) in enumerate(s.elements)
        ]
        return Observation(app_package=s.app_package, screen_title=s.title, nodes=nodes)

    def node_text(self, node_id: Optional[int]) -> Optional[str]:
        if node_id is None:
            return None
        s = self.screen
        if 1 <= node_id <= len(s.elements):
            return s.elements[node_id - 1][0]
        return None

    def apply(self, action: Action) -> None:
        if action.type == ActionType.type_text and action.text:
            self.typed.append(action.text)
        nxt = self.scenario.transition(self, action)
        if nxt is not None:
            self.state = nxt


@dataclass
class RunResult:
    done: bool
    steps: int
    spoken: List[str] = field(default_factory=list)
    typed: List[str] = field(default_factory=list)
    sent: bool = False
    last_action: Optional[str] = None


# Words the runner accepts as "yes" — matches the Kotlin AgentLoop set.
_YES = "yes"


def run_scenario(scenario: Scenario, max_steps: int = 25) -> RunResult:
    """Drive one scenario to completion through the real `agent.decide`."""
    phone = VirtualPhone(scenario)
    history: List[str] = []
    pending_reply: Optional[str] = None
    last = None

    for step in range(max_steps):
        obs = phone.observe()
        resp = agent.decide(
            goal=scenario.goal,
            obs=obs,
            history=history,
            step_index=step,
            user_reply=pending_reply,
        )
        action = resp.action
        pending_reply = None
        last = action.type.value

        # Auto-confirm risky actions (a human would say "हो").
        if action.needs_confirmation:
            history.append(f"user confirmed: {action.say}")

        if action.type == ActionType.done:
            if action.say:
                phone.spoken.append(action.say)
            return RunResult(True, step + 1, phone.spoken, phone.typed, phone.sent, last)

        if action.type == ActionType.ask_user:
            if action.say:
                phone.spoken.append(action.say)
            pending_reply = scenario.scripted_reply or _YES
            history.append(f"asked: {action.say} -> {pending_reply}")
            continue

        if action.type == ActionType.read_aloud:
            if action.say:
                phone.spoken.append(action.say)
            history.append(f"read_aloud: {(action.say or '')[:40]}")
            continue

        # Movement / interaction actions mutate the phone.
        phone.apply(action)
        history.append(_describe(action, phone))

    return RunResult(False, max_steps, phone.spoken, phone.typed, phone.sent, last)


def _describe(action: Action, phone: VirtualPhone) -> str:
    t = action.type.value
    if action.type == ActionType.open_app:
        return f"open_app {action.app}"
    if action.type == ActionType.tap:
        return f"tap {action.node_id} ({phone.node_text(action.node_id)})"
    if action.type == ActionType.type_text:
        return f"type '{(action.text or '')[:20]}'"
    if action.type == ActionType.swipe:
        return f"swipe {action.direction}"
    return t
