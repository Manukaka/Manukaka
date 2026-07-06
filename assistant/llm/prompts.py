"""All prompt templates and the profile-extraction JSON schema in one place."""
from datetime import date

PERSONA = (
    "You are Manu, a completely private personal assistant running offline on the "
    "user's own laptop. You have access to the user's personal data: phone call "
    "transcripts, WhatsApp chats, and SMS messages. The user speaks Marathi, Hindi, "
    "Hinglish, and English — always reply in the same language the user used. "
    "Be warm, practical, and concise. Ground your answers in the provided context "
    "and profile; when you are not sure, say so instead of inventing details. "
    "When giving advice, refer to specific conversations or facts when relevant."
)


def build_system_prompt(profile_md: str, context_block: str) -> str:
    parts = [PERSONA, f"\nToday's date: {date.today().strftime('%d %B %Y')}."]
    if profile_md.strip():
        parts.append("\n## What you know about the user\n" + profile_md.strip())
    if context_block.strip():
        parts.append(
            "\n## Relevant excerpts from the user's data\n"
            "(retrieved for the current question — quote or use them when answering)\n"
            "Each excerpt is numbered. When your answer uses an excerpt, cite it "
            "inline with its number in square brackets, e.g. [1] or [2][3]. "
            "Do not cite excerpts you did not use.\n\n"
            + context_block.strip()
        )
    return "\n".join(parts)


PROFILE_EXTRACTION_SYSTEM = (
    "You extract durable personal facts from one conversation. Only record things "
    "worth remembering weeks later (relationships, commitments, money matters, "
    "health, work, strong preferences). Ignore small talk. Write facts in English, "
    "short and specific, even if the conversation is in Marathi or Hindi. "
    "If the conversation contains nothing durable, return empty lists."
)

PROFILE_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "people": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "relation": {"type": "string"},
            "notes": {"type": "string"},
        }, "required": ["name"]}},
        "commitments": {"type": "array", "items": {"type": "object", "properties": {
            "what": {"type": "string"},
            "with_whom": {"type": "string"},
            "due": {"type": "string"},
        }, "required": ["what"]}},
        "finances": {"type": "array", "items": {"type": "string"}},
        "health": {"type": "array", "items": {"type": "string"}},
        "work": {"type": "array", "items": {"type": "string"}},
        "preferences": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["people", "commitments", "finances", "health", "work", "preferences"],
}


def build_extraction_prompt(source_label: str, conversation_text: str) -> str:
    return (
        f"Conversation source: {source_label}\n\n"
        f"---\n{conversation_text}\n---\n\n"
        "Extract the durable personal facts from this conversation."
    )


PROFILE_MERGE_SYSTEM = (
    "You maintain a compact personal profile. Merge duplicate facts, keep the "
    "newest version when facts conflict, drop trivia, and keep the result short."
)


DIGEST_SYSTEM = (
    "You are Manu, the user's private offline assistant. Write a brief, warm "
    "weekly digest of the user's conversations: what happened, open threads, "
    "commitments made, and anything they should not forget. Use short sections "
    "with bold headers, mention people by name, and keep it under 300 words. "
    "Write in the language the user mostly used in these conversations."
)


def build_digest_prompt(excerpts_block: str, days: int) -> str:
    return (
        f"Here are the user's conversations from the last {days} days:\n\n"
        f"{excerpts_block}\n\n"
        "Write the digest."
    )
