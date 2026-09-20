"""Context builder tests."""

from __future__ import annotations

from app.database.models import Memory
from app.schemas.memory import ConfidenceOut
from app.services.context_service import build_context
from app.services.retrieval_service import RetrievedMemory


class _FakePerson:
    name = "Ali"


class _FakeProfile:
    interests = [{"value": "football", "confidence": 0.7}]
    preferences = [{"value": "tea", "confidence": 0.7}]
    important_facts = [{"value": "studies CS", "confidence": 0.9}]
    communication_habits = ["prefers short messages"]
    topics = [{"value": "cricket", "confidence": 0.8}]


class _FakeStyle:
    average_message_length = 24.0
    average_words_per_message = 4.0
    language_mix = {"english": 0.8, "roman-urdu": 0.2}
    tone = "positive"
    emoji_usage = {"common_emojis": ["😂"]}
    common_words = ["cricket", "match"]


class _FakeMessage:
    def __init__(self, sender, content):
        self.sender = sender
        self.content = content
        self.is_assistant = sender == "assistant"


def _retrieved(content, similarity=0.8, conf=0.9):
    memory = Memory(person_id=1, content=content, memory_type="FACT", confidence=conf, importance=0.7)
    return RetrievedMemory(memory=memory, similarity=similarity, score=0.9)


def test_context_contains_all_sections():
    result = build_context(
        question="What does Ali like?",
        recent_messages=[_FakeMessage("me", "hi"), _FakeMessage("assistant", "hello!")],
        retrieved=[_retrieved("Ali likes cricket")],
        person=_FakePerson(),
        profile=_FakeProfile(),
        style=_FakeStyle(),
        confidence=ConfidenceOut(level="HIGH", score=0.85),
        budget_chars=9000,
    )
    for label in [
        "[CURRENT QUESTION]",
        "[RECENT CONVERSATION]",
        "[RELEVANT MEMORIES]",
        "[IMPORTANT FACTS]",
        "[PERSON PROFILE]",
        "[WRITING STYLE]",
        "[RETRIEVAL METADATA]",
    ]:
        assert label in result.text
    assert "cricket" in result.text


def test_context_respects_budget():
    many = [_retrieved("A very long memory snippet about cricket " * 20, 0.8) for _ in range(20)]
    result = build_context(
        question="What does Ali like?",
        recent_messages=[_FakeMessage("me", "hello there") for _ in range(50)],
        retrieved=many,
        person=_FakePerson(),
        profile=_FakeProfile(),
        style=_FakeStyle(),
        confidence=ConfidenceOut(level="MEDIUM", score=0.6),
        budget_chars=800,
    )
    assert result.used_chars <= 900  # small tolerance for the truncation marker
    assert result.budget == 800


def test_empty_context_is_still_well_formed():
    result = build_context(
        question="Where are we?",
        recent_messages=[],
        retrieved=[],
        person=_FakePerson(),
        profile=None,
        style=None,
        confidence=ConfidenceOut(level="LOW", score=0.1),
        budget_chars=3000,
    )
    assert "[RELEVANT MEMORIES]" in result.text
    assert "(no relevant memories retrieved)" in result.text