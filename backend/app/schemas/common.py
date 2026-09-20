"""Shared schema primitives."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Fact(BaseModel):
    """A single extracted profile fact with provenance + confidence.

    Confirmed facts carry a high confidence; uncertain AI-generated guesses
    keep a low confidence and are never presented as fact.
    """

    value: str
    source_message_id: Optional[int] = None
    source_text: str = ""
    confidence: float = 0.5
    created_at: str = ""