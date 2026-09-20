"""Offline heuristic provider.

Lets the whole pipeline run without any external API: embeddings are
deterministic hash vectors and replies are grounded in the retrieved memories
from the context text. It never invents facts - when no memory matches it
explicitly says so and asks for clarification.
"""

from __future__ import annotations

import re
from typing import Sequence

from app.ai.base import AIProvider
from app.utils.embeddings import hash_embedding
from app.utils.similarity import best_relevance

DIM = 384

_SECTION_BOUNDARY = r"(?=\n\[[A-Z][A-Z /]+\]|\Z)"


class LocalProvider(AIProvider):
    name = "local"
    offline = True

    @property
    def available(self) -> bool:
        return True

    @property
    def configured(self) -> bool:
        return False  # offline heuristic provider needs no API key

    @property
    def embedding_dim(self):
        return DIM

    @property
    def embedding_model_name(self):
        return "hash embeddings"

    def generate(self, system_prompt: str, messages: Sequence[dict]) -> str:
        question = messages[-1].get("content", "") if messages else ""
        confidence = _extract_confidence(system_prompt)

        candidates = _extract_candidates(system_prompt)
        if not candidates:
            return (
                "I don't have a memory that matches that yet. "
                "Could you tell me more so I can remember it? "
                f"(confidence: {confidence})"
            )

        scored: list[tuple[float, str]] = []
        for text, base in candidates:
            relevance = 0.7 * best_relevance(question, text) + 0.3 * base
            scored.append((relevance, text))
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_text = scored[0]
        if len(best_text) > 240:
            best_text = best_text[:237].rstrip() + "..."

        if best_score < 0.12:
            return (
                "I don't have a memory that matches that yet. "
                "Could you tell me more so I can remember it? "
                f"(confidence: {confidence})"
            )

        if best_score < 0.30 or confidence == "LOW":
            return (
                f"I'm not very sure, but I recall: {best_text} - can you confirm? "
                f"(confidence: {confidence})"
            )
        return f"Based on what I remember: {best_text} (confidence: {confidence})"

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [hash_embedding(text, DIM) for text in texts]


def _extract_candidates(context: str) -> list[tuple[str, float]]:
    """Return (text, base_relevance) pairs from memories and stored facts."""
    candidates: list[tuple[str, float]] = []

    for line in _section(context, "RELEVANT MEMORIES").splitlines():
        parsed = _parse_memory_line(line)
        if parsed is not None:
            text, score = parsed
            candidates.append((text, score))

    for line in _section(context, "IMPORTANT FACTS").splitlines():
        text = line.strip().lstrip("-").strip()
        if text:
            candidates.append((text, 0.6))

    return candidates


def _section(context: str, header: str) -> str:
    pattern = rf"\[{re.escape(header)}\]\s*(.*?){_SECTION_BOUNDARY}"
    match = re.search(pattern, context, re.S)
    return match.group(1) if match else ""


_MEMORY_LINE = re.compile(
    r"^\s*\d+\.\s*\[([0-9.]+)\]\s*\([^)]*\)\s*(.*?)(?:\s+—\s+recalled from.*)?$"
)


def _parse_memory_line(line: str) -> tuple[str, float] | None:
    match = _MEMORY_LINE.match(line)
    if not match:
        return None
    try:
        similarity = float(match.group(1))
    except ValueError:
        similarity = 0.5
    text = match.group(2).strip()
    if not text:
        return None
    return text, max(0.0, min(1.0, similarity))


def _extract_confidence(context: str) -> str:
    match = re.search(r"Confidence signal:\s*(\w+)", context)
    if match:
        return match.group(1).upper()
    match = re.search(r"confidence\s+([A-Z]+)\s*\(", context)
    if match:
        return match.group(1).upper()
    return "LOW"
