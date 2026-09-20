"""OpenAI-backed provider (chat + embeddings).

Kept so the application can switch back to the native OpenAI API without code
changes. When ``AI_PROVIDER=openai`` (or ``auto`` with an OpenAI key and no
OpenRouter key) this provider is selected. Errors are classified the same way
as the OpenRouter provider.
"""

from __future__ import annotations

import time
from typing import Optional, Sequence

from app.ai.base import AIProvider
from app.ai.errors import REASON_MISSING_KEY, classify_error, provider_error
from app.core.config import Settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger

logger = get_logger("openai")

_MAX_RETRIES = 3
_SLEEP_BASE = 2.0
_TIMEOUT = 60.0


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise provider_error(
                "OPENAI_API_KEY is not set. Add it to your .env file or use "
                "AI_PROVIDER=mock/local to run without a key.",
                reason=REASON_MISSING_KEY,
            )
        self._settings = settings
        self._api_key = settings.openai_api_key
        self._chat_model = settings.chat_model
        self._embedding_model = settings.embedding_model
        self._client = None

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @property
    def available(self) -> bool:
        return True

    @property
    def chat_model_name(self) -> Optional[str]:
        return self._chat_model

    @property
    def embedding_model_name(self) -> Optional[str]:
        return self._embedding_model

    @property
    def embedding_model(self) -> str:
        return f"{self.name}:{self._embedding_model}"

    def _client_open(self):
        if self._client is None:
            import openai

            self._client = openai.OpenAI(
                api_key=self._api_key,
                timeout=_TIMEOUT,
                max_retries=0,  # retries are handled by the _MAX_RETRIES loop
            )
        return self._client

    def generate(self, system_prompt: str, messages: Sequence[dict]) -> str:
        payload = [{"role": "system", "content": system_prompt}, *messages]
        last_error: ProviderError | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client_open().chat.completions.create(
                    model=self._chat_model,
                    messages=payload,
                    temperature=0.4,
                    max_tokens=700,
                )
                return response.choices[0].message.content or ""
            except ProviderError:
                raise
            except Exception as exc:  # network / rate-limit / api errors
                last_error = classify_error(exc, provider=self.name, operation="chat")
                if last_error.retryable and attempt < _MAX_RETRIES - 1:
                    time.sleep(_SLEEP_BASE * (2 ** attempt))
                    continue
                break
        logger.warning("OpenAI chat call failed: %s", last_error)
        raise last_error or provider_error(
            "The AI provider could not generate a response. Please try again later."
        )

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if not texts:
            return []
        try:
            response = self._client_open().embeddings.create(
                model=self._embedding_model, input=list(texts)
            )
            return [item.embedding for item in response.data]
        except ProviderError:
            raise
        except Exception as exc:
            raise classify_error(exc, provider=self.name, operation="embedding") from exc