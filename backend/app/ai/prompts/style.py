"""Communication style constraints derived from a WritingStyle model."""

from __future__ import annotations

from app.database.models import WritingStyle


def style_section(style: WritingStyle | None, person_name: str) -> str:
    """Convert :class:`WritingStyle` data into response-generation constraints.

    Parameters
    ----------
    style:
        Analyzed writing-style record for the person, or ``None`` if no
        analysis has been performed yet.
    person_name:
        Display name used when referencing the person in generated lines.
    """
    if style is None:
        return ""

    lines: list[str] = []

    if style.common_words:
        lines.append(
            f"- Words {person_name} uses frequently: "
            + ", ".join(style.common_words[:12])
        )

    if style.common_phrases:
        lines.append(
            f"- Phrases {person_name} often says: "
            + "; ".join(f'"{p}"' for p in style.common_phrases[:6])
        )

    emoji_usage = style.emoji_usage or {}
    if emoji_usage.get("common_emojis"):
        emojis = " ".join(emoji_usage["common_emojis"][:6])
        lines.append(f"- Emojis {person_name} tends to use: {emojis}")

    if style.average_message_length and style.average_message_length > 0:
        lines.append(
            f"- Typical message length: ~{style.average_message_length:.0f} characters "
            f"({style.average_words_per_message:.0f} words). "
            "Match this length unless the question requires more detail."
        )

    if style.tone and style.tone.lower() not in ("neutral", "unknown", ""):
        lines.append(f"- Tone: {style.tone}")

    if style.language_mix and len(style.language_mix) > 1:
        langs = ", ".join(
            f"{k} {v:.0%}" for k, v in style.language_mix.items()
        )
        lines.append(f"- Languages used: {langs}")

    if style.common_greetings:
        lines.append(
            f"- Common greetings: {', '.join(style.common_greetings[:4])}"
        )

    if style.common_endings:
        lines.append(
            f"- Common sign-offs: {', '.join(style.common_endings[:4])}"
        )

    if not lines:
        return ""

    return (
        "\nSTYLE GUIDELINES — match how this person actually communicates:\n"
        + "\n".join(lines)
        + "\n"
    )
