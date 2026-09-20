"""Timestamp parsing / formatting.

Imported chat exports use many date formats; we normalize everything to
timezone-aware UTC datetimes. Naive times are assumed to be UTC.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

ISO_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y %H:%M",
    "%Y-%m-%d",
    "%d-%m-%Y",
]

_EPOCH_INT = re.compile(r"^\d{10,13}(\.\d+)?$")


def parse_timestamp(value: object) -> Optional[datetime]:
    """Parse many common timestamp shapes; returns UTC datetime or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        if _EPOCH_INT.match(str(value)):
            seconds = float(value) if value < 10**11 else float(value) / 1000.0
            dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        else:
            return None
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if _EPOCH_INT.match(text):
            return parse_timestamp(float(text))
        dt = None
        for fmt in ISO_FORMATS:
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def format_timestamp(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None