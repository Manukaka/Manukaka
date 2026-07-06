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

### Phase 3 — Memory that acts like memory

1. **Structured commitments**: extract due dates into structured records; an
   "Upcoming" panel in the UI; "what should I not forget?" answered from data,
   not vibes.
2. **Per-contact profiles**: a page per person (relationship, open threads,
   last contact date).
3. **Weekly digest**: on-demand summary of the week across all sources.

### Phase 4 — More data in

1. **Telegram export** parser (JSON export format).
2. **WhatsApp voice notes**: route exported `.opus` voice notes through the
   existing Whisper pipeline.
3. **Watch folders**: auto-ingest when new files appear (no button pressing).
4. **Email** (`.eml`/mbox) parser — optional, later.

### Phase 5 — Product polish

1. **Persistent chat sessions** (SQLite): history survives restarts, multiple
   named conversations.
2. **Transcript browser** in the UI (search + read transcripts and chats).
3. **Packaging**: single-file installer (PyInstaller) so setup doesn't require
   the console.
4. **Tray app + autostart** so Manu is always one click away.

## 3. Suggested order of work

Phase 1 is the multiplier — every later feature lands faster and safer on top
of CI + tests + logging. Phases 2 and 3 deliver the most user-visible
intelligence gains. Phases 4 and 5 can be interleaved based on need.

Each phase item should land as its own small PR with tests.
