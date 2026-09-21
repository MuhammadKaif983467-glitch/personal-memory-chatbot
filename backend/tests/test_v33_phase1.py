"""V3.3 Phase 1: Database hardening, FTS5, and foundation tests.

Covers:
- FK enforcement and cascade behavior
- FTS5 full-text search
- Composite indexes
- Migration idempotency and versioning
- Database integrity
- Large data performance
- Security (FTS injection, SQL injection, project isolation)
- Search API backward compatibility
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database.database import Database
from app.database.repositories import MessageRepository

SAMPLE_JSON = Path(__file__).parent.parent / "app" / "sample_data" / "sample_chat.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_sample(client: TestClient, *, person: str = "Ali", title: str = "Test Chat") -> dict:
    payload = json.loads(SAMPLE_JSON.read_text(encoding="utf-8"))
    payload["consent_confirmed"] = True
    payload["conversation"]["person"] = person
    payload["conversation"]["title"] = title
    resp = client.post("/import/json", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _bulk_import(client: TestClient, count: int, *, person: str = "BulkUser") -> dict:
    messages = [
        {"sender": person, "content": f"Bulk message {i} about topic {i % 10}", "timestamp": f"2026-01-01T00:{i:02d}:00"}
        for i in range(count)
    ]
    payload = {
        "consent_confirmed": True,
        "conversation": {"person": person, "title": f"Bulk Import {count}"},
        "messages": messages,
    }
    resp = client.post("/import/json", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Phase 13: FK Enforcement & Cascade
# ---------------------------------------------------------------------------

class TestFKEnforcement:
    def test_foreign_keys_enforced(self, app):
        """SQLite FK enforcement must be enabled on every connection."""
        with app.state.context.db.engine.connect() as conn:
            fk = conn.execute(sqlalchemy_text("PRAGMA foreign_keys")).fetchone()[0]
        assert fk == 1, "PRAGMA foreign_keys must be ON"

    def test_invalid_person_reference_rejected(self, app):
        """Inserting a message with a non-existent person_id must fail."""
        from sqlalchemy import text
        with app.state.context.db.engine.connect() as conn:
            try:
                conn.execute(text(
                    "INSERT INTO messages (conversation_id, person_id, sender, content, "
                    "original_content, message_type, message_origin) "
                    "VALUES (99999, 99999, 'test', 'should fail', '', 'text', 'imported')"
                ))
                conn.commit()
                assert False, "Expected FK violation"
            except Exception as e:
                assert "FOREIGN KEY" in str(e) or "constraint" in str(e).lower()
                conn.rollback()

    def test_cascade_delete_conversation_removes_messages(self, client, imported_alias):
        """Deleting a conversation should remove its messages via cascade."""
        conv_id = imported_alias["conversation_id"]
        msgs_before = client.get(f"/messages?conversation_id={conv_id}&limit=1000").json()["total"]
        assert msgs_before > 0

        resp = client.delete(f"/conversations/{conv_id}")
        assert resp.status_code == 200

        msgs_after = client.get(f"/messages?conversation_id={conv_id}&limit=1000").json()["total"]
        assert msgs_after == 0

    def test_project_isolation_intact(self, client):
        """Project A data must not leak into Project B searches."""
        proj_a = client.post("/projects", json={"name": "Iso A"}).json()
        proj_b = client.post("/projects", json={"name": "Iso B"}).json()

        client.post("/import/json", json={
            "consent_confirmed": True, "project_id": proj_a["id"],
            "conversation": {"person": "Alice", "title": "A Chat"},
            "messages": [{"sender": "Alice", "content": "secret alpha data", "timestamp": "2026-01-01T00:00:00"}],
        })
        client.post("/import/json", json={
            "consent_confirmed": True, "project_id": proj_b["id"],
            "conversation": {"person": "Bob", "title": "B Chat"},
            "messages": [{"sender": "Bob", "content": "private beta data", "timestamp": "2026-01-01T00:00:00"}],
        })

        search_a = client.post("/search", json={"query": "alpha", "project_id": proj_a["id"]}).json()
        assert any("alpha" in h["content"].lower() for h in search_a["messages"])
        assert not any("beta" in h["content"].lower() for h in search_a["messages"])

        search_b = client.post("/search", json={"query": "beta", "project_id": proj_b["id"]}).json()
        assert any("beta" in h["content"].lower() for h in search_b["messages"])
        assert not any("alpha" in h["content"].lower() for h in search_b["messages"])


# ---------------------------------------------------------------------------
# Phase 13: FTS5
# ---------------------------------------------------------------------------

class TestFTS5:
    def test_fts5_table_exists(self, app):
        """messages_fts virtual table must exist after init."""
        with app.state.context.db.engine.connect() as conn:
            exists = conn.execute(
                sqlalchemy_text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages_fts'")
            ).fetchone()
        assert exists is not None

    def test_fts5_triggers_exist(self, app):
        """FTS sync triggers must exist."""
        expected = {"messages_fts_ai", "messages_fts_ad", "messages_fts_au"}
        with app.state.context.db.engine.connect() as conn:
            triggers = {
                r[0] for r in conn.execute(
                    sqlalchemy_text("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'messages_fts_%'")
                ).fetchall()
            }
        assert expected.issubset(triggers)

    def test_fts5_insert_sync(self, client, imported_alias):
        """New messages must appear in FTS5 index."""
        person_id = imported_alias["person_id"]
        resp = client.post("/chat", json={
            "message": "Hello I like pizza very much",
            "person_id": person_id,
        })
        assert resp.status_code == 200
        # Search for the new message content
        search = client.post("/search", json={"query": "pizza"}).json()
        assert len(search["messages"]) > 0

    def test_fts5_search_finds_content(self, client, imported_alias):
        """FTS5 must find imported message content."""
        search = client.post("/search", json={"query": "love"}).json()
        assert search["total"] > 0

    def test_fts5_project_scoped(self, client):
        """FTS5 search must be project-scoped."""
        proj_a = client.post("/projects", json={"name": "FTS A"}).json()
        proj_b = client.post("/projects", json={"name": "FTS B"}).json()

        client.post("/import/json", json={
            "consent_confirmed": True, "project_id": proj_a["id"],
            "conversation": {"person": "P", "title": "C1"},
            "messages": [{"sender": "P", "content": "quantum computing is fascinating", "timestamp": "2026-01-01T00:00:00"}],
        })
        client.post("/import/json", json={
            "consent_confirmed": True, "project_id": proj_b["id"],
            "conversation": {"person": "Q", "title": "C2"},
            "messages": [{"sender": "Q", "content": "traditional cooking recipes", "timestamp": "2026-01-01T00:00:00"}],
        })

        results_a = client.post("/search", json={"query": "quantum", "project_id": proj_a["id"]}).json()
        assert any("quantum" in h["content"].lower() for h in results_a["messages"])
        assert not any("cooking" in h["content"].lower() for h in results_a["messages"])

    def test_fts5_rebuild(self, app):
        """FTS5 rebuild must succeed without errors."""
        with app.state.context.db.session_ctx() as session:
            repo = MessageRepository(session)
            count = repo.fts_rebuild()
            assert count >= 0


# ---------------------------------------------------------------------------
# Phase 13: Migration
# ---------------------------------------------------------------------------

class TestMigration:
    def test_migration_versioning_table_exists(self, app):
        """schema_migrations table must exist."""
        with app.state.context.db.engine.connect() as conn:
            exists = conn.execute(
                sqlalchemy_text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'")
            ).fetchone()
        assert exists is not None

    def test_migration_recorded(self, app):
        """V3.3.001 migration must be recorded."""
        with app.state.context.db.engine.connect() as conn:
            row = conn.execute(
                sqlalchemy_text("SELECT version FROM schema_migrations WHERE version = 'V3.3.001'")
            ).fetchone()
        assert row is not None

    def test_migration_idempotent(self, app):
        """Running init() twice must not corrupt the database."""
        db = app.state.context.db
        db.init()
        db.init()
        with db.engine.connect() as conn:
            integrity = conn.execute(sqlalchemy_text("PRAGMA integrity_check")).fetchone()[0]
        assert integrity == "ok"

    def test_restart_safe(self, app):
        """Application restart must not duplicate schema objects."""
        db = app.state.context.db
        db.init()
        with db.engine.connect() as conn:
            fts_tables = conn.execute(
                sqlalchemy_text("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='messages_fts'")
            ).fetchone()[0]
        assert fts_tables == 1


# ---------------------------------------------------------------------------
# Phase 13: Database Integrity
# ---------------------------------------------------------------------------

class TestDatabaseIntegrity:
    def test_integrity_check(self, app):
        """PRAGMA integrity_check must report ok."""
        with app.state.context.db.engine.connect() as conn:
            result = conn.execute(sqlalchemy_text("PRAGMA integrity_check")).fetchone()[0]
        assert result == "ok"

    def test_no_orphaned_source_message_ids(self, app):
        """All memories.source_message_id must reference existing messages."""
        with app.state.context.db.session_ctx() as session:
            from sqlalchemy import text
            orphans = session.execute(text(
                "SELECT count(*) FROM memories WHERE source_message_id IS NOT NULL "
                "AND source_message_id NOT IN (SELECT id FROM messages)"
            )).scalar()
        assert orphans == 0

    def test_no_orphaned_mv_source_message_ids(self, app):
        """All memory_versions.source_message_id must reference existing messages."""
        with app.state.context.db.session_ctx() as session:
            from sqlalchemy import text
            orphans = session.execute(text(
                "SELECT count(*) FROM memory_versions WHERE source_message_id IS NOT NULL "
                "AND source_message_id NOT IN (SELECT id FROM messages)"
            )).scalar()
        assert orphans == 0


# ---------------------------------------------------------------------------
# Phase 14: Large Data
# ---------------------------------------------------------------------------

class TestLargeData:
    def test_10k_messages_import(self, client):
        """Importing 10,000 messages must succeed."""
        start = time.time()
        result = _bulk_import(client, 10000)
        elapsed = time.time() - start
        assert result["messages_created"] == 10000
        assert elapsed < 60, f"10k import took {elapsed:.1f}s (>60s)"

    def test_fts_search_10k(self, client):
        """FTS search on 10k messages must be fast."""
        _bulk_import(client, 10000, person="SearchUser")
        start = time.time()
        resp = client.post("/search", json={"query": "topic 5"}).json()
        elapsed = time.time() - start
        assert resp["total"] > 0
        assert elapsed < 5, f"FTS search on 10k took {elapsed:.1f}s (>5s)"

    def test_conversation_messages_10k(self, client):
        """Loading 10k messages for a conversation must work."""
        result = _bulk_import(client, 10000, person="ConvUser")
        conv_id = result["conversation_id"]
        start = time.time()
        resp = client.get(f"/messages?conversation_id={conv_id}&limit=200").json()
        elapsed = time.time() - start
        assert resp["total"] == 10000
        assert elapsed < 5, f"Loading 200 msgs from 10k took {elapsed:.1f}s (>5s)"


# ---------------------------------------------------------------------------
# Phase 17: Security
# ---------------------------------------------------------------------------

class TestSecurity:
    def test_fts_injection_wildcard(self, client, imported_alias):
        """FTS wildcard injection must not crash."""
        resp = client.post("/search", json={"query": "*"})
        assert resp.status_code == 200

    def test_fts_injection_operators(self, client, imported_alias):
        """FTS operator injection (AND/OR/NOT/NEAR) must not crash."""
        for q in ['" OR 1=1 --', "AND OR NOT", "NEAR(foo bar)", "^~\\"]:
            resp = client.post("/search", json={"query": q})
            assert resp.status_code == 200, f"Failed for query: {q}"

    def test_sql_injection_in_search(self, client, imported_alias):
        """SQL injection in search must not succeed."""
        resp = client.post("/search", json={"query": "' OR 1=1 --"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 0

    def test_project_isolation_search(self, client):
        """Malicious search queries cannot cross project boundaries."""
        proj_a = client.post("/projects", json={"name": "Sec A"}).json()
        proj_b = client.post("/projects", json={"name": "Sec B"}).json()
        client.post("/import/json", json={
            "consent_confirmed": True, "project_id": proj_a["id"],
            "conversation": {"person": "A", "title": "A"},
            "messages": [{"sender": "A", "content": "classified alpha secret", "timestamp": "2026-01-01T00:00:00"}],
        })
        client.post("/import/json", json={
            "consent_confirmed": True, "project_id": proj_b["id"],
            "conversation": {"person": "B", "title": "B"},
            "messages": [{"sender": "B", "content": "public beta info", "timestamp": "2026-01-01T00:00:00"}],
        })
        # Search in B must not find A's data even with injection
        results = client.post("/search", json={"query": "alpha secret", "project_id": proj_b["id"]}).json()
        assert not any("classified" in h.get("content", "").lower() for h in results["messages"])

    def test_oversized_query(self, client, imported_alias):
        """Extremely long search strings must be handled safely (422 or 200)."""
        long_query = "a" * 10000
        resp = client.post("/search", json={"query": long_query})
        assert resp.status_code in (200, 422), f"Unexpected status: {resp.status_code}"

    def test_unicode_search(self, client, imported_alias):
        """Unicode content (Urdu, emoji) must be searchable."""
        client.post("/import/json", json={
            "consent_confirmed": True,
            "conversation": {"person": "Uni", "title": "Unicode"},
            "messages": [
                {"sender": "Uni", "content": "مرحبا بالعالم", "timestamp": "2026-01-01T00:00:00"},
                {"sender": "Uni", "content": "Hello world 🌍", "timestamp": "2026-01-01T00:01:00"},
            ],
        })
        resp = client.post("/search", json={"query": "مرحبا"})
        assert resp.status_code == 200

    def test_roman_urdu_search(self, client, imported_alias):
        """Roman Urdu content must be searchable."""
        client.post("/import/json", json={
            "consent_confirmed": True,
            "conversation": {"person": "RU", "title": "Roman Urdu"},
            "messages": [
                {"sender": "RU", "content": "kya haal hai dost", "timestamp": "2026-01-01T00:00:00"},
            ],
        })
        resp = client.post("/search", json={"query": "dost"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Phase 15: Search API Compatibility
# ---------------------------------------------------------------------------

class TestSearchCompatibility:
    def test_search_response_schema(self, client, imported_alias):
        """POST /search must return the same response schema."""
        resp = client.post("/search", json={"query": "test"})
        assert resp.status_code == 200
        body = resp.json()
        assert "query" in body
        assert "messages" in body
        assert "memories" in body
        assert "conversations" in body
        assert "total" in body

    def test_search_with_all_filters(self, client, imported_alias):
        """POST /search with all filters must work."""
        person_id = imported_alias["person_id"]
        conv_id = imported_alias["conversation_id"]
        resp = client.post("/search", json={
            "query": "test",
            "person_id": person_id,
            "conversation_id": conv_id,
        })
        assert resp.status_code == 200

    def test_empty_search(self, client, imported_alias):
        """POST /search with empty query must not crash."""
        resp = client.post("/search", json={"query": ""})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Composite Index Verification
# ---------------------------------------------------------------------------

class TestCompositeIndexes:
    def test_expected_indexes_exist(self, app):
        """All V3.3 composite indexes must exist."""
        expected = [
            "ix_messages_conversation_ts",
            "ix_messages_person_ts",
            "ix_messages_sender_conv",
            "ix_messages_origin",
            "ix_memories_proj_person_type",
            "ix_memories_status_updated",
            "ix_memories_source_msg",
            "ix_conversations_proj_started",
            "ix_cp_conv_person",
            "ix_mv_memory_revision",
        ]
        with app.state.context.db.engine.connect() as conn:
            indexes = {
                r[0] for r in conn.execute(
                    sqlalchemy_text("SELECT name FROM sqlite_master WHERE type='index'")
                ).fetchall()
            }
        for idx in expected:
            assert idx in indexes, f"Missing index: {idx}"


# ---------------------------------------------------------------------------
# Dead code: verify cleanup doesn't break anything
# ---------------------------------------------------------------------------

class TestBackendImports:
    def test_import_database_module(self):
        """app.database must be importable."""
        from app.database import database, models, repositories
        assert database is not None
        assert models is not None
        assert repositories is not None

    def test_import_services(self):
        """All services must be importable."""
        from app.services.analytics_service import AnalyticsService
        from app.services.chat_service import ChatService
        from app.services.memory_service import MemoryService
        assert AnalyticsService is not None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

from sqlalchemy import text as sqlalchemy_text
