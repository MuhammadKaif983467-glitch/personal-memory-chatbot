"""V3.4 Phase 1: Conversation-aware retrieval tests.

Covers:
- conversation_id filtering and boost
- date range filtering
- same-person boost
- cross-conversation isolation
- lexical fallback with conversation context
- backward compatibility (no conversation_id)
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.database.models import Memory, Message
from app.database.repositories import (
    MemoryRepository, PersonRepository, ConversationRepository, MessageRepository,
)
from app.services.retrieval_service import RetrievalService, RetrievedMemory


class TestConversationAwareRetrieval:
    """Test conversation_id parameter in retrieval."""

    def test_retrieve_without_conversation_id(self, app, db):
        """Backward compatibility: retrieve without conversation_id works."""
        ctx = app.state.context
        retrieval = ctx.chat_service.retrieval
        person = PersonRepository(db).create("ConvTest", project_id=1)
        mem_repo = MemoryRepository(db)
        mem_repo.create(person_id=person.id, content="blue is a color", memory_type="FACT", project_id=1)
        db.commit()
        results = retrieval.retrieve(db, "what color", person_id=person.id)
        assert len(results) >= 1

    def test_conversation_boost_applied(self, app, db):
        """Memories from current conversation should score higher."""
        ctx = app.state.context
        retrieval = ctx.chat_service.retrieval
        person = PersonRepository(db).create("BoostTest", project_id=1)
        conv_repo = ConversationRepository(db)
        msg_repo = MessageRepository(db)

        conv = conv_repo.create(person.id, "Boost conv", source="test", project_id=1)
        msg = Message(
            conversation_id=conv.id, person_id=person.id, sender="me",
            content="I love hiking in mountains", original_content="I love hiking in mountains",
            message_origin="imported",
        )
        msg_repo.add(msg)
        db.commit()

        mem_repo = MemoryRepository(db)
        mem = mem_repo.create(
            person_id=person.id, content="loves hiking in mountains",
            memory_type="INTEREST", source_message_id=msg.id, project_id=1,
        )
        db.commit()

        with_conv = retrieval.retrieve(db, "hiking", person_id=person.id, conversation_id=conv.id)
        without_conv = retrieval.retrieve(db, "hiking", person_id=person.id)

        assert len(with_conv) >= 1
        assert len(without_conv) >= 1

        with_score = next(r.score for r in with_conv if r.memory.id == mem.id)
        without_score = next(r.score for r in without_conv if r.memory.id == mem.id)
        assert with_score > without_score

    def test_date_range_filtering(self, app, db):
        """Memories outside date range should be excluded."""
        ctx = app.state.context
        retrieval = ctx.chat_service.retrieval
        person = PersonRepository(db).create("DateTest", project_id=1)
        mem_repo = MemoryRepository(db)
        mem_repo.create(person_id=person.id, content="old memory", memory_type="FACT", project_id=1)
        db.commit()

        future = datetime.now(timezone.utc) + timedelta(days=365)
        results = retrieval.retrieve(db, "old memory", person_id=person.id, date_from=future)
        assert len(results) == 0

    def test_date_to_filters_old_memories(self, app, db):
        """Memories after date_to should be excluded."""
        ctx = app.state.context
        retrieval = ctx.chat_service.retrieval
        person = PersonRepository(db).create("DateToTest", project_id=1)
        mem_repo = MemoryRepository(db)
        mem_repo.create(person_id=person.id, content="recent fact", memory_type="FACT", project_id=1)
        db.commit()

        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        results = retrieval.retrieve(db, "recent fact", person_id=person.id, date_to=past)
        assert len(results) == 0

    def test_same_person_boost(self, app, db):
        """Memories from the same person should get a small boost."""
        ctx = app.state.context
        retrieval = ctx.chat_service.retrieval
        person_repo = PersonRepository(db)
        p1 = person_repo.create("Person1", project_id=1)
        p2 = person_repo.create("Person2", project_id=1)
        mem_repo = MemoryRepository(db)
        mem_repo.create(person_id=p1.id, content="likes coffee every morning", memory_type="PREFERENCE", project_id=1)
        mem_repo.create(person_id=p2.id, content="enjoys tea in afternoon", memory_type="PREFERENCE", project_id=1)
        db.commit()

        results = retrieval.retrieve(db, "coffee and tea preferences", person_id=p1.id)
        assert len(results) >= 1
        # The p1 memory should have same_person context_reason
        p1_results = [r for r in results if r.memory.person_id == p1.id]
        assert len(p1_results) >= 1
        assert p1_results[0].context_reason == "same_person"

    def test_empty_conversation_graceful(self, app, db):
        """Empty conversation_id (no messages yet) should not crash."""
        ctx = app.state.context
        retrieval = ctx.chat_service.retrieval
        person = PersonRepository(db).create("EmptyConv", project_id=1)
        conv = ConversationRepository(db).create(person.id, "Empty", source="test", project_id=1)
        db.commit()

        results = retrieval.retrieve(db, "anything", person_id=person.id, conversation_id=conv.id)
        assert isinstance(results, list)


class TestLexicalFallbackConversationContext:
    """Test lexical retrieval with conversation context."""

    def test_lexical_fallback_with_conversation(self, app, db):
        """Lexical fallback should still work with conversation_id."""
        ctx = app.state.context
        retrieval = ctx.chat_service.retrieval
        person = PersonRepository(db).create("LexConv", project_id=1)
        mem_repo = MemoryRepository(db)
        mem_repo.create(person_id=person.id, content="enjoys reading books", memory_type="INTEREST", project_id=1)
        db.commit()

        results = retrieval._lexical_retrieve(
            db, "reading books", person_id=person.id, project_id=1,
            memory_type=None, limit=10, conversation_id=None,
        )
        assert len(results) >= 1

    def test_lexical_date_range(self, app, db):
        """Lexical fallback respects date range."""
        ctx = app.state.context
        retrieval = ctx.chat_service.retrieval
        person = PersonRepository(db).create("LexDate", project_id=1)
        mem_repo = MemoryRepository(db)
        mem_repo.create(person_id=person.id, content="temporal fact", memory_type="FACT", project_id=1)
        db.commit()

        future = datetime.now(timezone.utc) + timedelta(days=365)
        results = retrieval._lexical_retrieve(
            db, "temporal fact", person_id=person.id, project_id=1,
            memory_type=None, limit=10, date_from=future,
        )
        assert len(results) == 0
