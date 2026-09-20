"""AI provider factory.

Resolution order:
  openrouter -> real OpenRouter provider (requires OPENROUTER_API_KEY)
  openai     -> real OpenAI provider (requires OPENAI_API_KEY)
  mock       -> deterministic fake provider (tests)
  local      -> offline heuristic provider
  auto       -> openrouter when a key is present, else openai when a key is
               present, otherwise local
"""

from __future__ import annotations

import logging

from app.ai.base import AIProvider
from app.core.config import Settings

logger = logging.getLogger("pmc.ai")


def get_provider(settings: Settings) -> AIProvider:
    mode = settings.ai_provider or "auto"

    if mode == "mock":
        from app.ai.providers.mock_provider import MockProvider

        return MockProvider()

    if mode == "openrouter":
        from app.ai.openrouter_provider import OpenRouterProvider

        return OpenRouterProvider(settings)

    if mode == "openai":
        from app.ai.openai_provider import OpenAIProvider

        return OpenAIProvider(settings)

    if mode == "local":
        from app.ai.providers.local_provider import LocalProvider

        return LocalProvider()

    if mode == "auto":
        if settings.openrouter_api_key or settings.openrouter_api_key_1 or settings.openrouter_api_key_2:
            from app.ai.openrouter_provider import OpenRouterProvider

            return OpenRouterProvider(settings)
        if settings.openai_api_key:
            from app.ai.openai_provider import OpenAIProvider

            return OpenAIProvider(settings)
        logger.warning("No API key configured - falling back to the local offline provider.")
        from app.ai.providers.local_provider import LocalProvider

        return LocalProvider()

    raise ValueError(f"Unknown ai_provider setting: {mode!r}")