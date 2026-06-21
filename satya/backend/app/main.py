"""Satya fact-check API (FastAPI).

Endpoints:
  GET  /api/health
  POST /v1/check/text   {text, lang}
  POST /v1/check/url    {url, lang}
  POST /v1/check/image  (multipart: file, lang)

Each check is deduped by content hash so viral forwards are verified once.
"""
import base64
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import cache, claude_client, config

app = FastAPI(title="Satya", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    lang: str = config.DEFAULT_LANG


class UrlRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2000)
    lang: str = config.DEFAULT_LANG


def _run(kind: str, cache_key: str, **kwargs) -> dict:
    """Serve from cache or run the check, then cache the result."""
    cached = cache.get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}
    try:
        result = claude_client.check(kind, **kwargs)
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # SDK / network errors
        raise HTTPException(status_code=502, detail=f"Fact-check service error: {e}")
    cache.put(cache_key, result)
    return {**result, "cached": False}


@app.get("/api/health")
def health():
    return {"status": "ok", "model": config.MODEL, "languages": config.SUPPORTED_LANGS}


@app.get("/api/taxonomy")
def taxonomy():
    """Verdict labels/colours, so the app and backend share one source of truth."""
    return config.VERDICT_TAXONOMY


@app.post("/v1/check/text")
def check_text(req: TextRequest):
    key = cache.make_key(f"text:{req.lang}", cache.normalise_text(req.text))
    return _run("text", key, text=req.text, lang=req.lang)


@app.post("/v1/check/url")
def check_url(req: UrlRequest):
    key = cache.make_key(f"url:{req.lang}", req.url.strip().lower().encode("utf-8"))
    return _run("url", key, url=req.url, lang=req.lang)


@app.post("/v1/check/image")
async def check_image(file: UploadFile = File(...), lang: str = Form(config.DEFAULT_LANG)):
    media_type = (file.content_type or "").lower()
    if media_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {media_type}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload.")
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8 MB).")
    image_b64 = base64.standard_b64encode(data).decode("utf-8")
    key = cache.make_key(f"image:{lang}", data)
    return _run("image", key, image_b64=image_b64, media_type=media_type, lang=lang)
