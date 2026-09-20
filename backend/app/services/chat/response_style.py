"""Converts WritingStyle into structured response-generation constraints."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.database.models import WritingStyle


@dataclass
class ResponseStyle:
    """Structured representation of a person's communication style.

    Attributes
    ----------
    tone:
        Overall tone label (e.g. ``"warm"``, ``"casual"``).
    language_mix:
        Mapping of language name to its proportion (e.g. ``{"english": 0.7, "urdu": 0.3}``).
    average_words:
        Typical words per message.
    emoji_frequency:
        How often emojis appear (0.0 – 1.0 scale).
    common_phrases:
        Frequently used expressions.
    greetings:
        Common opening lines.
    endings:
        Common sign-off lines.
    """

    tone: str
    language_mix: dict[str, float]
    average_words: float
    emoji_frequency: float
    common_phrases: list[str] = field(default_factory=list)
    greetings: list[str] = field(default_factory=list)
    endings: list[str] = field(default_factory=list)


def build_response_style(style: WritingStyle | None) -> ResponseStyle | None:
    """Convert a :class:`WritingStyle` ORM model into a :class:`ResponseStyle`.

    Returns ``None`` when *style* is ``None`` or contains no usable data.
    """
    if style is None:
        return None

    emoji_usage = style.emoji_usage or {}
    emoji_frequency = emoji_usage.get("frequency", 0.0)

    return ResponseStyle(
        tone=style.tone or "neutral",
        language_mix=style.language_mix or {},
        average_words=style.average_words_per_message or 0.0,
        emoji_frequency=float(emoji_frequency),
        common_phrases=style.common_phrases or [],
        greetings=style.common_greetings or [],
        endings=style.common_endings or [],
    )
