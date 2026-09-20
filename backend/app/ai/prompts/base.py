"""Composes the full system prompt from modular pieces."""

from __future__ import annotations

from app.database.models import WritingStyle
from app.ai.prompts.identity import identity_section
from app.ai.prompts.style import style_section
from app.ai.prompts.memory import memory_section
from app.ai.prompts.safety import safety_section
from app.ai.prompts.response import response_section, context_footer


def build_system_prompt(
    person_name: str,
    relationship: str,
    confidence_level: str,
    context_text: str,
    style: WritingStyle | None = None,
) -> str:
    """Build the complete system prompt from modular sections.

    Parameters
    ----------
    person_name:
        Display name of the person whose memories are being queried.
    relationship:
        Relationship label (e.g. ``"friend"``).
    confidence_level:
        Retrieval confidence — ``"HIGH"``, ``"MEDIUM"``, or ``"LOW"``.
    context_text:
        Pre-assembled context string with ``[SECTION]``-labelled parts.
    style:
        Optional :class:`WritingStyle` record for persona-matching constraints.
    """
    parts: list[str] = [
        identity_section(person_name, relationship),
        style_section(style, person_name),
        memory_section(confidence_level),
        safety_section(),
        response_section(),
        "",
        context_footer(context_text),
    ]
    return "\n".join(parts)
