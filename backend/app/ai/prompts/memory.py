"""Memory context and confidence-level handling."""

from __future__ import annotations

_CONFIDENCE_RULES: dict[str, str] = {
    "HIGH": (
        "There are strong supporting memories. You may answer using them "
        "as fact, but still do not invent details they do not contain."
    ),
    "MEDIUM": (
        "There is partial support. Answer with the remembered content but "
        "soften it (e.g. 'I recall...'), and invite the user to confirm."
    ),
    "LOW": (
        "No reliable memory was found. If the question is about past "
        "conversations, say you do not have that memory yet, do NOT invent "
        "historical events, and ask for clarification."
    ),
}


def memory_section(confidence_level: str) -> str:
    """Return the rules paragraph governing how memories are used in responses.

    Parameters
    ----------
    confidence_level:
        One of ``"HIGH"``, ``"MEDIUM"``, or ``"LOW"`` indicating retrieval
        confidence.
    """
    confidence_rule = _CONFIDENCE_RULES.get(
        confidence_level, _CONFIDENCE_RULES["LOW"]
    )

    return f"""RULES:
- Use retrieved memories only when relevant to the question.
- Do not invent historical events, facts, or conversations.
- Do not claim a memory exists when retrieval found nothing.
- Distinguish remembered information from the current conversation.
- Respect user corrections over old memories (user is always more recent).
- Avoid exposing private historical messages unless relevant to the answer.
- Confidence signal: {confidence_level}. {confidence_rule}
- Ask for clarification when required.
- Keep answers concise, natural and conversational — not formal.
"""
