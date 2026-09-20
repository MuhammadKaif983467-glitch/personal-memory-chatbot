"""Recent messages and conversation continuity.

Extracts conversation context formatting from context_service._recent_conversation
into a standalone pipeline service for reuse across chat and preview flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class ConversationContext:
    """Structured output of conversation context extraction.

    Attributes
    ----------
    recent_text:
        Formatted multi-line string of recent messages.
    recent_count:
        Number of messages included.
    speaker_roles:
        Mapping of sender name to its dominant role label.
    """

    recent_text: str
    recent_count: int
    speaker_roles: dict[str, str]


def build_conversation_context(
    messages: Sequence,
    person_name: str,
    user_name: str = "me",
    limit: int = 10,
    max_content_chars: int = 400,
) -> ConversationContext:
    """Build conversation context from recent messages.

    Parameters
    ----------
    messages:
        Sequence of Message ORM objects (newest last).
    person_name:
        Display name of the person being conversed with.
    user_name:
        Label for the human side of the conversation.
    limit:
        Maximum number of recent messages to include.
    max_content_chars:
        Truncate each message content to this many characters.

    Returns
    -------
    ConversationContext
        Structured context ready for prompt assembly.
    """
    lines: list[str] = []
    speaker_roles: dict[str, str] = {}

    for message in messages[-limit:]:
        is_assistant = getattr(message, "is_assistant", False)
        role = "assistant" if is_assistant else "user"
        sender = getattr(message, "sender", None)
        content = (getattr(message, "content", None) or "").replace("\n", " ")
        if len(content) > max_content_chars:
            content = content[:max_content_chars].rstrip() + "..."

        # Track the role each sender plays in the conversation.
        if sender and sender not in speaker_roles:
            speaker_roles[sender] = role

        lines.append(f"- [{role}] {content}")

    return ConversationContext(
        recent_text="\n".join(lines) if lines else "(no conversation yet)",
        recent_count=len(lines),
        speaker_roles=speaker_roles,
    )
