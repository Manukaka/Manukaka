"""Thin client for the local Ollama server (streaming chat, JSON extraction, unload)."""
import json
from typing import Dict, Iterator, List, Optional

import requests

from .. import config


def _cfg() -> dict:
    return config.CFG["llm"]


def is_up() -> bool:
    try:
        r = requests.get(f"{_cfg()['ollama_url']}/api/version", timeout=3)
        return r.ok
    except requests.RequestException:
        return False


def model_available() -> bool:
    try:
        r = requests.get(f"{_cfg()['ollama_url']}/api/tags", timeout=5)
        names = [m["name"] for m in r.json().get("models", [])]
        wanted = _cfg()["model"]
        return any(n == wanted or n.startswith(wanted + ":") for n in names)
    except (requests.RequestException, ValueError, KeyError):
        return False


def chat_stream(messages: List[Dict[str, str]]) -> Iterator[str]:
    """Yield response text chunks. `messages` = [{role, content}, ...]."""
    cfg = _cfg()
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": True,
        "think": False,  # Qwen3 thinking mode would add big latency for chat
        "options": {"num_ctx": cfg["num_ctx"], "temperature": cfg["temperature"]},
    }
    with requests.post(f"{cfg['ollama_url']}/api/chat", json=payload,
                       stream=True, timeout=600) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if data.get("done"):
                break


def extract(prompt: str, schema: dict, system: Optional[str] = None) -> Optional[dict]:
    """One-shot structured extraction using Ollama's JSON-schema `format` output."""
    cfg = _cfg()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"num_ctx": cfg["num_ctx"], "temperature": 0.1},
    }
    try:
        r = requests.post(f"{cfg['ollama_url']}/api/chat", json=payload, timeout=600)
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])
    except (requests.RequestException, ValueError, KeyError):
        return None


def unload() -> None:
    """Ask Ollama to release the model's VRAM (needed before loading whisper)."""
    cfg = _cfg()
    try:
        requests.post(f"{cfg['ollama_url']}/api/generate",
                      json={"model": cfg["model"], "keep_alive": 0}, timeout=30)
    except requests.RequestException:
        pass
