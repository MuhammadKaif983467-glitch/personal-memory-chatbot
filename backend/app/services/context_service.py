"""Context builder.

Assembles a bounded context block for the AI provider from:

  CURRENT QUESTION
  RECENT CONVERSATION
  RELEVANT MEMORIES
  IMPORTANT FACTS
  PERSON PROFILE
  WRITING STYLE
  RETRIEVAL METADATA

The builder enforces a character budget so we never dump whole chat history
into a single request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from app.database.models import Person, PersonProfile, WritingStyle
from app.schemas.common import Fact
from app.schemas.memory import ConfidenceOut
from app.services.retrieval_service import RetrievedMemory

_SECTION_HEADERS = [
    "CURRENT QUESTION",
    "RECENT CONVERSATION",
    "RELEVANT MEMORIES",
    "IMPORTANT FACTS",
    "PERSON PROFILE",
    "WRITING STYLE",
    "RETRIEVAL METADATA",
]


@dataclass
class ContextResult:
    text: str
    used_chars: int
    sections: dict
    budget: int


def build_context(
    *,
    question: str,
    recent_messages: Sequence,
    retrieved: Sequence[RetrievedMemory],
    person: Optional[Person],
    profile: Optional[PersonProfile],
    style: Optional[WritingStyle],
    confidence: ConfidenceOut,
    budget_chars: int = 9000,
    recent_limit: int = 10,
) -> ContextResult:
    sections: dict = {}

    sections["CURRENT QUESTION"] = question.strip()

    sections["RECENT CONVERSATION"] = _recent_conversation(recent_messages, recent_limit)

    sections["RELEVANT MEMORIES"] = _memories(retrieved, limit=10)

    sections["IMPORTANT FACTS"] = _important_facts(profile)

    sections["PERSON PROFILE"] = _profile_text(profile, person)

    sections["WRITING STYLE"] = _style_text(style)

    best_sim = max((r.similarity for r in retrieved), default=0.0)
    sections["RETRIEVAL METADATA"] = (
        f"Retrieved {len(retrieved)} memory/memories; best similarity "
        f"{best_sim:.2f}; confidence {confidence.level} ({confidence.score:.2f})."
    )

    text = _assemble(sections)
    used = len(text)

    # Enforce the budget: shrink the most flexible sections first, then hard-cap.
    if used > budget_chars:
        overflow = used - budget_chars
        for section in ("RELEVANT MEMORIES", "RECENT CONVERSATION", "IMPORTANT FACTS", "PERSON PROFILE", "WRITING STYLE"):
            if overflow <= 0:
                break
            body = sections.get(section, "")
            ratio = max(0.30, 1.0 - (overflow / max(len(body), 1)))
            sections[section] = _truncate(body, int(len(body) * ratio))
            used = len(_assemble(sections))
            overflow = used - budget_chars

    final_text = _assemble(sections)
    if len(final_text) > budget_chars:
        final_text = _truncate(final_text, budget_chars)
    return ContextResult(
        text=final_text,
        used_chars=len(final_text),
        sections={k: len(v) for k, v in sections.items()},
        budget=budget_chars,
    )


def _recent_conversation(messages: Sequence, limit: int) -> str:
    lines: list[str] = []
    for message in messages[-limit:]:
        role = "assistant" if message.is_assistant else "user"
        content = (message.content or "").replace("\n", " ")[:400]
        lines.append(f"- [{role}] {content}")
    return "\n".join(lines) if lines else "(no conversation yet)"


def _memories(retrieved: Sequence[RetrievedMemory], limit: int) -> str:
    if not retrieved:
        return "(no relevant memories retrieved)"
    lines: list[str] = []
    for index, item in enumerate(sorted(retrieved, key=lambda r: r.similarity, reverse=True)[:limit], start=1):
        memory = item.memory
        snippet = (memory.content or "").replace("\n", " ")[:400]
        created = memory.created_at.date().isoformat() if memory.created_at else "?"
        lines.append(
            f"{index}. [{item.similarity:.2f}] ({memory.memory_type}, conf {memory.confidence:.2f}) "
            f"{snippet} — recalled from {created}"
        )
    return "\n".join(lines)


def _important_facts(profile: Optional[PersonProfile]) -> str:
    if profile is None:
        return "(no stored facts yet)"
    facts: list[Fact] = []
    for raw in list(profile.important_facts or []):
        try:
            facts.append(Fact(**raw))
        except Exception:
            continue
    facts.sort(key=lambda f: f.confidence, reverse=True)
    if not facts:
        return "(no stored facts yet)"
    return "\n".join(f"- {f.value}" for f in facts[:6])


def _profile_text(profile: Optional[PersonProfile], person: Optional[Person]) -> str:
    if profile is None:
        return f"About {person.name if person else 'this person'}: (no profile built yet)"
    bits: list[str] = [f"About {person.name if person else 'this person'}:"]
    if profile.interests:
        bits.append("Interests: " + "; ".join(str(f.get("value", ""))[:80] for f in profile.interests[:5]))
    if profile.preferences:
        bits.append("Preferences: " + "; ".join(str(f.get("value", ""))[:80] for f in profile.preferences[:5]))
    if profile.communication_habits:
        bits.append("Habits: " + "; ".join(str(h)[:80] for h in profile.communication_habits[:4]))
    if profile.topics:
        topics = [t.get("value", "") for t in profile.topics[:6]]
        bits.append("These topics come up often: " + ", ".join(topics))
    return "\n".join(bits)


def _style_text(style: Optional[WritingStyle]) -> str:
    if style is None:
        return "(no style analysis yet)"
    lines = [
        f"Average message length: {style.average_message_length:.0f} chars, "
        f"{style.average_words_per_message:.0f} words.",
        f"Tone: {style.tone or 'neutral'}.",
    ]
    if style.language_mix:
        mix = ", ".join(f"{k} {v:.0%}" for k, v in style.language_mix.items())
        lines.append(f"Languages: {mix}.")
    if (style.emoji_usage or {}).get("common_emojis"):
        lines.append("Emojis: " + " ".join(style.emoji_usage["common_emojis"][:6]))
    if style.common_words:
        lines.append("Frequent words: " + ", ".join(style.common_words[:8]))
    return "\n".join(lines)


def _assemble(sections: dict) -> str:
    blocks: list[str] = []
    for header in _SECTION_HEADERS:
        body = sections.get(header)
        if body is None:
            continue
        blocks.append(f"[{header}]\n{body}")
    return "\n\n".join(blocks)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."