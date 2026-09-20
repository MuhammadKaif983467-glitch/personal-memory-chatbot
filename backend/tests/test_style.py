"""Writing style analysis tests."""

from __future__ import annotations

from app.database.models import Message
from app.database.repositories import ConversationRepository, MessageRepository, PersonRepository
from app.services.style_service import StyleService


def _fixture_person(db):
    people = PersonRepository(db)
    person = people.create("Ali")
    conversation = ConversationRepository(db).create(person.id, "t", "import")
    messages_texts = [
        "Hello! how are you?",
        "I like cricket 🏏",
        "Great match today :)",
        "aap kaise ho? mujhe cricket pasand hai",
        "bye tc",
    ]
    rows = [
        Message(
            conversation_id=conversation.id, person_id=person.id, sender="Ali", content=t,
            message_type="text", msg_metadata={},
        )
        for t in messages_texts
    ]
    MessageRepository(db).bulk_create(rows)
    db.commit()
    return person


def test_style_analysis_fields(db):
    person = _fixture_person(db)
    style = StyleService(db).analyze(person.id)
    db.commit()

    assert style.average_message_length > 0
    assert style.average_words_per_message > 0
    assert isinstance(style.common_words, list)
    assert isinstance(style.language_mix, dict)
    assert "english" in style.language_mix
    assert style.tone in ("positive", "negative", "neutral")
    assert style.emoji_usage["frequency_per_message"] > 0  # cricket emoji present
    assert "common_emojis" in style.emoji_usage
    assert style.punctuation_style["counts"]["questions"] >= 1


def test_style_with_no_text_messages(db):
    people = PersonRepository(db)
    person = people.create("Ali")
    db.commit()
    style = StyleService(db).analyze(person.id)
    assert style.average_message_length == 0
    assert style.language_mix == {}