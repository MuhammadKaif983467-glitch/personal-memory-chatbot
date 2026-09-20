"""Structured application exceptions with safe HTTP mappings.

Nothing here should ever contain secrets or full private message bodies.
"""

from __future__ import annotations

from typing import Optional


class ChatbotError(Exception):
    """Base class for all application errors."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: Optional[list] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.details = details or []
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message, "details": self.details}


class NotFoundError(ChatbotError):
    status_code = 404
    code = "not_found"


class ImportValidationError(ChatbotError):
    status_code = 422
    code = "import_validation_error"


class ConsentRequiredError(ChatbotError):
    status_code = 403
    code = "consent_required"


class ForbiddenError(ChatbotError):
    status_code = 403
    code = "forbidden"


class ProviderError(ChatbotError):
    """AI provider failure with a classified ``reason``.

    ``reason`` is machine-readable so the API can return a controlled,
    user-facing error instead of an opaque 500/502 (e.g. quota vs auth vs
    rate-limit vs invalid model). ``retryable`` tells the caller whether a
    retry with backoff is sensible.
    """

    status_code = 502
    code = "ai_provider_error"

    def __init__(
        self,
        message: str,
        *,
        reason: str = "provider_error",
        retryable: bool = False,
        details: Optional[list] = None,
        status_code: Optional[int] = None,
    ):
        super().__init__(message, details=details, status_code=status_code)
        self.reason = reason
        self.retryable = retryable

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["reason"] = self.reason
        data["retryable"] = self.retryable
        return data


class ConflictError(ChatbotError):
    status_code = 409
    code = "conflict"