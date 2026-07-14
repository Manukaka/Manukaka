"""FastAPI app: the mobile client's only entry point.

The Anthropic key never leaves this server. The phone POSTs the current screen +
the user's goal to /agent/step and gets back a single validated action.
"""
from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from . import agent
from .config import settings
from .ratelimit import RateLimiter
from .schema import StepRequest, StepResponse
from .usage import tracker

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
        device_id=req.device_id,
    )


def _usage_dict(u) -> dict:
    return {
        "requests": u.requests,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "est_cost_usd": round(u.est_cost_usd, 4),
    }


@app.get("/usage")
def usage_all() -> dict:
    """Token & estimated-cost totals, plus a per-device breakdown."""
    return {
        "totals": _usage_dict(tracker.totals()),
        "devices": {d: _usage_dict(u) for d, u in tracker.snapshot().items()},
        "note": "cost is an estimate from an editable price table (app/usage.py)",
    }


@app.get("/usage/{device_id}")
def usage_device(device_id: str) -> dict:
    return {"device_id": device_id, **_usage_dict(tracker.for_device(device_id))}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    t = tracker.totals()
    rows = "".join(
        f"<tr><td>{d}</td><td>{u.requests}</td><td>{u.input_tokens:,}</td>"
        f"<td>{u.output_tokens:,}</td><td>${u.est_cost_usd:.4f}</td></tr>"
        for d, u in sorted(tracker.snapshot().items())
    ) or "<tr><td colspan='5'>No usage yet.</td></tr>"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Manu — usage</title>
<style>
 body{{font-family:system-ui,Arial;margin:2rem;background:#faf9fd;color:#1c1b1f}}
 h1{{color:#6750A4}} table{{border-collapse:collapse;width:100%;max-width:820px}}
 th,td{{border-bottom:1px solid #ddd;padding:.55rem .8rem;text-align:right}}
 th:first-child,td:first-child{{text-align:left}} thead{{background:#eee}}
 .tot{{font-weight:700}} .note{{color:#777;font-size:.85rem;margin-top:1rem}}
</style></head><body>
<h1>🪷 Manu — usage &amp; estimated cost</h1>
<table>
 <thead><tr><th>Device</th><th>Requests</th><th>Input tok</th><th>Output tok</th><th>Est. cost</th></tr></thead>
 <tbody>{rows}</tbody>
 <tfoot><tr class="tot"><td>TOTAL</td><td>{t.requests}</td><td>{t.input_tokens:,}</td>
  <td>{t.output_tokens:,}</td><td>${t.est_cost_usd:.4f}</td></tr></tfoot>
</table>
<p class="note">Cost is an estimate from an editable price table in
 <code>app/usage.py</code> — adjust it to match current Anthropic pricing.</p>
</body></html>"""


@app.exception_handler(Exception)
def _unhandled(_request, exc: Exception) -> JSONResponse:  # pragma: no cover
    return JSONResponse(status_code=500, content={"detail": f"internal error: {exc}"})
