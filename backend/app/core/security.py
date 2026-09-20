"""Privacy helpers.

The core privacy rule of this project: you must NOT process another person's
chat data without their consent. We enforce that at import time and we scrub
anything that looks like a secret before it can reach logs.
"""

from __future__ import annotations

import re
from typing import Optional

from app.core.config import Settings
from app.core.exceptions import ConsentRequiredError

# Common secret patterns used to redact log lines before they are written.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"[A-Za-z0-9]{40,}"),
    re.compile(r"(api[_-]?key|token|password)\s*[:=]\s*\S+", re.IGNORECASE),
]


def require_consent(consent_confirmed: bool, settings: Settings) -> None:
    """Raise unless the caller explicitly confirmed permission to process data."""
    if settings.consent_required and not consent_confirmed:
        raise ConsentRequiredError(
            "Consent is required: confirm that you have permission to process this conversation data.",
        )


def redact(text: str) -> str:
    """Replace likely secrets with a placeholder (safe for logs/errors)."""
    result = text
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def safe_error_message(message: str) -> str:
    """Return a user-friendly, secret-free version of an error message."""
    return redact(str(message))[:500]