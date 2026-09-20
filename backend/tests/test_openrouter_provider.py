"""Tests for OpenRouter configuration, provider behaviour and error handling.

The real API is never called: the OpenAI SDK inside the provider is replaced
with a fake client and classifier inputs are synthetic. The suite stays
hermetic and never needs a live key.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ai import openrouter_provider as orp
from app.ai.errors import (
    REASON_AUTH,
    REASON_INVALID_MODEL,
    REASON_MISSING_KEY,
    REASON_NETWORK,
    REASON_QUOTA,
    REASON_RATE_LIMIT,
    REASON_TIMEOUT,
    classify_error,
    provider_error,
)
from app.ai.factory import get_provider
from app.ai.openrouter_provider import OpenRouterProvider
from app.core.config import Settings
from app.core.exceptions import ProviderError
from app.factory import create_app
from app.services.dataset_import_service import DatasetImportService

OPENROUTER_TEST_KEY = "sk-or-test-key-0000000000000000"
CHAT_MODEL = "openai/gpt-4o-mini"
EMBED_MODEL = "openai/text-embedding-3-small"


class _FakeCompletions:
    def __init__(self, content="hello from openrouter"):
        self._content = content

    def create(self, **kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
        )


class _FakeEmbeddings:
    def __init__(self, dim=1536, refuse=None):
        self._dim = dim
        self._refuse = refuse
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        model = kwargs.get("model")
        if self._refuse and model in self._refuse:
            raise _PlainError(f"The model {model} does not exist", 404)
        count = len(kwargs.get("input", [])) or 1
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * self._dim) for _ in range(count)])


class _FakeClient:
    def __init__(self, content="hello from openrouter", dim=1536, api_key=None, base_url=None, timeout=None, refuse_chat=None, refuse_embeddings=None, **kwargs):
        # max_retries=0 is passed to real clients; fakes accept and ignore it.
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.chat = SimpleNamespace(completions=_FakeCompletions(content))
        self.embeddings = _FakeEmbeddings(dim, refuse=refuse_embeddings)


def _settings(**overrides) -> Settings:
    values = {
        "ai_provider": "openrouter",
        "openrouter_api_key": OPENROUTER_TEST_KEY,
        "openrouter_base_url": "https://openrouter.ai/api/v1",
        "openrouter_chat_model": CHAT_MODEL,
        "openrouter_embedding_model": EMBED_MODEL,
        "openrouter_embedding_dimensions": 1536,
        "vector_store": "simple",
    }
    values.update(overrides)
    return Settings(**values)


# ---- configuration ----

def test_settings_expose_openrouter_defaults():
    settings = _settings()
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.openrouter_chat_model == CHAT_MODEL
    assert settings.openrouter_embedding_model == EMBED_MODEL
    assert settings.openrouter_embedding_dimensions == 1536


def test_placeholder_key_is_treated_as_unset():
    settings = Settings(openrouter_api_key="your_openrouter_api_key_here")
    assert settings.openrouter_api_key == ""


def test_factory_selects_openrouter_provider():
    provider = get_provider(_settings())
    assert isinstance(provider, OpenRouterProvider)
    assert provider.name == "openrouter"
    assert provider.configured is True


def test_factory_auto_prefers_openrouter_over_openai():
    settings = Settings(
        ai_provider="auto",
        openrouter_api_key=OPENROUTER_TEST_KEY,
        openai_api_key="sk-another-test-key-0123456789abcdef",
    )
    assert isinstance(get_provider(settings), OpenRouterProvider)


def test_openrouter_missing_key_is_clear():
    provider = OpenRouterProvider(_settings(openrouter_api_key=""))
    assert provider.configured is False
    with pytest.raises(ProviderError) as exc:
        provider.embed(["hello"])
    assert exc.value.reason == REASON_MISSING_KEY


# ---- chat generation ----

def test_generate_uses_base_url_and_model(monkeypatch):
    captured = {}

    def fake_openai_class(api_key=None, base_url=None, timeout=None, **kwargs):
        # max_retries=0 mirrors the real client construction.
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        captured["timeout"] = timeout
        return _FakeClient()

    monkeypatch.setattr(orp.openai, "OpenAI", fake_openai_class)
    provider = OpenRouterProvider(_settings())
    reply = provider.generate("system", [{"role": "user", "content": "hi"}])
    assert reply == "hello from openrouter"
    assert captured["api_key"] == OPENROUTER_TEST_KEY
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert "sk-or" not in reply


def test_generate_empty_reply_is_provider_error(monkeypatch):
    monkeypatch.setattr(orp.openai, "OpenAI", lambda **kwargs: _FakeClient(content="   "))
    provider = OpenRouterProvider(_settings())
    with pytest.raises(ProviderError):
        provider.generate("s", [{"role": "user", "content": "q"}])


def test_chat_model_falls_back_to_next_model(monkeypatch):
    seen = []

    def fake_openai_class(**kwargs):
        client = _FakeClient(content="fallback-answer")

        class _Completions:
            def create(self, model, messages, temperature=0.4, max_tokens=700):
                seen.append(model)
                if model == CHAT_MODEL:
                    raise _PlainError("The model does not exist", 404)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="fallback-answer"))]
                )

        client.chat = SimpleNamespace(completions=_Completions())
        return client

    monkeypatch.setattr(orp.openai, "OpenAI", fake_openai_class)
    settings = _settings(
        openrouter_chat_model=f"{CHAT_MODEL},deepseek/deepseek-v4-flash-0731:free"
    )
    provider = OpenRouterProvider(settings)
    reply = provider.generate("s", [{"role": "user", "content": "q"}])
    assert reply == "fallback-answer"
    assert seen == [CHAT_MODEL, "deepseek/deepseek-v4-flash-0731:free"]


def test_embedding_model_falls_back_to_next_model(monkeypatch):
    seen = []

    def tracking_openai_class(**kwargs):
        client = _FakeClient(refuse_embeddings={EMBED_MODEL})
        inner = client.embeddings

        class _T:
            def create(self, **kw):
                seen.append(kw["model"])
                return inner.create(**kw)

        client.embeddings = _T()
        return client

    monkeypatch.setattr(orp.openai, "OpenAI", tracking_openai_class)
    settings = _settings(
        openrouter_embedding_model=f"{EMBED_MODEL},nvidia/llama-nemotron-embed-vl-1b-v2:free",
        openrouter_embedding_dimensions=1536,
    )
    provider = OpenRouterProvider(settings)
    vectors = provider.embed(["hello"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 1536
    assert seen == [EMBED_MODEL, "nvidia/llama-nemotron-embed-vl-1b-v2:free"]
    assert provider.embedding_model == "openrouter:nvidia/llama-nemotron-embed-vl-1b-v2:free"


def test_embedding_chain_primary_preferred_in_tag(app, db):
    """The per-vector tag reflects the first chain model actually in use."""
    from app.services.embedding_service import EmbeddingService

    openrouter = OpenRouterProvider(_settings())
    assert openrouter.embedding_model == f"openrouter:{EMBED_MODEL}"

    settings = _settings(openrouter_embedding_model=f"nvidia/llama-nemotron-embed-vl-1b-v2:free,{EMBED_MODEL}")
    provider = OpenRouterProvider(settings)
    assert provider.embedding_model == "openrouter:nvidia/llama-nemotron-embed-vl-1b-v2:free"


# ---- embeddings ----

def test_embed_uses_openrouter_model_and_dimension(monkeypatch):
    captured = {}

    def fake_openai_class(**kwargs):
        return _FakeClient()

    monkeypatch.setattr(orp.openai, "OpenAI", fake_openai_class)
    provider = OpenRouterProvider(_settings())
    cli = provider._client_embed()
    fake_embeddings = cli.embeddings  # noqa: F841
    vectors = provider.embed(["hello", "world"])
    assert len(vectors) == 2
    assert all(len(v) == 1536 for v in vectors)


def test_embed_rejects_wrong_dimension(monkeypatch):
    def fake_openai_class(**kwargs):
        return _FakeClient(dim=64)

    monkeypatch.setattr(orp.openai, "OpenAI", fake_openai_class)
    provider = OpenRouterProvider(_settings())
    with pytest.raises(ProviderError) as exc:
        provider.embed(["oops"])
    assert exc.value.reason == REASON_INVALID_MODEL


# ---- error classification ----

class _PlainError(Exception):
    def __init__(self, message="boom", status_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def test_classification_authentication():
    err = classify_error(_PlainError("Incorrect API key provided", 401))
    assert err.reason == REASON_AUTH
    assert err.status_code == 401


def test_classification_quota_status_402():
    err = classify_error(_PlainError("payment required", 402))
    assert err.reason == REASON_QUOTA
    assert err.status_code == 402


def test_classification_quota_hint_in_429():
    err = classify_error(_PlainError("You exceeded your current quota", 429))
    assert err.reason == REASON_QUOTA


def test_classification_rate_limit():
    err = classify_error(_PlainError("Rate limit reached", 429))
    assert err.reason == REASON_RATE_LIMIT
    assert err.retryable is True


def test_classification_invalid_model_404():
    err = classify_error(_PlainError("The model abcd does not exist", 404))
    assert err.reason == REASON_INVALID_MODEL


def test_classification_network():
    err = classify_error(ConnectionError("connect refused"))
    assert err.reason == REASON_NETWORK


def test_classification_timeout():
    err = classify_error(TimeoutError("timed out"))
    assert err.reason == REASON_TIMEOUT


def test_classification_never_leaks_key():
    err = classify_error(_PlainError("Authorization: Bearer sk-or-leaky-key-1234567890AB", 401))
    assert OPENROUTER_TEST_KEY not in str(err)
    assert "sk-or-leaky" not in err.message


def test_provider_error_round_trip_to_dict():
    err = provider_error("something failed", reason=REASON_QUOTA)
    data = err.to_dict()
    assert data["reason"] == REASON_QUOTA
    assert data["error"] == "ai_provider_error"
    assert "message" in data


# ---- embedding compatibility detection ----

def _seed_mock_vectors(app, db):
    context = app.state.context
    dataset = {
        "dataset_name": "Compat Test",
        "version": "1.0",
        "participants": [{"name": "Ali", "role": "Friend"}],
        "conversation": {"conversation_id": "c1", "title": "t", "source": "compat"},
        "designed_memory_facts": {"ali": [["preference", "Ali prefers coffee."]]},
        "intentional_corrections": [],
        "messages": [
            {
                "message_id": 1,
                "sender": "Ali",
                "timestamp": "2026-01-01T10:00:00",
                "content": "I like cricket",
                "message_type": "text",
            }
        ],
    }
    DatasetImportService(db, context.settings, context.embeddings).import_dataset(
        dataset, consent_confirmed=True
    )


def test_compatibility_detects_embedding_model_change(app, db):
    _seed_mock_vectors(app, db)
    context = app.state.context
    openrouter = OpenRouterProvider(_settings())
    from app.services.embedding_service import EmbeddingService

    probe = EmbeddingService(openrouter, context.vector_store)
    problems = probe.verify_compatible(db)
    assert problems, "expected a model mismatch to be reported"
    assert "openrouter" in " ".join(problems)

    with pytest.raises(ProviderError):
        probe.check_embedding_compatible(db)


def test_compatibility_passes_for_active_model(app, db):
    _seed_mock_vectors(app, db)
    context = app.state.context
    from app.services.embedding_service import EmbeddingService

    probe = EmbeddingService(context.provider, context.vector_store)  # mock provider
    assert probe.verify_compatible(db) == []
    probe.check_embedding_compatible(db)  # must not raise


def test_bulk_embedding_is_idempotent(app, db):
    from app.database.repositories import MemoryRepository
    from app.services.embedding_service import EmbeddingService

    _seed_mock_vectors(app, db)
    context = app.state.context
    memories = MemoryRepository(db).list_active()
    probe = EmbeddingService(context.provider, context.vector_store)
    first = probe.ensure_memory_embeddings(db, memories, chunk_size=2)
    assert first == len(memories)
    second = probe.ensure_memory_embeddings(db, memories, chunk_size=2)
    assert second == len(memories)  # refresh again is idempotent
    assert probe.memory_count() == len(memories)
    assert probe.verify_compatible(db) == []


def test_openrouter_settings_endpoint_is_secret_free(tmp_path, monkeypatch):
    monkeypatch.setattr(
        orp.openai,
        "OpenAI",
        lambda **kwargs: _FakeClient(),
    )
    app = create_app(
        {
            "ai_provider": "openrouter",
            "openrouter_api_key": OPENROUTER_TEST_KEY,
            "openrouter_chat_model": CHAT_MODEL,
            "openrouter_embedding_model": EMBED_MODEL,
            "vector_store": "simple",
            "database_url": f"sqlite:///{(tmp_path / 't.db').as_posix()}",
            "vector_db_path": str(tmp_path / "chroma"),
            "imports_dir": str(tmp_path / "imports"),
            "processed_dir": str(tmp_path / "processed"),
            "exports_dir": str(tmp_path / "exports"),
        }
    )
    client = TestClient(app)
    body = client.get("/settings").json()
    assert body["provider"] == "openrouter"
    assert body["api_key_configured"] is True
    assert body["auth_status"] == "configured"
    assert body["chat_model"] == CHAT_MODEL
    assert body["embedding_model"] == EMBED_MODEL
    assert OPENROUTER_TEST_KEY not in client.get("/settings").text
    health = client.get("/health").json()
    assert health["provider"] == "openrouter"
    assert health["embedding_model"] == EMBED_MODEL
    assert health["provider_auth_configured"] is True
    assert health["chat_auth_configured"] is True
    assert health["embedding_auth_configured"] is True
    assert health["tts_configured"] is False
    assert OPENROUTER_TEST_KEY not in client.get("/health").text


def test_openrouter_settings_never_contains_key_field(tmp_path, monkeypatch):
    monkeypatch.setattr(orp.openai, "OpenAI", lambda **kwargs: _FakeClient())
    app = create_app(
        {
            "ai_provider": "openrouter",
            "openrouter_api_key": OPENROUTER_TEST_KEY,
            "openrouter_chat_model": CHAT_MODEL,
            "openrouter_embedding_model": EMBED_MODEL,
            "vector_store": "simple",
            "database_url": f"sqlite:///{(tmp_path / 't.db').as_posix()}",
            "vector_db_path": str(tmp_path / "chroma"),
            "imports_dir": str(tmp_path / "imports"),
            "processed_dir": str(tmp_path / "processed"),
            "exports_dir": str(tmp_path / "exports"),
        }
    )
    client = TestClient(app)
    text = client.get("/settings").text
    assert "openrouter_api_key" not in text
    assert not re.search(r"sk-or-[A-Za-z0-9]{6,}", text)


# ---- live key separation (OPENROUTER_API_KEY_1 -> embeddings, _2 -> chat) ---

_EMBED_KEY = "sk-or-v1-embeddings-only-0000000000000000000000001"
_CHAT_KEY = "sk-or-v1-chat-only-000000000000000000000000002"


def test_split_key_routing_never_swaps(monkeypatch):
    """Chat calls must use KEY_2 and embedding calls KEY_1, never swapped."""
    captured = []

    def fake_openai_class(**kwargs):
        client = _FakeClient()
        client._used_key = kwargs.get("api_key")
        captured.append(client)
        return client

    monkeypatch.setattr(orp.openai, "OpenAI", fake_openai_class)
    settings = Settings(
        ai_provider="openrouter",
        openrouter_api_key_1=_EMBED_KEY,
        openrouter_api_key_2=_CHAT_KEY,
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_chat_model=CHAT_MODEL,
        openrouter_embedding_model=EMBED_MODEL,
        openrouter_embedding_dimensions=1536,
        vector_store="simple",
    )
    provider = OpenRouterProvider(settings)
    reply = provider.generate("s", [{"role": "user", "content": "hi"}])
    assert reply == "hello from openrouter"
    vectors = provider.embed(["hello"])
    assert len(vectors) == 1 and len(vectors[0]) == 1536
    used = [c._used_key for c in captured]
    assert used.count(_CHAT_KEY) == 1, f"chat expected KEY_2, got {used}"
    assert used.count(_EMBED_KEY) == 1, f"embeddings expected KEY_1, got {used}"
    assert _CHAT_KEY in used and _EMBED_KEY in used
    # no single client may have been handed the wrong key
    chat_clients = [c for c in captured if c._used_key == _CHAT_KEY]
    embed_clients = [c for c in captured if c._used_key == _EMBED_KEY]
    assert len(chat_clients) == 1 and len(embed_clients) == 1
    assert all(c._used_key != _EMBED_KEY for c in chat_clients)
    assert all(c._used_key != _CHAT_KEY for c in embed_clients)


def test_embedding_key_alone_does_not_enable_chat(monkeypatch):
    monkeypatch.setattr(orp.openai, "OpenAI", lambda **kwargs: _FakeClient())
    provider = OpenRouterProvider(
        _settings(openrouter_api_key="", openrouter_api_key_1=_EMBED_KEY)
    )
    assert provider.chat_key_configured is False
    assert provider.embedding_key_configured is True
    assert provider.configured is True
    with pytest.raises(ProviderError) as exc:
        provider.generate("s", [{"role": "user", "content": "hi"}])
    assert exc.value.reason == REASON_MISSING_KEY
    assert len(provider.embed(["hi"])) == 1  # embedding leg still works


def test_chat_key_alone_does_not_enable_embeddings(monkeypatch):
    monkeypatch.setattr(orp.openai, "OpenAI", lambda **kwargs: _FakeClient())
    provider = OpenRouterProvider(
        _settings(openrouter_api_key="", openrouter_api_key_2=_CHAT_KEY)
    )
    assert provider.chat_key_configured is True
    assert provider.embedding_key_configured is False
    assert provider.configured is True
    assert provider.generate("s", [{"role": "user", "content": "hi"}]) == "hello from openrouter"
    with pytest.raises(ProviderError) as exc:
        provider.embed(["hi"])
    assert exc.value.reason == REASON_MISSING_KEY


def test_settings_key_routing_properties():
    settings = Settings(
        ai_provider="openrouter",
        openrouter_api_key_1=_EMBED_KEY,
        openrouter_api_key_2=_CHAT_KEY,
    )
    assert settings.openrouter_embedding_api_key == _EMBED_KEY
    assert settings.openrouter_chat_api_key == _CHAT_KEY
    assert settings.chat_key_configured is True
    assert settings.embedding_key_configured is True
    assert settings.split_keys_in_use is True
    # single-key fallback: dedicated keys win, legacy key remains valid fallback
    legacy = Settings(
        ai_provider="openrouter",
        openrouter_api_key=OPENROUTER_TEST_KEY,
        openrouter_api_key_1=_EMBED_KEY,
    )
    assert legacy.openrouter_embedding_api_key == _EMBED_KEY
    assert legacy.openrouter_chat_api_key == OPENROUTER_TEST_KEY
    assert legacy.split_keys_in_use is False
    # legacy-only setup still works without the split keys
    old = Settings(ai_provider="openrouter", openrouter_api_key=OPENROUTER_TEST_KEY)
    assert old.openrouter_embedding_api_key == OPENROUTER_TEST_KEY
    assert old.openrouter_chat_api_key == OPENROUTER_TEST_KEY


def test_placeholder_split_keys_treated_as_unset():
    settings = Settings(
        openrouter_api_key_1="your_openrouter_api_key_here",
        openrouter_api_key_2="changeme",
    )
    assert settings.openrouter_api_key_1 == ""
    assert settings.openrouter_api_key_2 == ""
    assert settings.split_keys_in_use is False
    assert settings.chat_key_configured is False
    assert settings.embedding_key_configured is False