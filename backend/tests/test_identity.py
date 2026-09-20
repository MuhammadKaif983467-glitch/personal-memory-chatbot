"""Identity service tests."""

from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError
from app.database.models import Message
from app.database.repositories import ConversationRepository, MessageRepository, PersonRepository
from app.services.identity_service import IdentityService


def test_find_create_and_match_exact(db):
    identity = IdentityService(db)
    person = identity.find_or_create_person("Ali", relationship="friend")
    assert person.id is not None
    db.commit()

    assert identity.find_person("Ali").id == person.id
    assert identity.find_person("  ali  ").id == person.id  # normalized match, no new person
    assert PersonRepository(db).list_all().__len__() == 1


def test_new_person_created_for_different_name(db):
    identity = IdentityService(db)
    p1 = identity.find_or_create_person("Ali")
    p2 = identity.find_or_create_person("Hassan")
    db.commit()
    assert p1.id != p2.id


def test_merge_people_moves_messages_and_conversations(db):
    identity = IdentityService(db)
    people = PersonRepository(db)
    conversations = ConversationRepository(db)
    messages = MessageRepository(db)

    source = people.create("Ali")
    target = people.create("AliOfficial")
    conv = conversations.create(source.id, "test", "import")
    messages.add(Message(conversation_id=conv.id, person_id=source.id, sender="Ali", content="hi", msg_metadata={}))
    db.commit()

    result = identity.merge_people(source.id, target.id)

    assert result.moved_messages == 1
    assert conversations.get(conv.id).person_id == target.id
    assert people.get(source.id) is None  # source deleted after merge
    assert identity.find_person("Ali").id == target.id


def test_merge_requires_two_different_persons(db):
    identity = IdentityService(db)
    person = identity.find_or_create_person("Ali")
    with pytest.raises(NotFoundError):
        identity.merge_people(person.id, person.id)


def test_merge_unknown_person_raises(db):
    identity = IdentityService(db)
    person = identity.find_or_create_person("Ali")
    with pytest.raises(NotFoundError):
        identity.merge_people(9999, person.id)