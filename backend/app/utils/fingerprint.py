"""Conversation fingerprinting for stable deduplication.

A conversation fingerprint is a SHA-256 hash of stable attributes:
  - project_id (or empty if None)
  - source/platform
  - normalized participants (sorted names)
  - first message timestamp
  - last message timestamp
  - total message count
  - first message sample (normalized, first 100 chars)
  - last message sample (normalized, last 100 chars)

This allows detecting the same conversation imported under different filenames
or titles, while keeping genuinely different conversations separate.
"""

from __future__ import annotations

import hashlib
from typing import Optional, Sequence


def compute_conversation_fingerprint(
    project_id: Optional[int],
    source: str,
    participant_names: Sequence[str],
    started_at: Optional[str] = None,
    ended_at: Optional[str] = None,
    message_count: int = 0,
    first_message_sample: str = "",
    last_message_sample: str = "",
) -> str:
    """Compute a stable SHA-256 fingerprint for a conversation."""
    parts = [
        str(project_id) if project_id is not None else "",
        source.strip().lower(),
        ",".join(sorted(name.strip().lower() for name in participant_names if name.strip())),
        started_at or "",
        ended_at or "",
        str(message_count),
        _normalize_sample(first_message_sample),
        _normalize_sample(last_message_sample),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_sample(text: str) -> str:
    """Normalize a message sample for fingerprinting."""
    if not text:
        return ""
    normalized = text.strip().lower()
    if len(normalized) > 100:
        normalized = normalized[:100]
    return normalized
