"""Calls Claude to produce a structured fact-check verdict.

Uses the Anthropic Python SDK with:
  - the web_search / web_fetch server tools for live evidence,
  - output_config.format to force a parseable verdict object,
  - adaptive thinking so the model reasons before rating.
The API key is read from the ANTHROPIC_API_KEY environment variable.
"""
import json
from typing import Optional

import anthropic

from . import config, prompts, verdict

# Server tools: dynamic-filtering web search + web fetch (Opus 4.6+/4.8).
TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": config.WEB_SEARCH_MAX_USES},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": config.WEB_SEARCH_MAX_USES},
]

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def build_user_content(kind: str, *, lang: str, text: str = "", url: str = "",
                       image_b64: str = "", media_type: str = "") -> list:
    """Assemble the user message content for a given check kind."""
    instr = prompts.lang_instruction(lang)
    if kind == "text":
        return [_text_block(
            f"Fact-check the main claim in this forwarded message. {instr}\n\n"
            f"Message:\n\"\"\"\n{text}\n\"\"\""
        )]
    if kind == "url":
        return [_text_block(
            f"Fact-check the main claim(s) in the content at this link. "
            f"Fetch and read it, then research the claim. {instr}\n\nLink: {url}"
        )]
    if kind == "image":
        return [
            {"type": "image",
             "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
            _text_block(
                "This is a screenshot or image that is being forwarded in India. "
                "Read any text in it, identify the main factual claim, and fact-check it. "
                "If it is a real photo or video being reused out of its original context, "
                f"say so. {instr}"
            ),
        ]
    raise ValueError(f"unknown check kind: {kind}")


def _extract_json(content_blocks) -> dict:
    """Pull the final JSON verdict out of the response content blocks."""
    for block in content_blocks:
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)
    raise ValueError("no text block with a verdict in the model response")


def check(kind: str, *, lang: str = config.DEFAULT_LANG, **kwargs) -> dict:
    """Run a fact-check and return a decorated verdict dict.

    Raises RuntimeError on a model refusal so the API layer can map it to a
    clean response.
    """
    client = _get_client()
    user_content = build_user_content(kind, lang=lang, **kwargs)
    messages = [{"role": "user", "content": user_content}]

    # Server tools run a sampling loop; resend on pause_turn until it completes.
    for _ in range(config.WEB_SEARCH_MAX_USES + 3):
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            system=prompts.SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            tools=TOOLS,
            output_config={"format": verdict.OUTPUT_FORMAT, "effort": config.EFFORT},
            messages=messages,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("The fact-check could not be completed for this content.")
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        return verdict.decorate(_extract_json(response.content))

    raise RuntimeError("Fact-check timed out while researching. Please try again.")
