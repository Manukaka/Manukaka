"""Runtime configuration, read from environment variables.

Nothing secret is hard-coded. The Anthropic API key lives only on the server,
never in the mobile APK.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional in production
    pass


@dataclass(frozen=True)
class Settings:
    # --- Anthropic ---
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Model routing: a cheap model handles routine steps, an escalation model
    # handles hard reasoning / vision. Override via env for cost tuning.
    model_fast: str = os.getenv("MANU_MODEL_FAST", "claude-haiku-4-5-20251001")
    model_smart: str = os.getenv("MANU_MODEL_SMART", "claude-sonnet-5")

    max_tokens: int = int(os.getenv("MANU_MAX_TOKENS", "1024"))
    temperature: float = float(os.getenv("MANU_TEMPERATURE", "0.2"))

    # --- Safety / cost caps ---
    # Max agent steps the backend will serve for a single task before forcing a stop.
    max_steps_per_task: int = int(os.getenv("MANU_MAX_STEPS", "40"))

    # Per-device rate limit (requests per rolling window).
    rate_limit_requests: int = int(os.getenv("MANU_RATE_LIMIT_REQUESTS", "120"))
    rate_limit_window_seconds: int = int(os.getenv("MANU_RATE_LIMIT_WINDOW", "60"))

    # Optional shared secret the app must send in the `X-Manu-Key` header.
    # Empty string disables the check (fine for local dev only).
    app_shared_secret: str = os.getenv("MANU_APP_SHARED_SECRET", "")


settings = Settings()
