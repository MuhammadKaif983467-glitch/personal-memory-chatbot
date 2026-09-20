"""Logging setup.

Message content is private; by default we log counts, ids and truncated
snippets only. ``safe_snippet`` clips any text before it is logged.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"pmc.{name}")


def safe_snippet(text: str, limit: int = 120) -> str:
    """Clip a text for safe logging (never log full private messages)."""
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit] + "..."