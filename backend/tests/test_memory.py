"""Memory extraction / correction / deletion tests."""

from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError
from app.database.models import Message
from app.database.repositories import ConversationRepository, EmbeddingRecordRepository, MemoryRepository, MessageRepository, PersonRepository
from app.database.models import Memory
from app.schemas.import_export import AnalyzeResult
from app.services.embedding_service import content_checksum
from app.services.memory_service import MemoryService, extract_candidates_from_message


class _FakeMessage:
    def __init__(self, message_id, content, sender="Ali", message_type="text", is_duplicate=False, is_spam=False, is_assistant=False):
        self.id = message_id
        self.content = content
        self.sender = sender
        self.message_type = message_type
        self.is_duplicate = is_duplicate
        self.is_spam = is_spam
        self.is_assistant = is_assistant


def test_extract_candidates_interest_and_fact():
    message = _FakeMessage(1, "I like playing football")
    candidates = extract_candidates_from_message("Ali", message)
    assert any(c.memory_type == "INTEREST" and "football" in c.content for c in candidates)

    facts = extract_candidates_from_message("Ali", _FakeMessage(2, "I am 22 years old"))
    assert any(c.memory_type == "FACT" and "22" in c.content for c in facts)


def test_extract_skips_assistant_and_spam():
    assert extract_candidates_from_message("Ali", _FakeMessage(1, "I like football", is_assistant=True)) == []
    assert extract_candidates_from_message("Ali", _FakeMessage(2, "I like football", is_spam=True)) == []


def test_extract_user_note_requires_person_name():
    ok = extract_candidates_from_message("Ali", _FakeMessage(1, "remember that Ali moved to Lahore"), is_user_message=True)
    assert len(ok) == 1 and "moved to Lahore" in ok[0].content

    noise = extract_candidates_from_message("Ali", _FakeMessage(2, "how are you doing"), is_user_message=True)
    assert noise == []


def _person_with_messages(db, texts):
    people = PersonRepository(db)
    person = people.create("Ali")
    conversation = ConversationRepository(db).create(person.id, "t", "import")
    messages = MessageRepository(db)
    rows = [
        Message(conversation_id=conversation.id, person_id=person.id, sender="Ali", content=t, msg_metadata={})
        for t in texts
    ]
    messages.bulk_create(rows)
    db.commit()
    return person


def test_memory_service_creates_and_dedupes(db, app):
    person = _person_with_messages(db, ["I prefer chai over coffee", "I prefer chai over coffee"])
    service = MemoryService(db)
    messages = MessageRepository(db).all_for_person(person.id)
    for message in messages:
        for candidate in extract_candidates_from_message(person.name, message):
            service.create_memory(candidate, person.id)
    db.commit()

    active = MemoryRepository(db).list_active(person.id)
    matches = [m for m in active if m.memory_type == "PREFERENCE" and "chai" in m.content]
    assert len(matches) == 1  # deduped
    assert matches[0].source_message_id is not None


def test_analyze_person_pipeline_creates_embeddings(db, app):
    person = _person_with_messages(
        db,
        ["I like playing football", "I study computer science at university", "what's up"],
    )
    embeddings = app.state.context.embeddings
    result = MemoryService(db).analyze_person(person.id, embeddings)

    assert isinstance(result, AnalyzeResult)
    assert result.memories_created >= 2
    assert result.memories_total > 0
    assert result.profile_generated
    assert result.style_generated
    assert app.state.context.vector_store.count() >= 1
    # embeddings recorded with checksums
    records = MemoryRepository(db).list_active(person.id)
    for memory in records:
        record = EmbeddingRecordRepository(db).get_by_memory(memory.id)
        assert record is not None
        assert record.checksum == content_checksum(memory.content)


def test_no_duplicate_embedding_for_unchanged_memory(db, app):
    person = _person_with_messages(db, ["I like playing football"])
    embeddings = app.state.context.embeddings
    MemoryService(db).analyze_person(person.id, embeddings)
    count_before = app.state.context.vector_store.count()
    # re-analysis must not duplicate embeddings
    MemoryService(db).analyze_person(person.id, embeddings)
    assert app.state.context.vector_store.count() == count_before


def test_correct_memory_retires_old_and_embeds_new(db, app):
    person = _person_with_messages(db, ["I prefer chai over coffee"])
    embeddings = app.state.context.embeddings
    service = MemoryService(db)
    service.analyze_person(person.id, embeddings)

    memory = next(
        m for m in MemoryRepository(db).list_active(person.id)
        if "chai" in m.content
    )
    replacement = service.correct(memory.id, "I actually prefer coffee", embeddings)

    assert memory.status == "corrected"
    active = MemoryRepository(db).list_active(person.id)
    assert replacement.id in [m.id for m in active]
    assert memory.id not in [m.id for m in active]
    # old vector is gone, new vector replaced it
    assert EmbeddingRecordRepository(db).get_by_memory(memory.id) is None
    assert EmbeddingRecordRepository(db).get_by_memory(replacement.id) is not None
    assert replacement.confidence >= 0.8


def test_delete_memory_removes_embedding(db, app):
    person = _person_with_messages(db, ["I prefer chai over coffee"])
    embeddings = app.state.context.embeddings
    service = MemoryService(db)
    service.analyze_person(person.id, embeddings)

    memory = next(m for m in MemoryRepository(db).list_active(person.id) if "chai" in m.content)
    service.delete(memory.id, embeddings)

    assert MemoryRepository(db).get(memory.id).status == "deleted"
    assert EmbeddingRecordRepository(db).get_by_memory(memory.id) is None


def test_operate_on_active_memory_only_raises(db, app):
    person = _person_with_messages(db, ["hello there"])
    embeddings = app.state.context.embeddings
    service = MemoryService(db)
    service.analyze_person(person.id, embeddings)
    order = MemoryRepository(db).list_active(person.id)
    assert order
    memory = order[0]
    service.delete(memory.id, embeddings)
    with pytest.raises(NotFoundError):
        service.delete(memory.id, embeddings)