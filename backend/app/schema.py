"""Request/response contracts shared with the Android app.

The action schema is the heart of the agent: Claude looks at the current screen
(an accessibility-tree observation) plus the user's goal, and returns exactly one
`Action` telling the phone what to do next. The app executes it and reports back
the new observation, looping until `done` or `ask_user`.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    open_app = "open_app"          # launch an app by human name (e.g. "WhatsApp")
    tap = "tap"                    # tap a node from the observation (by node_id)
    type_text = "type_text"        # type into the currently focused / last-tapped field
    swipe = "swipe"                # scroll/swipe in a direction
    back = "back"                  # system Back
    home = "home"                  # system Home
    read_aloud = "read_aloud"      # speak text to the user (does not end the task)
    ask_user = "ask_user"          # pause and ask the user a question / confirmation
    wait = "wait"                  # wait for the screen to settle, then re-observe
    done = "done"                  # the task is complete


class SwipeDirection(str, Enum):
    up = "up"
    down = "down"
    left = "left"
    right = "right"


class UiNode(BaseModel):
    """One interactable element from the Android accessibility tree."""

    id: int
    text: Optional[str] = None
    desc: Optional[str] = Field(default=None, description="contentDescription")
    cls: Optional[str] = Field(default=None, description="short class name, e.g. Button")
    clickable: bool = False
    editable: bool = False


class Observation(BaseModel):
    """What the phone currently sees."""

    app_package: Optional[str] = None
    screen_title: Optional[str] = None
    nodes: List[UiNode] = Field(default_factory=list)
    # Optional base64 PNG for the vision fallback (kept out of the cheap text path).
    screenshot_b64: Optional[str] = None


class StepRequest(BaseModel):
    device_id: str = Field(..., description="stable per-install id, for rate limiting")
    goal: str = Field(..., description="the user's spoken instruction, verbatim")
    observation: Observation
    step_index: int = 0
    # Compact history of previous actions this task, so Claude doesn't loop.
    history: List[str] = Field(default_factory=list)
    # If the user just answered an ask_user prompt, their reply goes here.
    user_reply: Optional[str] = None


class Action(BaseModel):
    type: ActionType
    # Union-ish payload — only the fields relevant to `type` are populated.
    app: Optional[str] = None
    node_id: Optional[int] = None
    text: Optional[str] = None
    direction: Optional[SwipeDirection] = None
    # `say` is spoken to the user for read_aloud / ask_user / done.
    say: Optional[str] = None
    # Set True when the action has real-world consequences (send/pay/delete) and
    # the app must get a spoken "yes" before executing.
    needs_confirmation: bool = False


class StepResponse(BaseModel):
    action: Action
    model_used: str
    # True when the backend stopped the loop for safety/budget reasons.
    forced_stop: bool = False
