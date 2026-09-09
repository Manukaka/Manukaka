"""Follow-up questions ("what did *she* say about it?") search terribly as-is.
One cheap LLM call rewrites the question into standalone search queries using
the recent chat turns. Any failure falls back to searching the raw question.
"""
from typing import Dict, List

from .. import config
from ..llm import ollama_client
from ..log import get_logger

log = get_logger(__name__)

MAX_QUERIES = 2

REWRITE_SYSTEM = (
    "You turn the user's latest chat message into search queries over their "
    "personal conversations (calls, WhatsApp, SMS). Resolve pronouns and "
    "references using the chat history. Return 1-2 short standalone queries in "
    "the same language as the message, plus an English version if the message "
    "is not in English. If the message already works as a search query, return "
    "it unchanged as the only query."
)

REWRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["queries"],
}


def rewrite(question: str, history: List[Dict]) -> List[str]:
    """Extra search queries for a follow-up question; [] when not needed/possible."""
    if not config.CFG["rag"]["query_rewrite"] or not history:
        return []
    turns = "\n".join(f"{m.get('role')}: {m.get('content', '')[:300]}"
                      for m in history[-4:])
    prompt = (
        f"Chat history:\n{turns}\n\n"
        f"Latest message: {question}\n\n"
        "Write the search queries."
    )
    try:
        result = ollama_client.extract(prompt, REWRITE_SCHEMA, system=REWRITE_SYSTEM)
    except Exception:
        log.exception("Query rewrite crashed; searching the raw question only")
        return []
    if not result:
        return []
    queries = [q.strip() for q in result.get("queries", [])
               if isinstance(q, str) and q.strip() and q.strip().lower() != question.lower()]
    return queries[:MAX_QUERIES]
