"""FastAPI backend: streaming chat (SSE), ingest trigger, status."""
import json
import threading
import time
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .ingestion import runner
from .llm import ollama_client, prompts
from .log import get_logger
from .memory import chatlog, commitments
from .memory import profile as memory_profile

log = get_logger(__name__)

app = FastAPI(title="Manu")


class IngestState:
    def __init__(self):
        self._running = False
        self.log: List[str] = []
        self.lock = threading.Lock()

    @property
    def running(self) -> bool:
        with self.lock:
            return self._running

    def try_start(self) -> bool:
        """Atomically claim the ingest slot; False if a run is already active."""
        with self.lock:
            if self._running:
                return False
            self._running = True
            self.log = ["Starting…"]
            return True

    def finish(self) -> None:
        with self.lock:
            self._running = False

    def status_cb(self, msg: str):
        with self.lock:
            self.log.append(msg)
            self.log = self.log[-50:]


STATE = IngestState()


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None  # [{role, content}, ...]


@app.get("/")
def index():
    return FileResponse(config.UI_DIR / "index.html")


@app.get("/api/health")
def health():
    from .rag import store
    chunks = 0
    try:
        chunks = store.count()
    except Exception:
        log.exception("Could not read the vector store for /api/health")
    return {
        "ollama": ollama_client.is_up(),
        "model": config.CFG["llm"]["model"],
        "model_available": ollama_client.model_available() if ollama_client.is_up() else False,
        "chunks": chunks,
        "ingesting": STATE.running,
    }


@app.post("/api/ingest")
def ingest():
    if not STATE.try_start():
        raise HTTPException(409, "Ingestion already running")

    def work():
        try:
            runner.run_ingest(STATE.status_cb)
        except Exception as e:
            log.exception("Ingestion crashed")
            STATE.status_cb(f"Ingestion failed: {e}")
        finally:
            STATE.finish()

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


@app.get("/api/status")
def status():
    with STATE.lock:
        return {"running": STATE._running, "log": list(STATE.log)}


@app.get("/api/history")
def history(limit: int = 40):
    """Persisted chat messages so the conversation survives restarts."""
    try:
        return {"messages": chatlog.recent(limit)}
    except Exception:
        log.exception("Could not load chat history")
        return {"messages": []}


@app.get("/api/upcoming")
def upcoming():
    """Structured commitments: dated ones soonest-first, plus recent undated."""
    return commitments.upcoming()


def _index_docs() -> List[dict]:
    from .rag import keyword
    return keyword.get_index().docs


@app.get("/api/contacts")
def contacts():
    """Per-person overview: sources, last contact, and profile facts about them."""
    people: dict = {}
    try:
        for doc in _index_docs():
            meta = doc["metadata"]
            name = meta.get("contact")
            if not name:
                continue
            p = people.setdefault(name, {"name": name, "chunks": 0,
                                         "last_ts": 0.0, "sources": set(), "facts": []})
            p["chunks"] += 1
            p["last_ts"] = max(p["last_ts"], meta.get("end_ts", 0))
            p["sources"].add(meta.get("source_type", "?"))
    except Exception:
        log.exception("Could not read the index for /api/contacts")

    try:
        for entry in memory_profile.load_profile().get("people", []):
            fact = entry.get("fact", {})
            name = fact.get("name") if isinstance(fact, dict) else None
            if not name:
                continue
            for known in people:
                if name.lower() in known.lower() or known.lower() in name.lower():
                    people[known]["facts"].append(memory_profile._fact_text(entry))
                    break
    except Exception:
        log.exception("Could not attach profile facts for /api/contacts")

    out = sorted(people.values(), key=lambda p: p["last_ts"], reverse=True)
    for p in out:
        p["sources"] = sorted(p["sources"])
    return {"contacts": out}


class DigestRequest(BaseModel):
    days: int = 7


@app.post("/api/digest")
def digest(req: DigestRequest):
    """LLM summary of the last N days across all conversations."""
    if runner.GPU_BUSY.is_set():
        raise HTTPException(409, "Please wait — I'm still transcribing your calls.")
    if not ollama_client.is_up():
        raise HTTPException(503, "Ollama is not running. Start Ollama and try again.")

    days = max(1, min(req.days, 31))
    cutoff = time.time() - days * 86400
    try:
        docs = [d for d in _index_docs() if d["metadata"].get("end_ts", 0) >= cutoff]
    except Exception:
        log.exception("Could not read the index for /api/digest")
        docs = []
    if not docs:
        return {"digest": None,
                "message": f"No conversations from the last {days} days are indexed yet."}

    docs.sort(key=lambda d: d["metadata"].get("end_ts", 0), reverse=True)
    block, size = [], 0
    for d in docs:
        if size + len(d["text"]) > 9000:
            break
        block.append(d["text"])
        size += len(d["text"])

    messages = [
        {"role": "system", "content": prompts.DIGEST_SYSTEM},
        {"role": "user", "content": prompts.build_digest_prompt("\n\n".join(block), days)},
    ]
    try:
        return {"digest": ollama_client.chat_once(messages)}
    except Exception as e:
        log.exception("Digest generation failed")
        raise HTTPException(502, f"Digest failed: {e}")


@app.post("/api/chat")
def chat(req: ChatRequest):
    if runner.GPU_BUSY.is_set():
        # Whisper owns the GPU during transcription; chatting now would OOM.
        # Text parsing/embedding phases run on CPU, so chat stays available then.
        raise HTTPException(409, "Please wait — I'm still transcribing your calls.")
    if not ollama_client.is_up():
        raise HTTPException(503, "Ollama is not running. Start Ollama and try again.")

    question = req.message.strip()
    if not question:
        raise HTTPException(400, "Empty message")

    turns = config.CFG["llm"]["chat_history_turns"]
    history = (req.history or [])[-(turns * 2):]

    # RAG: retrieve relevant excerpts (works even with an empty index)
    context_block = ""
    sources: List[dict] = []
    try:
        from .rag import retriever
        hits = retriever.retrieve(question, history)
        context_block = retriever.format_context(hits)
        sources = retriever.sources(hits)
    except Exception:
        log.exception("Retrieval failed; answering without conversation context")

    system = prompts.build_system_prompt(memory_profile.load_profile_md(), context_block)
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": question})

    def stream():
        answer_parts: List[str] = []
        try:
            for chunk in ollama_client.chat_stream(messages):
                answer_parts.append(chunk)
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            if sources:
                yield f"data: {json.dumps({'sources': sources})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            log.exception("Chat stream failed")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if answer_parts:
                try:
                    chatlog.append("user", question)
                    chatlog.append("assistant", "".join(answer_parts))
                except Exception:
                    log.exception("Could not persist the chat turn")

    return StreamingResponse(stream(), media_type="text/event-stream")


app.mount("/ui", StaticFiles(directory=str(config.UI_DIR)), name="ui")
