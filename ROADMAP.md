# Manu — Project Status & Roadmap

_Last updated: 2026-07-04_

## 1. Where the project stands today (v0.1)

Manu is a working end-to-end MVP of a fully offline personal AI assistant:

- **Ingestion**: call recordings (ffmpeg → faster-whisper large-v3 → pyannote
  diarization), WhatsApp `.txt` exports (Android + iOS formats), SMS XML backups.
  A sha256 manifest makes re-ingestion idempotent.
- **Retrieval (RAG)**: session-aware chunking with deterministic chunk IDs,
  BGE-M3 embeddings on CPU, ChromaDB store, recency-boosted top-k retrieval.
- **Memory**: LLM-extracted "life profile" (people, commitments, finances,
  health, work, preferences) rendered to `profile.md` and injected into every chat.
- **Chat**: FastAPI + SSE streaming from Ollama (qwen3:8b), desktop window via
  pywebview with browser fallback, GPU turn-taking between Whisper and the LLM.
- **Ops**: Windows setup scripts (`setup.bat`/`setup.ps1`), model downloader,
  CLI ingest script, 6 unit tests covering the parsers and chunking.

Codebase: ~1,200 lines of Python across `assistant/` with clean module
boundaries (`ingestion/`, `rag/`, `memory/`, `llm/`, `ui/`). PR #1 (the MVP)
is merged to `main`.

### Known weak spots

| Area | Issue |
|---|---|
| Testing | Only parsers/chunking are tested. No tests for retriever, profile memory, server endpoints, or the ingest runner. |
| CI | No GitHub Actions — tests are never run automatically. |
| Error visibility | Several `except Exception: pass` blocks (e.g. retrieval inside `/api/chat`) silently swallow failures; there is no logging framework, only the ingest status callback. |
| Concurrency | `STATE.running` is mutated outside its lock; chat is fully blocked during ingestion even in CPU-only phases (parsing/embedding). |
| Profile safety | `_maybe_merge` replaces the whole profile with LLM output with no backup — a bad merge silently loses memory. |
| Config | `config.yaml` is not validated; a typo fails deep inside the stack with a cryptic error. |
| Chat state | Chat history lives only in the browser tab; refresh loses the conversation. |

## 2. Roadmap

### Phase 1 — Strong foundations (code hardening) — **done**

1. ✅ **CI pipeline**: GitHub Actions running `ruff` + `pytest` on every push/PR
   (`.github/workflows/ci.yml`, light `requirements-dev.txt`). `mypy` deferred.
2. ✅ **Logging**: `assistant/log.py` — console + rotating file in `data/logs/`;
   every previously-silent `except` now logs the traceback.
3. ✅ **Test expansion** (6 → 34 tests):
   - `retriever` (recency boost math, context formatting) with a fake store
   - `memory/profile` (extract/merge/render) with a mocked Ollama client
   - `server` endpoints via FastAPI `TestClient` (health, ingest 409, chat 4xx paths)
   - `runner` manifest logic + a text-source ingest run with a fake embedder
   - `config` validation errors
4. ✅ **Config validation**: pydantic models for `config.yaml`; typos and wrong
   types fail at startup with the offending key named.
5. ✅ **Profile safety**: timestamped backup of `profile.json` before every LLM
   merge (`data/profile/backups/`, last 10 kept).
6. ✅ **Concurrency fixes**: `STATE` mutations locked; chat now blocks only
   while whisper owns the GPU, not during CPU parsing/embedding phases.

### Phase 2 — Retrieval quality (answers get noticeably smarter) — **done**

1. ✅ **Hybrid search**: pure-Python BM25 (`rag/keyword.py`, no new deps) fused
   with vector search via reciprocal-rank fusion — big win for names, amounts,
   and code-switched Marathi/Hinglish where embeddings are weakest.
