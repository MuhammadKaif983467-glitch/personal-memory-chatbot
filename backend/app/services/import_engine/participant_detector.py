"""Auto-detect participants from normalized messages."""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from app.services.import_engine.normalizer import NormalizedMessage


def detect_participants(messages: Sequence[NormalizedMessage]) -> list:
    """Return participant names sorted by message count descending."""
    counter: Counter = Counter()
    for msg in messages:
        if not msg.is_system and msg.sender:
            counter[msg.sender] += 1
    return [name for name, _ in counter.most_common()]
