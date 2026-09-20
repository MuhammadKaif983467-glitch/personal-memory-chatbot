"""Deterministic fake provider used by the test suite.

Produces stable hash-based embeddings (see utils/embeddings.py) and a fixed,
recognizable reply. Tests never need a real API key.
"""

from __future__ import annotations

from typing import Sequence

from app.ai.base import AIProvider
from app.utils.embeddings import hash_embedding

MOCK_EMBEDDING_DIM = 384
MOCK_REPLY = (
    "[mock] Acknowledged. (Running without a real AI provider - set "
    "AI_PROVIDER=openrouter with OPENROUTER_API_KEY for real answers.)"
)


class MockProvider(AIProvider):
    name = "mock"
    offline = True

    @property
    def available(self) -> bool:
        return True

    @property
    def configured(self) -> bool:
        return False  # deterministic offline provider needs no API key

    @property
    def embedding_dim(self):
        return MOCK_EMBEDDING_DIM

    @property
    def embedding_model_name(self):
        return "hash embeddings"

    def generate(self, system_prompt: str, messages: Sequence[dict]) -> str:
        last_role = messages[-1].get("content", "") if messages else ""
        # Keep the reply deterministic but echo the question count for tests.
        token = last_role[:40].replace("\n", " ")
        return f"{MOCK_REPLY} You said: {token}"

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [hash_embedding(text, MOCK_EMBEDDING_DIM) for text in texts]