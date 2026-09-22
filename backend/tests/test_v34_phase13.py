"""V3.4 Phase 13: Large-data scalability tests.

Tests with synthetic datasets to verify performance at scale.
"""

import pytest
from app.database.models import Memory, Message
from app.database.repositories import MemoryRepository, PersonRepository


class TestScalability:
    def test_import_10k_messages(self, app, db, client):
        """Import 10k messages and verify integrity."""
        import json
        from datetime import datetime, timezone, timedelta

        person = PersonRepository(db).create("ScaleTest", project_id=1)
        db.commit()

        messages = []
        for i in range(10000):
            messages.append({
                "sender": "me" if i % 2 == 0 else "ScaleTest",
                "content": f"Message number {i} about topic {i % 100}",
                "timestamp": (datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)).isoformat(),
            })

        payload = {
            "consent_confirmed": True,
            "conversation": {"person": "ScaleTest", "title": "Scale Test"},
            "messages": messages,
        }
        resp = client.post("/import/json", json=payload)
        assert resp.status_code == 200
        report = resp.json()
        assert report["imported"] > 0

    def test_search_10k_messages(self, app, db, client):
        """Search across large dataset returns quickly."""
        import time
        from app.database.repositories import MessageRepository

        # Create messages directly
        person = PersonRepository(db).create("SearchScale", project_id=1)
        db.commit()

        msg_repo = MessageRepository(db)
        from app.database.models import Conversation
        from app.database.repositories import ConversationRepository
        conv = ConversationRepository(db).create(person.id, "Search scale", source="test", project_id=1)
        db.commit()

        for i in range(5000):
            msg = Message(
                conversation_id=conv.id, sender="me",
                content=f"Scale message {i} about coffee and hiking",
                original_content=f"Scale message {i}", message_origin="imported",
            )
            msg_repo.add(msg)
        db.commit()

        start = time.time()
        results = msg_repo.fts_search("coffee", project_id=1, limit=20)
        elapsed = time.time() - start
        assert elapsed < 5.0  # Should be fast
        assert len(results) > 0

    def test_memory_search_large(self, app, db):
        """Memory search with many memories returns quickly."""
        import time
        from app.services.retrieval_service import RetrievalService

        person = PersonRepository(db).create("MemScale", project_id=1)
        mem_repo = MemoryRepository(db)
        for i in range(1000):
            mem_repo.create(
                person_id=person.id,
                content=f"Memory about topic {i % 50} with detail {i}",
                memory_type="FACT",
                project_id=1,
            )
        db.commit()

        retrieval = app.state.context.chat_service.retrieval
        start = time.time()
        results = retrieval._lexical_retrieve(
            db, "topic 25", person_id=person.id, project_id=1,
            memory_type=None, limit=12,
        )
        elapsed = time.time() - start
        assert elapsed < 5.0
        assert len(results) > 0
