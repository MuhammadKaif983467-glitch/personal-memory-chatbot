"""V3.4 Phases 8-10: Provider diagnostics and offline degradation tests."""

import pytest
from unittest.mock import MagicMock
from app.services.provider_diagnostics import (
    ProviderState, ProviderDiagnostics, OfflineDegradation,
)


class TestOfflineDegradation:
    def test_initial_state_unknown(self):
        deg = OfflineDegradation()
        assert deg.state == ProviderState.UNKNOWN
        assert not deg.is_online
        assert not deg.is_degraded
        assert not deg.is_offline

    def test_success_sets_healthy(self):
        deg = OfflineDegradation()
        deg.record_success()
        assert deg.state == ProviderState.HEALTHY
        assert deg.is_online

    def test_failure_sets_degraded(self):
        deg = OfflineDegradation()
        deg.record_success()
        deg.record_failure("timeout")
        assert deg.state == ProviderState.DEGRADED
        assert deg.is_degraded

    def test_recovery_after_failure(self):
        deg = OfflineDegradation()
        deg.record_failure("network")
        deg.record_recovery()
        assert deg.state == ProviderState.RECOVERING

    def test_success_after_recovery(self):
        deg = OfflineDegradation()
        deg.record_failure("network")
        deg.record_recovery()
        deg.record_success()
        assert deg.state == ProviderState.HEALTHY


class TestProviderDiagnostics:
    def test_diagnostics_no_secrets(self):
        diag = ProviderDiagnostics(
            configured=True,
            provider_name="openrouter",
            chat_model="gpt-4o-mini",
            state="healthy",
        )
        d = diag
        assert "sk-" not in str(d)
        assert d.provider_name == "openrouter"

    def test_diagnostics_from_provider(self):
        provider = MagicMock()
        provider.configured = True
        provider.name = "openrouter"
        provider.chat_model_name = "gpt-4o-mini"
        provider.embedding_model_name = "text-embedding-3-small"
        provider.offline = False

        deg = OfflineDegradation()
        diag = deg.get_diagnostics(provider)
        assert diag.configured is True
        assert diag.provider_name == "openrouter"
        assert diag.chat_model == "gpt-4o-mini"

    def test_diagnostics_offline_provider(self):
        provider = MagicMock()
        provider.configured = False
        provider.offline = True
        provider.name = "local"

        deg = OfflineDegradation()
        diag = deg.get_diagnostics(provider)
        assert diag.offline_mode is True
