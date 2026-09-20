"""AI provider interface.

Application code depends only on this abstraction, so the OpenAI provider can
be replaced (local heuristic, Anthropic, Ollama, ...) without touching the
retrieval / context / chat logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence


class AIProvider(ABC):
    name: str = "base"

    # Whether the provider needs no external service (mock/local heuristics).
    # Offline providers also produce hash-style embeddings that have no
    # semantic cosine meaning, so retrieval re-ranks them lexically.
    offline: bool = False

    @property
    def configured(self) -> bool:
        """Whether the provider has everything it needs (e.g. an API key)."""
        return True

    @property
    def chat_model_name(self) -> Optional[str]:
        """Human-readable active chat model, or None for offline providers."""
        return None

    @property
    def embedding_model_name(self) -> Optional[str]:
        """Human-readable active embedding model, or None for offline providers."""
        return None

    @property
    def embedding_model(self) -> str:
        """Stable descriptor attached to stored vectors.

        Combines the provider name and embedding model so a model change is
        detectable at retrieval time (offline providers simply use the name,
        which keeps legacy records compatible).
        """
        return self.name

    @property
    def embedding_dim(self) -> Optional[int]:
        """Expected vector width, when the provider knows it."""
        return None

    @abstractmethod
    def generate(self, system_prompt: str, messages: Sequence[dict]) -> str:
        """Return the assistant's reply for a chat history."""

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Return one embedding vector per input text."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this provider can actually be used right now."""