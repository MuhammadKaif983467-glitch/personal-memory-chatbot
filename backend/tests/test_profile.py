"""Profile generation tests."""

from __future__ import annotations

import pytest

from app.database.models import Message
from app.database.repositories import ConversationRepository, MessageRepository, PersonRepository, PersonProfileRepository
from app.services.profile_service import ProfileService


def _person_with_messages(db, texts):
    people = PersonRepository(db)
    person = people.create("Ali")
    conversations = ConversationRepository(db)
    conversation = conversations.create(person.id, "t", "import")
    messages = MessageRepository(db)
    for text in texts:
        messages.add(
            Message(conversation_id=conversation.id, person_id=person.id, sender="Ali", content=text, msg_metadata={})
        )
    db.commit()
    return person


def test_profile_extracts_interests_preferences_facts(db):
    person = _person_with_messages(
        db,
        [
            "I like football",
            "I prefer tea over coffee",
            "I study at FAST University",
            "I am 22 years old",
            "tell me something random",
        ],
    )
    profile = ProfileService(db).build(person.id)
    db.commit()

    assert len(profile.interests) >= 1
    assert any("football" in f["value"] for f in profile.interests)
    assert any("tea" in f["value"] for f in profile.preferences)
    facts = profile.important_facts
    assert any("FAST" in f["value"] for f in facts)
    assert any("22" in f["value"] for f in facts)
    # every fact carries source + confidence
    for fact in [*profile.interests, *profile.preferences, *profile.important_facts]:
        assert fact["source_message_id"]
        assert fact["confidence"] > 0
        assert fact["created_at"]


def test_profile_topics_from_frequency(db):
    person = _person_with_messages(
        db,
        ["cricket match was great", "the cricket game", "who won cricket today"],
    )
    profile = ProfileService(db).build(person.id)
    topics = profile.topics
    assert any(t["value"] == "cricket" for t in topics)


def test_profile_upsert_is_idempotent(db):
    person = _person_with_messages(db, ["I like football"])
    repo = PersonProfileRepository(db)
    assert repo.get_for_person(person.id) is None
    ProfileService(db).build(person.id)
    profile = repo.get_for_person(person.id)
    assert profile is not None
    ProfileService(db).build(person.id)
    assert repo.get_for_person(person.id).id == profile.id