"""Provider diagnostics and offline degradation.

Provides:
- Safe provider diagnostics (no secrets exposed)
- Offline/degraded operation modes
- Provider health state tracking
- Graceful degradation when provider unavailable
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.core.logging import get_logger

logger = get_logger("provider_diagnostics")


class ProviderState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OPEN = "open"
    RECOVERING = "recovering"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


@dataclass
class ProviderDiagnostics:
    """Safe provider diagnostics — never exposes API keys or secrets."""
    configured: bool = False
    provider_name: str = ""
    chat_model: str = ""
    embedding_model: str = ""
    state: str = "unknown"
    circuit_state: str = ""
    last_success: float = 0.0
    last_failure_category: str = ""
    fallback_used: bool = False
    embedding_available: bool = False
    chat_available: bool = False
    offline_mode: bool = False


class OfflineDegradation:
    """Manages graceful degradation when providers are unavailable.

    When the provider is offline, the application should:
    - Continue serving existing data
    - Use lexical/FTS5 retrieval instead of vector
    - Use heuristic summaries instead of AI
    - Show clear UI status
    - Never claim AI responses when in offline mode
    """

    def __init__(self) -> None:
        self._state = ProviderState.UNKNOWN
        self._last_check = 0.0
        self._degraded_since: Optional[float] = None

    @property
    def state(self) -> ProviderState:
        return self._state

    @property
    def is_online(self) -> bool:
        return self._state in (ProviderState.HEALTHY,)

    @property
    def is_degraded(self) -> bool:
        return self._state in (ProviderState.DEGRADED, ProviderState.RECOVERING)

    @property
    def is_offline(self) -> bool:
        return self._state in (ProviderState.OPEN, ProviderState.DISABLED)

    def record_success(self) -> None:
        self._state = ProviderState.HEALTHY
        self._degraded_since = None
        self._last_check = time.time()

    def record_failure(self, category: str = "unknown") -> None:
        if self._state == ProviderState.HEALTHY:
            self._state = ProviderState.DEGRADED
            self._degraded_since = time.time()
        elif self._state == ProviderState.DEGRADED:
            # After sustained failures, go to OPEN
            if self._degraded_since and (time.time() - self._degraded_since) > 60:
                self._state = ProviderState.OPEN
        self._last_check = time.time()

    def record_recovery(self) -> None:
        self._state = ProviderState.RECOVERING
        self._last_check = time.time()

    def get_diagnostics(self, provider=None) -> ProviderDiagnostics:
        """Build safe diagnostics — never exposes secrets."""
        diag = ProviderDiagnostics(
            configured=bool(getattr(provider, "configured", False)),
            provider_name=getattr(provider, "name", "unknown"),
            chat_model=getattr(provider, "chat_model_name", "") or "",
            embedding_model=getattr(provider, "embedding_model_name", "") or "",
            state=self._state.value,
            offline_mode=getattr(provider, "offline", False),
            embedding_available=bool(getattr(provider, "configured", False)),
            chat_available=bool(getattr(provider, "configured", False)),
        )

        if hasattr(provider, "circuit_breaker"):
            cb = provider.circuit_breaker
            diag.circuit_state = cb.state if hasattr(cb, "state") else ""

        return diag
