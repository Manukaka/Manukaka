"""FastAPI app: the mobile client's only entry point.

The Anthropic key never leaves this server. The phone POSTs the current screen +
the user's goal to /agent/step and gets back a single validated action.
"""
from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from . import agent
from .config import settings
from .ratelimit import RateLimiter
from .schema import StepRequest, StepResponse

app = FastAPI(title="Manu Mobile Backend", version="0.1.0")

_limiter = RateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "has_api_key": bool(settings.anthropic_api_key),
        "model_fast": settings.model_fast,
        "model_smart": settings.model_smart,
    }


def _check_auth(x_manu_key: str | None) -> None:
    if settings.app_shared_secret and x_manu_key != settings.app_shared_secret:
        raise HTTPException(status_code=401, detail="bad or missing X-Manu-Key")


@app.post("/agent/step", response_model=StepResponse)
def agent_step(req: StepRequest, x_manu_key: str | None = Header(default=None)) -> StepResponse:
    _check_auth(x_manu_key)

    if not _limiter.allow(req.device_id):
        raise HTTPException(status_code=429, detail="rate limit exceeded, slow down")

    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="server missing ANTHROPIC_API_KEY")

    return agent.decide(
        goal=req.goal,
        obs=req.observation,
        history=req.history,
        step_index=req.step_index,
        user_reply=req.user_reply,
    )


@app.exception_handler(Exception)
def _unhandled(_request, exc: Exception) -> JSONResponse:  # pragma: no cover
    return JSONResponse(status_code=500, content={"detail": f"internal error: {exc}"})
