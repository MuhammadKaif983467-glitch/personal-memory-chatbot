"""Writing style analysis.

Scans a person's cleaned messages and computes communication habits:
message lengths, emoji/sticker usage, common words and phrases, punctuation,
language mix (English / Urdu / Roman Urdu), tone, common greetings/endings.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.database.models import WritingStyle
from app.database.repositories import MessageRepository, PersonRepository, WritingStyleRepository
from app.utils.text import (
    common_emojis,
    count_emoji,
    detect_language,
    detect_tone,
    tokenize_words,
    top_phrases,
    top_tokens,
)


class StyleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.people = PersonRepository(session)
        self.styles = WritingStyleRepository(session)
        self.messages_repo = MessageRepository(session)

    def get_or_none(self, person_id: int) -> Optional[WritingStyle]:
        return self.styles.get_for_person(person_id)

    def analyze(self, person_id: int, messages: Optional[Sequence] = None) -> WritingStyle:
        person = self.people.get(person_id)
        if person is None:
            raise ValueError("Unknown person")
        if messages is None:
            messages = self.messages_repo.all_for_person(person_id)

        text_messages = [
            m for m in messages
            if m.content and not m.is_duplicate and not m.is_spam and m.message_type == "text"
        ]
        texts = [m.content for m in text_messages]

        lengths = [len(t) for t in texts]
        word_counts = [len(tokenize_words(t)) for t in texts]

        languages: dict[str, int] = {}
        for m in text_messages:
            lang, _ = detect_language(m.content)
            languages[lang] = languages.get(lang, 0) + 1

        punctuation = _punctuation_style(texts)
        greetings = _greeting_words(texts)
        endings = _ending_words(texts)

        emoji_total = sum(count_emoji(t) for t in texts)
        emoji_freq = round(emoji_total / max(len(texts), 1), 4)

        stickers = sum(1 for m in messages if m.message_type == "sticker")

        return self.styles.upsert(
            person_id,
            common_words=top_tokens(texts, 12),
            common_phrases=top_phrases(texts, 6),
            emoji_usage={
                "common_emojis": common_emojis(texts, 8),
                "frequency_per_message": emoji_freq,
                "total_emojis": emoji_total,
            },
            sticker_usage={"count": stickers},
            average_message_length=round(sum(lengths) / max(len(lengths), 1), 2),
            average_words_per_message=round(sum(word_counts) / max(len(word_counts), 1), 2),
            language_mix={k: round(v / max(len(text_messages), 1), 3) for k, v in languages.items()},
            tone=detect_tone(texts),
            punctuation_style=punctuation,
            common_greetings=greetings,
            common_endings=endings,
        )


def _punctuation_style(texts: Sequence[str]) -> dict:
    totals = {"exclamations": 0, "questions": 0, "periods": 0, "commas": 0}
    for t in texts:
        totals["exclamations"] += t.count("!")
        totals["questions"] += t.count("?")
        totals["periods"] += t.count(".")
        totals["commas"] += t.count(",")
    trailing = sum(1 for t in texts if t and t.rstrip()[-1:] in "!?")
    return {
        "counts": totals,
        "trailing_punctuation_ratio": round(trailing / max(len(texts), 1), 3),
    }


_GREETINGS = {"hi", "hello", "hey", "salam", "assalam", "salamualikum", "hye", "hola", "yo", "morning"}
_ENDINGS = {"bye", "byee", "goodnight", "tc", "bs", "allahafiz", "ok", "okay", "later", "n8"}


def _greeting_words(texts: Sequence[str]) -> list[str]:
    seen: dict[str, int] = {}
    for t in texts:
        first = t.casefold().strip().rstrip("!.,")
        words = tokenize_words(first)
        if words and words[0] in _GREETINGS:
            seen[words[0]] = seen.get(words[0], 0) + 1
    ranked = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)
    return [w for w, _ in ranked[:5]]


def _ending_words(texts: Sequence[str]) -> list[str]:
    seen: dict[str, int] = {}
    for t in texts:
        words = tokenize_words(t)
        if not words:
            continue
        last = words[-1]
        if last in _ENDINGS:
            seen[last] = seen.get(last, 0) + 1
    ranked = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)
    return [w for w, _ in ranked[:5]]