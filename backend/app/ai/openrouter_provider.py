"""OpenRouter-backed provider (chat + embeddings).

OpenRouter exposes an OpenAI-compatible API, so this provider uses the official
``openai`` SDK by changing the base URL and key only:

* chat:      POST {base_url}/chat/completions   model = settings.openrouter_chat_model
* embeddings: POST {base_url}/embeddings         model = settings.openrouter_embedding_model

Vectors are validated against the expected dimension so a model change never
silently produces garbage similarity scores. Errors are classified (auth,
quota, rate-limit, invalid model, timeout, network, provider) and never include
an API key.
"""

from __future__ import annotations

import time
from typing import Optional, Sequence

from app.ai.base import AIProvider
from app.ai.errors import (
    REASON_INVALID_MODEL,
    REASON_MISSING_KEY,
    classify_error,
    provider_error,
)
from app.core.config import Settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger

logger = get_logger("openrouter")

try:
    import openai  # noqa: E402  (OpenAI-compatible SDK, also used for OpenRouter)
except Exception:  # pragma: no cover - environment without the SDK
    openai = None  # type: ignore[assignment]

_MAX_RETRIES = 3
_SLEEP_BASE = 2.0
_TIMEOUT = 60.0
_EMBED_MAX_RETRIES = 10


