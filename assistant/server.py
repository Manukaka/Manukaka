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
from .memory import profile as memory_profile

app = FastAPI(title="Manu")


class IngestState:
    def __init__(self):
        self.running = False
        self.log: List[str] = []
        self.lock = threading.Lock()

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
        pass
    return {
        "ollama": ollama_client.is_up(),
        "model": config.CFG["llm"]["model"],
        "model_available": ollama_client.model_available() if ollama_client.is_up() else False,
        "chunks": chunks,
        "ingesting": STATE.running,
    }


@app.post("/api/ingest")
def ingest():
    if STATE.running:
        raise HTTPException(409, "Ingestion already running")
    STATE.running = True
    STATE.log = ["Starting…"]

    def work():
        try:
            runner.run_ingest(STATE.status_cb)
        except Exception as e:
            STATE.status_cb(f"Ingestion failed: {e}")
        finally:
            STATE.running = False

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


@app.get("/api/status")
def status():
    with STATE.lock:
        return {"running": STATE.running, "log": list(STATE.log)}


@app.post("/api/chat")
def chat(req: ChatRequest):
    if STATE.running:
        # Whisper owns the GPU during ingestion; chatting now would OOM
        raise HTTPException(409, "Please wait — I'm still processing your files.")
    if not ollama_client.is_up():
        raise HTTPException(503, "Ollama is not running. Start Ollama and try again.")

    question = req.message.strip()
    if not question:
        raise HTTPException(400, "Empty message")

    # RAG: retrieve relevant excerpts (works even with an empty index)
    context_block = ""
    try:
        from .rag import retriever
        hits = retriever.retrieve(question)
        context_block = retriever.format_context(hits)
    except Exception:
        pass

    system = prompts.build_system_prompt(memory_profile.load_profile_md(), context_block)
    turns = config.CFG["llm"]["chat_history_turns"]
    history = (req.history or [])[-(turns * 2):]
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": question})

    def stream():
        try:
            for chunk in ollama_client.chat_stream(messages):
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


app.mount("/ui", StaticFiles(directory=str(config.UI_DIR)), name="ui")
