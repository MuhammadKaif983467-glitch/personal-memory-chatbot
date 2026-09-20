"""Lightweight in-process metrics counters used for observability.

Values are aggregated in memory and never contain message content.
"""

from __future__ import annotations

import threading
import time
from typing import Dict


class Metrics:
    def __init__(self) -> None:
        self._counts: Dict[str, int] = {}
        self._lock = threading.Lock()
        self.started_at = time.time()

    def inc(self, key: str, delta: int = 1) -> None:
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + delta

    def record(self, key: str, ms: float) -> None:
        with self._lock:
            self._counts[key] = ms

    def snapshot(self) -> dict:
        with self._lock:
            counts = dict(self._counts)
        counts["uptime_seconds"] = round(time.time() - self.started_at, 2)
        return counts