class OpenRouterProvider(AIProvider):
    name = "openrouter"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Key separation: OPENROUTER_API_KEY_1 -> embeddings,
        # OPENROUTER_API_KEY_2 -> chat, each falling back to the legacy key.
        self._chat_api_key = settings.openrouter_chat_api_key
        self._embed_api_key = settings.openrouter_embedding_api_key
        self._base_url = (settings.openrouter_base_url or "https://openrouter.ai/api/v1").rstrip("/")
        self._chat_models = list(dict.fromkeys(settings.chat_model_chain)) or [settings.openrouter_chat_model]
        self._embedding_models = list(dict.fromkeys(settings.embedding_model_chain)) or [
            settings.openrouter_embedding_model
        ]
        self._chat_model = self._chat_models[0] if self._chat_models else "openai/gpt-4o-mini"
        self._embedding_model = self._embedding_models[0] if self._embedding_models else "openai/text-embedding-3-small"
        self._embedding_dim = settings.openrouter_embedding_dimensions
        self._active_embedding_model: Optional[str] = None
        self._chat_client = None
        self._embed_client = None
        self._client_failed = False

    # ---- configuration surface (secret-free) ----

    @property
    def configured(self) -> bool:
        return bool(self._chat_api_key) or bool(self._embed_api_key)

    @property
    def chat_key_configured(self) -> bool:
        return bool(self._chat_api_key)

    @property
    def embedding_key_configured(self) -> bool:
        return bool(self._embed_api_key)

    @property
    def available(self) -> bool:
        return self._chat_client is not None or self._embed_client is not None or self.configured

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def chat_model_name(self) -> Optional[str]:
        return self._chat_model

    @property
    def embedding_model_name(self) -> Optional[str]:
        return self._active_embedding_model or self._embedding_model

    @property
    def embedding_model(self) -> str:
        """Identifier of the embedding model actually in use (per-vector tag)."""
        active = self._active_embedding_model or self._embedding_model
        return f"{self.name}:{active}"

    @property
    def embedding_dim(self) -> Optional[int]:
        return self._embedding_dim

    def _require_key(self, api_key: str, operation: str) -> None:
        if api_key:
            return
        self._client_failed = True
        if operation == "chat":
            message = (
                "The chat API key is not set (OPENROUTER_API_KEY_2 or "
                "OPENROUTER_API_KEY). Add it to your .env file or use "
                "AI_PROVIDER=mock/local to run without a key."
            )
        else:
            message = (
                "The embedding API key is not set (OPENROUTER_API_KEY_1 or "
                "OPENROUTER_API_KEY). Add it to your .env file or use "
                "AI_PROVIDER=mock/local to run without a key."
            )
        raise provider_error(message, reason=REASON_MISSING_KEY)

    def _client_chat(self):
        if self._chat_client is None:
            self._require_key(self._chat_api_key, "chat")
            if openai is None:
                self._client_failed = True
                raise provider_error(
                    "The OpenAI SDK is not installed. Run `pip install openai`.",
                    reason=REASON_MISSING_KEY,
                )
            try:
                self._chat_client = openai.OpenAI(
                    api_key=self._chat_api_key,
                    base_url=self._base_url,
                    timeout=_TIMEOUT,
                    max_retries=0,  # retries are handled by _chat_once/_embed_once
                )
            except Exception as exc:
                self._client_failed = True
                raise classify_error(exc, provider=self.name, operation="connection") from exc
        return self._chat_client

    def _client_embed(self):
        if self._embed_client is None:
            self._require_key(self._embed_api_key, "embedding")
            if openai is None:
                self._client_failed = True
                raise provider_error(
                    "The OpenAI SDK is not installed. Run `pip install openai`.",
                    reason=REASON_MISSING_KEY,
                )
            try:
                self._embed_client = openai.OpenAI(
                    api_key=self._embed_api_key,
                    base_url=self._base_url,
                    timeout=_TIMEOUT,
                    max_retries=0,  # retries are handled by _chat_once/_embed_once
                )
            except Exception as exc:
                self._client_failed = True
                raise classify_error(exc, provider=self.name, operation="connection") from exc
        return self._embed_client

    # ---- chat ----

    def generate(self, system_prompt: str, messages: Sequence[dict]) -> str:
        payload = [{"role": "system", "content": system_prompt}, *messages]
        models = self._chat_models
        last_error: ProviderError | None = None
        for model in models:
            try:
                return self._chat_once(model, payload)
            except ProviderError as exc:
                if exc.reason == REASON_INVALID_MODEL and len(models) > 1:
                    logger.warning(
                        "Chat model %r not available on OpenRouter, trying the next configured model.", model
                    )
                    last_error = exc
                    continue
                raise
        raise last_error or provider_error(
            "The AI provider could not generate a response. Please try again later."
        )

    def _chat_once(self, model: str, payload: Sequence[dict]) -> str:
        """Run one chat completions call for `model` with transient retries."""
        last_error: ProviderError | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client_chat().chat.completions.create(
                    model=model,
                    messages=payload,
                    temperature=0.4,
                    max_tokens=700,
                )
                content = response.choices[0].message.content or ""
                if not content.strip():
                    raise provider_error(
                        "The AI provider returned an empty response.",
                        reason=REASON_INVALID_MODEL,
                    )
                return content
            except ProviderError:
                raise
            except Exception as exc:  # network / rate-limit / api errors
                last_error = classify_error(exc, provider=self.name, operation="chat")
                if last_error.retryable and attempt < _MAX_RETRIES - 1:
                    time.sleep(_SLEEP_BASE * (2 ** attempt))
                    continue
                break
        raise last_error or provider_error(
            "The AI provider could not generate a response. Please try again later."
        )

    # ---- embeddings ----

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if not texts:
            return []
        models = self._embedding_models
        last_error: ProviderError | None = None
        for model in models:
            try:
                vectors = self._embed_once(model, texts)
            except ProviderError as exc:
                if exc.reason in (REASON_INVALID_MODEL,) and len(models) > 1:
                    logger.warning(
                        "Embedding model %r unusable on OpenRouter, trying the next configured model.", model
                    )
                    last_error = exc
                    continue
                raise
            self._active_embedding_model = model
            return vectors
        raise last_error or provider_error(
            "No embedding model could produce vectors for this query.",
            reason=REASON_INVALID_MODEL,
        )

    def _embed_once(self, model: str, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        kwargs: dict = {"model": model, "input": list(texts)}
        if self._embedding_dim:
            kwargs["dimensions"] = self._embedding_dim
        for attempt in range(_EMBED_MAX_RETRIES):
            try:
                response = self._client_embed().embeddings.create(**kwargs)
                vectors = [item.embedding for item in response.data]
            except ProviderError:
                raise
            except Exception as exc:
                err = classify_error(exc, provider=self.name, operation="embedding")
                if not err.retryable or attempt >= _EMBED_MAX_RETRIES - 1:
                    raise err from exc
                sleep_seconds = self._embed_backoff(exc, attempt)
                logger.info(
                    "Embedding call rate-limited/transient (%s); waiting %.0fs before retry (%s/%s).",
                    err.reason,
                    sleep_seconds,
                    attempt + 1,
                    _EMBED_MAX_RETRIES,
                )
                time.sleep(sleep_seconds)
                continue
            for vector in vectors:
                if self._embedding_dim and len(vector) != self._embedding_dim:
                    raise provider_error(
                        "Embedding provider returned an unexpected vector dimension "
                        f"(expected {self._embedding_dim}, got {len(vector)}). "
                        "The embedding model configuration may have changed.",
                        reason=REASON_INVALID_MODEL,
                    )
            return vectors
        # All retries exhausted without a raise: the loop always returns or
        # raises, so this fallback is unreachable; kept as a type-guard.
        raise provider_error(
            "No embedding model could produce vectors for this query.",
            reason=REASON_INVALID_MODEL,
        )

    def _embed_backoff(self, exc: Exception, attempt: int) -> float:
        """Sleep time before retrying an embedding call.

        Prefers the provider-supplied ``x-ratelimit-reset`` timestamp so the
        retry lands just after the window opens, falling back to exponential
        backoff. Capped so a long wait never blocks the process forever.
        """
        reset_ms: Optional[float] = None
        headers = getattr(exc, "headers", None) or {}
        reset_value = headers.get("x-ratelimit-reset")
        if reset_value:
            try:
                reset_ms = float(reset_value)
            except (TypeError, ValueError):
                reset_ms = None
        now_ms = time.time() * 1000.0
        if reset_ms and reset_ms > now_ms:
            wait = (reset_ms - now_ms) / 1000.0 + 1.0
        else:
            wait = _SLEEP_BASE * (2 ** attempt)
        return min(max(wait, 1.0), 120.0)