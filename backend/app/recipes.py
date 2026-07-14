"""Small per-app hints injected into the prompt when we recognise the foreground app.

These make common flows more reliable and cheaper (fewer wrong taps) without
hard-coding behaviour — they're guidance the model may use, not a script.
"""
from __future__ import annotations

# Keyed by a substring of the app package. First match wins.
RECIPES = {
    "com.whatsapp": (
        "WhatsApp: to message someone, tap the search icon, type the contact name, "
        "tap the contact, tap the 'Type a message' box at the bottom, type, then tap "
        "the send (paper-plane) button — remember to confirm before sending."
    ),
    "com.android.chrome": (
        "Chrome: the bar at the top is both address and search — tap it, type the "
        "query, and open the top result. Read answers back with read_aloud."
    ),
    "com.google.android.apps.messaging": (
        "Messages: tap 'Start chat', pick the contact, type in the text box, then tap "
        "send — confirm before sending."
    ),
    "com.android.settings": (
        "Settings: use the search bar at the very top to jump to any setting quickly."
    ),
    "dialer": (
        "Phone: search or tap a contact, then tap the green call button — confirm "
        "before calling."
    ),
    "com.samsung.android.app.notes": (
        "Samsung Notes: the note text is on screen; summarise it for the user with "
        "read_aloud."
    ),
}


def recipe_for(app_package: str | None) -> str | None:
    if not app_package:
        return None
    for key, hint in RECIPES.items():
        if key in app_package:
            return hint
    return None
