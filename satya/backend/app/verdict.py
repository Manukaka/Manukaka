"""Verdict taxonomy and the JSON schema the model is constrained to."""
from . import config

# JSON schema used with output_config.format so every AI response is parseable.
# Constraints follow the structured-outputs rules: object types declare
# additionalProperties: false and list required keys; enums are allowed.
VERDICT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": config.VERDICT_CODES,
            "description": "Overall rating of the main claim.",
        },
        "confidence": {
            "type": "string",
            "enum": config.VERDICT_TAXONOMY["confidence_levels"],
            "description": "How confident the rating is, given available evidence.",
        },
        "claim": {
            "type": "string",
            "description": "The single main factual claim being checked, restated plainly.",
        },
        "summary": {
            "type": "string",
            "description": "Plain-language explanation of the verdict, in the requested language.",
        },
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short bullet points of the key evidence behind the verdict.",
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "publisher": {"type": "string"},
                },
                "required": ["title", "url", "publisher"],
                "additionalProperties": False,
            },
            "description": "Sources consulted, preferring trusted Indian fact-checkers and primary sources.",
        },
    },
    "required": ["verdict", "confidence", "claim", "summary", "evidence", "sources"],
    "additionalProperties": False,
}

OUTPUT_FORMAT = {"type": "json_schema", "schema": VERDICT_JSON_SCHEMA}


def decorate(result: dict) -> dict:
    """Attach human-facing labels/colour for the returned verdict code."""
    code = result.get("verdict")
    meta = next((v for v in config.VERDICT_TAXONOMY["verdicts"] if v["code"] == code), None)
    if meta:
        result["verdict_label_en"] = meta["label_en"]
        result["verdict_label_hi"] = meta["label_hi"]
        result["verdict_color"] = meta["color"]
    return result