2. ✅ **Metadata boosting** (`rag/query_analysis.py`): contact names and time
   phrases ("last week", "गेल्या आठवड्यात", "पिछले महीने") detected in the
   question boost matching chunks (boost, not hard-filter, on purpose).
3. ✅ **Query rewriting** (`rag/rewrite.py`): one LLM pass turns follow-up
   questions into standalone search queries; any failure falls back silently.
4. ✅ **Citations**: excerpts are numbered, the model cites [n] inline, and the
   UI shows a sources footer under each answer (only excerpts actually cited).
   Clickable transcript view moves to Phase 5's transcript browser.

### Phase 3 — Memory that acts like memory — **done**

1. ✅ **Structured commitments** (`memory/commitments.py`): extracted
   commitments get a parsed ISO due date (dateutil, day-first, next-year
   rollover), deduped storage in `data/profile/commitments.json`, an
   `/api/upcoming` endpoint, and an **Upcoming** panel in the UI.
2. ✅ **Per-contact overview**: `/api/contacts` + **People** panel — last
   contact date, memory counts, source types, and the profile facts Manu has
   gathered about each person.
3. ✅ **Weekly digest**: `/api/digest` + **Digest** button — summarizes the
   last 7 days of indexed conversations with the local LLM (bounded context,
   most recent first).

### Phase 4 — More data in

1. ✅ **Telegram export** parser (`ingestion/telegram.py`): handles both the
   full-account `result.json` and single-chat exports, entity-list text,
   skips service events/media/saved-messages; drop files in `ingest/telegram/`.
2. ✅ **Voice notes**: `ingest/audio/` already accepts `.opus`/`.m4a` — drop
   exported WhatsApp/Telegram voice notes there and they go through Whisper.
   *(No code needed; documented.)*
3. ⬜ **Watch folders** — sub-plan:
   - a `watchdog`-free polling thread (10 s) started from `app.py`, guarded by
     a new `app.auto_ingest: false` config flag (off by default: auto-ingest
     unloads the LLM mid-chat, so it must be a choice)
   - only trigger when file sizes are stable across two polls (copy finished)
   - reuse `STATE.try_start()` so manual + auto ingest can never overlap
4. ⬜ **Email** (`.eml`/mbox) parser — sub-plan: stdlib `email` + `mailbox`
   modules, contact = counterpart address's display name, thread → session;
   needs a fixture set (plain, HTML-only, and Devanagari subject cases).

### Phase 5 — Product polish

1. ✅ **Persistent chat history** (`memory/chatlog.py`, SQLite): every chat
   turn is stored in `data/chat.db`; `/api/history` restores it on window
   open. *(Multiple named conversations still to do — see sub-plan below.)*
2. ⬜ **Named conversations** — sub-plan: `conversations` table + `conv_id`
   column, `GET/POST /api/conversations`, a left sidebar in the UI, and
   "new chat" resets context without deleting history.
3. ⬜ **Transcript browser** — sub-plan: `GET /api/transcripts` (list) and
   `GET /api/transcripts/{stem}` (text) reading `data/transcripts/`; make the
   citation chips in the sources footer clickable to open the transcript in
   the info panel.
4. ⬜ **Packaging** — sub-plan: PyInstaller one-dir build of `assistant.app`,
   models still downloaded on first run (they cannot be bundled), an Inno
   Setup script for a real installer, and a tray icon (`pystray`) + Startup
   shortcut for autostart. Needs a Windows machine to build/verify.

## 3. Suggested order of work

Phase 1 is the multiplier — every later feature lands faster and safer on top
of CI + tests + logging. Phases 2 and 3 deliver the most user-visible
intelligence gains. Phases 4 and 5 can be interleaved based on need.

Remaining items, in suggested order: transcript browser (5.3, small and makes
citations tangible) → watch folders (4.3) → named conversations (5.2) →
email parser (4.4) → packaging (5.4, needs Windows).

Each remaining item should land as its own small PR with tests.
