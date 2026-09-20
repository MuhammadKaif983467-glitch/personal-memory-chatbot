"""Profile service.

Extracts structured, low-risk facts from the person's messages using explicit
language patterns ("I like X", "I prefer X", "I study X", ...). Every fact is
stored WITH its source message, a confidence score and a creation time. Facts
are conservative: no uncertain AI guesses are ever promoted to confirmed fact.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.database.models import PersonProfile
from app.database.repositories import MessageRepository, PersonProfileRepository, PersonRepository
from app.schemas.common import Fact
from app.utils.text import meaningful_words

# (regex, fact-kind) where kind is interests | preferences | important_facts
_PATTERN_SETS = {
    "interests": [
        (re.compile(r"\bi (?:like|love) (?:to |playing |watching |reading |going to )?(.{2,40}?)(?:[.,!?]|\s*$)", re.I), 0.7),
    ],
    "preferences": [
        (re.compile(r"\bi prefer (?:to )?(.{2,40}?)(?:[.,!?]|\s*$)", re.I), 0.7),
        (re.compile(r"\bi (?:don't|dont|do not) like (.{2,40}?)(?:[.,!?]|\s*$)", re.I), 0.7),
    ],
    "important_facts": [
        (re.compile(r"\bi (?:am|em) (\d{1,3}) (?:years? old|years)", re.I), 0.85),
        (re.compile(r"\bmy name is ([A-Za-z][A-Za-z ]{1,30})[.,!?]?", re.I), 0.9),
        (re.compile(r"\bi (?:study|read) at ([A-Za-z ]{2,40})[.,!?]?", re.I), 0.75),
        (re.compile(r"\bi (?:work|am working) (?:at|in) (.{2,40}?)(?:[.,!?]|\s*$)", re.I), 0.75),
        (re.compile(r"\bi (?:live|am living) (?:in|at) (.{2,40}?)(?:[.,!?]|\s*$)", re.I), 0.7),
        (re.compile(r"\bi was born in (.{2,40}?)(?:[.,!?]|\s*$)", re.I), 0.7),
        (re.compile(r"\bmy birthday (?:is|falls on) (.{2,40}?)(?:[.,!?]|\s*$)", re.I), 0.8),
        (re.compile(r"\bmy (?:best friend|mother|father|brother|sister|wife|husband) (?:is called|is|works) (.{2,40}?)(?:[.,!?]|\s*$)", re.I), 0.7),
    ],
}

_MAX_FACT_VALUE_CHARS = 80


class ProfileService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.people = PersonRepository(session)
        self.profiles = PersonProfileRepository(session)
        self.messages_repo = MessageRepository(session)

    def get_or_none(self, person_id: int) -> Optional[PersonProfile]:
        return self.profiles.get_for_person(person_id)

    def build(self, person_id: int, messages: Optional[Sequence] = None) -> PersonProfile:
        """Recompute the profile from the person's cleaned text messages."""
        person = self.people.get(person_id)
        if person is None:
            raise ValueError("Unknown person")
        if messages is None:
            messages = self.messages_repo.all_for_person(person_id)

        texts = [m.content for m in messages if m.content and not m.is_duplicate and not m.is_spam]

        interests: list[Fact] = []
        preferences: list[Fact] = []
        important_facts: list[Fact] = []
        for message in messages:
            if not message.content or message.is_duplicate or message.is_spam:
                continue
            for name, patterns in _PATTERN_SETS.items():
                for regex, base_confidence in patterns:
                    match = regex.search(message.content)
                    if not match:
                        continue
                    value = _clean_fact_value(match.group(1))
                    if not value:
                        continue
                    fact = Fact(
                        value=value,
                        source_message_id=message.id,
                        source_text=message.content[:200],
                        confidence=base_confidence,
                        created_at=_now(),
                    )
                    target = {"interests": interests, "preferences": preferences, "important_facts": important_facts}[name]
                    if not any(f.value == value for f in target):
                        target.append(fact)

        topics = _topics(texts)
        habits = _habits(texts)

        return self.profiles.upsert(
            person_id,
            interests=[f.model_dump() for f in interests],
            preferences=[f.model_dump() for f in preferences],
            important_facts=[f.model_dump() for f in important_facts],
            communication_habits=habits,
            topics=topics,
        )


def _clean_fact_value(raw: str) -> str:
    value = re.sub(r"\s+", " ", raw).strip(" .,!?;")
    value = value.strip("'\"").strip()
    if not value:
        return ""
    if len(value) > _MAX_FACT_VALUE_CHARS:
        # keep leading fragment when we cannot trust the tail of a long sentence
        value = value[:_MAX_FACT_VALUE_CHARS].rsplit(" ", 1)[0]
    return value.strip()


def _topics(texts: Sequence[str], limit: int = 8) -> list[dict]:
    counter: dict[str, int] = {}
    for text in texts:
        for word in meaningful_words(text):
            counter[word] = counter.get(word, 0) + 1
    if not counter:
        return []
    top = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    max_count = max(counter.values())
    return [{"value": word, "confidence": round(count / max_count, 2)} for word, count in top]


def _habits(texts: Sequence[str]) -> list[str]:
    habits: list[str] = []
    avg_len = sum(len(t) for t in texts) / max(len(texts), 1)
    if avg_len <= 40:
        habits.append("prefers short messages")
    elif avg_len >= 120:
        habits.append("prefers long detailed messages")
    emoji_texts = sum(1 for t in texts if "\U0001F600" in t or "\U0001F601" in t or "\U0001F602" in t or "\U0001F604" in t)
    if texts and emoji_texts / len(texts) >= 0.1:
        habits.append("frequently uses emojis")
    return habits


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()