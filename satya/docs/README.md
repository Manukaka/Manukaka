# Satya — सत्य

An online, AI-powered fact-check app for India. Inspired by the InTruth
fact-check concept, rebuilt as an Android app + cloud backend for the way
misinformation actually spreads in India: WhatsApp forwards (text, screenshots,
images), news links, and viral speeches — across many languages, on low-end
phones.

**Core flow:** share a forward into Satya → get a clear, colour-coded verdict
with trusted Indian sources, in your language.

## Pieces

- **`app/`** — Flutter Android app. Share-to-check, paste text/link, screenshot
  & camera, local history, Hinglish/Hindi/English.
- **`backend/`** — FastAPI service that holds the Claude key, does live web
  research, returns a structured bilingual verdict, and caches viral forwards.
- **`shared/`** — single source of truth for the verdict taxonomy and the list
  of trusted Indian fact-checkers.
- **`docs/`** — this overview and `DEPLOYMENT.md`.

## Verdicts

| Code | English | Hindi |
|---|---|---|
| `TRUE` | True | सच |
| `MOSTLY_TRUE` | Mostly True | ज़्यादातर सच |
| `MISLEADING` | Misleading | भ्रामक |
| `FALSE` | False | झूठ |
| `UNVERIFIABLE` | Can't verify yet | पुष्टि नहीं हो सकी |

Every result carries a confidence level, a plain-language explanation, evidence
bullets, and clickable sources (PIB Fact Check, Alt News, BOOM, Factly, etc.).

## Why these choices (the "all perspectives" summary)

- **Trust & neutrality** — non-partisan prompt, always shows sources, says
  "can't verify" instead of guessing, never fabricates citations.
- **Built for India** — flags old-photo-as-new and out-of-context reuse;
  prioritises Indian fact-checkers; multilingual.
- **Cheap & light for users** — text-first, compressed images, and a content-
  hash cache so the same viral forward is verified once and served instantly.
- **Cost & abuse control for you** — server-side key, dedupe cache, size limits.
- **Privacy** — no login to start; checks stored only on the device.

## Roadmap

Live audio fact-check (debates/news), more Indian languages, a WhatsApp bot,
and shareable verdict images to fight misinformation through the same channel it
spreads on.

## Quick start

1. `cd backend && pip install -r requirements.txt && cp .env.example .env`
   (add your `ANTHROPIC_API_KEY`), then `uvicorn app.main:app --reload`.
2. `cd app && flutter create . && flutter pub get && flutter run`
   (point it at the backend in Settings).

See `backend/README.md` and `app/README.md` for detail, and
`docs/DEPLOYMENT.md` to ship it.
