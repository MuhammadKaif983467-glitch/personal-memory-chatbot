"""Person identity and speaker mapping.

Resolves a Person ORM model into display and API-compatible identity
information for prompt assembly and response construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PersonIdentity:
    """Resolved person identity.

    Attributes
    ----------
    person_name:
        Primary name from the Person record.
    relationship:
        Relationship label (e.g. ``"friend"``, ``"colleague"``).
    display_name:
        Best human-readable name (falls back to person_name).
    internal_role:
        API-compatible role string: ``"assistant"`` for the person,
        ``"user"`` for the human side.
    """

    person_name: str
    relationship: str
    display_name: str
    internal_role: str


def resolve_identity(
    person: Optional[object],
    user_name: str = "me",
) -> PersonIdentity:
    """Resolve person identity for display and API.

    Parameters
    ----------
    person:
        A Person ORM model (or any object with ``name`` and
        ``relationship_type`` attributes).  Falls back to safe defaults
        when ``None``.
    user_name:
        Label for the human side of the conversation.

    Returns
    -------
    PersonIdentity
        Structured identity ready for prompt and API use.
    """
    if person is None:
        return PersonIdentity(
            person_name="Unknown",
            relationship="unknown",
            display_name="Unknown",
            internal_role="assistant",
        )

    name = getattr(person, "name", "Unknown")
    relationship = getattr(person, "relationship_type", "unknown")
    aliases = getattr(person, "aliases", []) or []

    # Use the first alias as a more natural display name if available.
    display_name = aliases[0] if aliases else name

    return PersonIdentity(
        person_name=name,
        relationship=relationship,
        display_name=display_name,
        internal_role="assistant",
    )
