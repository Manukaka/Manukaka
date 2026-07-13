# Manu Mobile — Backend (Claude agent proxy)

A thin FastAPI service that stands between the Android app and the Claude API.
**The Anthropic API key lives only here — never in the APK.** The phone sends the
current screen (accessibility tree) plus the user's spoken instruction; the backend
asks Claude for the single next action and returns it.

## Why a backend at all?
- **Security:** the API key can't be extracted from a shipped APK.
- **Cost control:** model routing (cheap `Haiku` for routine steps, `Sonnet` for
  hard reasoning / vision), prompt caching of the big system prompt, and a hard
  per-task step budget.
- **Rate limiting:** per-device caps so a bug can't run up the bill.

## Run locally
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your real ANTHROPIC_API_KEY in .env
uvicorn app.main:app --host 0.0.0.0 --port 8080
```
Check it: `curl localhost:8080/health`

Try one agent step (fake screen):
```bash
curl -s localhost:8080/agent/step -H 'content-type: application/json' -d '{
  "device_id":"dev1","goal":"Settings उघड","step_index":0,
  "observation":{"screen_title":"Home","nodes":[{"id":1,"text":"Settings","clickable":true}]}
}' | python3 -m json.tool
```

## Tests
```bash
source .venv/bin/activate
python -m pytest tests/ -q     # network is mocked; no API key needed
```

## The action contract (what the app must implement)
See `app/schema.py`. Every step returns one `action`:

| type | payload | app should… |
|---|---|---|
| `open_app` | `app` (name) | launch that app |
| `tap` | `node_id` | tap that node from the observation |
| `type_text` | `text` | type into the focused field |
| `swipe` | `direction` | scroll up/down/left/right |
| `back` / `home` | — | press Back / go Home |
| `read_aloud` | `say` | speak it (task continues) |
| `ask_user` | `say` | speak it, listen, send reply back |
| `wait` | — | pause, re-observe |
| `done` | `say` | speak summary, end task |

`needs_confirmation: true` means the app must get a spoken "yes" before executing
(used for send / call / pay / delete).

## Deploy (cheap options for a global rollout)
Any container host works (Fly.io, Render, Railway, a small VPS). Set the env vars
from `.env.example`, expose port 8080 over HTTPS, and set a strong
`MANU_APP_SHARED_SECRET`. Point the app's backend URL at it.
