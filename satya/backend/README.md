# Satya backend

FastAPI service that fact-checks Indian misinformation with Claude. It holds the
API key server-side, does live web research, and returns a structured, bilingual
verdict. Identical viral forwards are deduped by content hash and served from a
local cache.

## Run locally

```bash
cd satya/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
export $(grep -v '^#' .env | xargs)   # or use a dotenv loader
uvicorn app.main:app --reload
```

Smoke test:

```bash
curl -s -X POST localhost:8000/v1/check/text \
  -H 'content-type: application/json' \
  -d '{"text":"Government is depositing Rs 15 lakh in every account","lang":"hinglish"}' | python -m json.tool
```

## Test

```bash
cd satya/backend
pip install -r requirements.txt
pytest            # Claude calls are mocked; no key or network needed
```

## Endpoints

| Method | Path | Body |
|---|---|---|
| GET | `/api/health` | — |
| GET | `/api/taxonomy` | — |
| POST | `/v1/check/text` | `{text, lang}` |
| POST | `/v1/check/url` | `{url, lang}` |
| POST | `/v1/check/image` | multipart `file`, `lang` |

`lang` is one of `en`, `hi`, `hinglish`. Every check returns:

```json
{
  "verdict": "FALSE",
  "verdict_label_en": "False",
  "verdict_label_hi": "झूठ",
  "verdict_color": "#D32F2F",
  "confidence": "high",
  "claim": "...",
  "summary": "...",
  "evidence": ["..."],
  "sources": [{"title": "...", "url": "...", "publisher": "..."}],
  "cached": false
}
```
