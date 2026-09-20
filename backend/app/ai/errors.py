"""AI provider error classification.

Turns arbitrary provider/transport exceptions into a classified
:class:`~app.core.exceptions.ProviderError` so the API can return a useful,
secret-free error instead of an opaque 500/502. Nothing here ever includes an
API key: only the status, the (sanitized) message and the reason family.

Reason families:

* ``missing_api_key``       - no key configured at all
* ``authentication_failed`` - 401/403 (bad or revoked key)
* ``insufficient_quota``    - 402 or a 429 that explicitly names quota/credit
* ``rate_limited``          - 429 (plain "too many requests")
* ``invalid_model``         - 400/404 naming a model
* ``timeout``               - request exceeded the timeout budget
* ``network_error``         - transport-level failure (DNS/connect)
* ``provider_error``        - upstream 5xx or unexpected provider response
* ``application_error``     - our own request was malformed
"""

from __future__ import annotations

from typing import Optional

from app.core.exceptions import ProviderError

REASON_MISSING_KEY = "missing_api_key"
REASON_AUTH = "authentication_failed"
REASON_QUOTA = "insufficient_quota"
REASON_RATE_LIMIT = "rate_limited"
REASON_INVALID_MODEL = "invalid_model"
REASON_TIMEOUT = "timeout"
REASON_NETWORK = "network_error"
REASON_PROVIDER = "provider_error"
REASON_APPLICATION = "application_error"

_STATUS_FOR_REASON = {
    REASON_MISSING_KEY: 500,
    REASON_AUTH: 401,
    REASON_QUOTA: 402,
    REASON_RATE_LIMIT: 429,
    REASON_INVALID_MODEL: 400,
    REASON_TIMEOUT: 504,
    REASON_NETWORK: 502,
    REASON_PROVIDER: 502,
    REASON_APPLICATION: 500,
}

_QUOTA_HINTS = (
    "insufficient_quota",
    "quota",
    "credit balance",
    "exceeded your current quota",
    "not enough credits",
    "billing",
    "exhausted",
    "payment required",
)

_MODEL_HINTS = (
    "model",
    "not exist",
    "unknown model",
    "does not exist",
    "unavailable model",
    "not found",
)

try:  # optional: only used to recognise the provider's typed errors
    import openai
except Exception:  # pragma: no cover - environment without the SDK
    openai = None  # type: ignore[assignment]


def provider_error(
    message: str,
    reason: str = REASON_PROVIDER,
    *,
    retryable: bool = False,
    status_code: Optional[int] = None,
) -> ProviderError:
    return ProviderError(
        message,
        reason=reason,
        retryable=retryable,
        status_code=status_code if status_code is not None else _STATUS_FOR_REASON.get(reason, 502),
    )


def classify_error(
    exc: Exception,
    *,
    provider: str = "provider",
    operation: str = "request",
) -> ProviderError:
    """Classify any exception into a safe ProviderError.

    ``provider`` and ``operation`` are used only for the human-readable
    message; neither is ever interleaved with a secret.
    """
    status = getattr(exc, "status_code", None)
    message = str(getattr(exc, "message", "") or exc)
    low = message.casefold()

    reason = _classify(status, low, exc)
    retryable = reason in (REASON_RATE_LIMIT, REASON_NETWORK, REASON_PROVIDER, REASON_TIMEOUT)
    status_code = _STATUS_FOR_REASON.get(reason, 502)

    friendly = _friendly(reason, provider, operation)
    # Strip anything that looks like a key/token before it can leak into logs.
    safe_message = _sanitize(message)
    detail = f"{friendly} {safe_message}" if safe_message else friendly
    return provider_error(detail, reason=reason, retryable=retryable, status_code=status_code)


def _classify(status, low: str, exc: Exception):
    if openai is not None:
        if isinstance(exc, openai.AuthenticationError):
            return REASON_AUTH
        if isinstance(exc, openai.PermissionDeniedError):
            return REASON_AUTH
        if isinstance(exc, openai.APITimeoutError):
            return REASON_TIMEOUT
        if isinstance(exc, openai.APIConnectionError):
            return REASON_NETWORK
        if isinstance(exc, openai.NotFoundError):
            return REASON_INVALID_MODEL
        if isinstance(exc, openai.RateLimitError):
            if any(hint in low for hint in _QUOTA_HINTS):
                return REASON_QUOTA
            return REASON_RATE_LIMIT
        if isinstance(exc, openai.BadRequestError):
            if any(hint in low for hint in _MODEL_HINTS):
                return REASON_INVALID_MODEL
            return REASON_APPLICATION
        if isinstance(exc, openai.InternalServerError):
            return REASON_PROVIDER
        if isinstance(exc, openai.APIStatusError):
            return REASON_PROVIDER

    if status == 401 or status == 403:
        return REASON_AUTH
    if status == 402:
        return REASON_QUOTA
    if status == 429:
        if any(hint in low for hint in _QUOTA_HINTS):
            return REASON_QUOTA
        return REASON_RATE_LIMIT
    if status == 404:
        return REASON_INVALID_MODEL
    if status == 400:
        if any(hint in low for hint in _MODEL_HINTS):
            return REASON_INVALID_MODEL
        return REASON_APPLICATION
    if status == 408:
        return REASON_TIMEOUT
    if status in (500, 502, 503, 504):
        return REASON_PROVIDER

    if isinstance(exc, TimeoutError):
        return REASON_TIMEOUT
    if _is_transport(exc):
        return REASON_NETWORK
    return REASON_PROVIDER if _looks_provider(low) else REASON_APPLICATION


def _is_transport(exc: Exception) -> bool:
    if isinstance(exc, ConnectionError):
        return True
    name = type(exc).__name__.casefold()
    return any(part in name for part in ("connection", "connect", "dns", "transport", "network"))


def _looks_provider(low: str) -> bool:
    return any(
        hint in low
        for hint in ("server error", "internal error", "bad gateway", "service unavailable", "upstream")
    )


def _friendly(reason: str, provider: str, operation: str) -> str:
    noun = f"{provider} {operation}"
    if reason == REASON_MISSING_KEY:
        return f"{provider} is not configured: no API key is set for {operation}."
    if reason == REASON_AUTH:
        return f"{noun} was rejected by the provider: the API key is invalid or expired."
    if reason == REASON_QUOTA:
        return f"The AI provider blocked {operation} because the account has no credits left."
    if reason == REASON_RATE_LIMIT:
        return f"The AI provider is rate-limiting our {operation} requests. Try again shortly."
    if reason == REASON_INVALID_MODEL:
        return f"The configured AI model is not available on the provider ({operation})."
    if reason == REASON_TIMEOUT:
        return f"The AI provider timed out during {operation}."
    if reason == REASON_NETWORK:
        return f"The AI provider could not be reached for {operation}."
    if reason == REASON_PROVIDER:
        return f"The AI provider failed while handling {operation}."
    return f"An invalid {operation} was sent to the AI provider."


def _sanitize(message: str) -> str:
    """Best-effort scrub of obvious credentials before logging/returning."""
    import re

    result = re.sub(r"sk-[A-Za-z0-9_\-]{10,}", "[redacted-key]", message)
    result = re.sub(r"sk-or-[A-Za-z0-9_\-]{10,}", "[redacted-key]", result)
    result = re.sub(r"(?i)(authorization\s*[:=]\s*\S+)", "[redacted]", result)
    result = re.sub(r"(?i)(bearer\s+[A-Za-z0-9._\-]{8,})", "[redacted]", result)
    return result[:300]