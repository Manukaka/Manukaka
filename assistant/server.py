"""FastAPI backend: streaming chat (SSE), ingest trigger, status."""
import json
import threading
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .ingestion import runner
from .llm import ollama_client, prompts
from .log import get_logger
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
        try:
            for chunk in ollama_client.chat_stream(messages):
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            if sources:
                yield f"data: {json.dumps({'sources': sources})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            log.exception("Chat stream failed")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


app.mount("/ui", StaticFiles(directory=str(config.UI_DIR)), name="ui")
