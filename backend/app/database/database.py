"""Database engine and session management.

The engine/session factory is created per application (dependency injection),
so tests can spin up isolated databases without touching a module-level engine.

V3.3 Phase 1 additions:
- SQLite foreign-key enforcement via connection event listener
- Versioned migration framework (schema_migrations table)
- FTS5 virtual table for message full-text search
- Composite indexes on verified hot query paths
- Orphaned FK reference cleanup
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, func, select, text, update
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Database:
    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.url = url
        connect_args = (
            {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
        )
        self.engine = create_engine(url, connect_args=connect_args, echo=echo, future=True)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False, future=True
        )

        # Enable foreign-key enforcement for every SQLite connection.
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _enable_fk(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.close()

    def init(self) -> None:
        """Create tables and apply additive migrations (idempotent).

        Import models first so they register on Base.
        """
        # noqa: F401 - importing registers the models on Base.metadata
        from app.database import models  # noqa: F401
        Base.metadata.create_all(self.engine)
        self._ensure_schema_migrations_table()
        self.migrate()
        self._apply_migration(
            "V3.3.001",
            "Clean orphaned FK references before FK enforcement",
            self._v3_3_001_clean_orphaned_fks,
        )
        self._ensure_fts5()
        self._ensure_indexes()
        self._ensure_fts_sync()

    # ------------------------------------------------------------------
    # Schema migrations versioning
    # ------------------------------------------------------------------

    def _ensure_schema_migrations_table(self) -> None:
        """Create the schema_migrations tracking table if it does not exist."""
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
                    description TEXT NOT NULL DEFAULT ''
                )
            """))
            conn.commit()

    def _migration_applied(self, version: str) -> bool:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM schema_migrations WHERE version = :v"), {"v": version}
            ).fetchone()
            return row is not None

    def _apply_migration(self, version: str, description: str, fn) -> None:
        """Apply a migration function if not yet recorded.  Idempotent."""
        if self._migration_applied(version):
            return
        fn()
        with self.engine.connect() as conn:
            conn.execute(
                text("INSERT INTO schema_migrations (version, description) VALUES (:v, :d)"),
                {"v": version, "d": description},
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Legacy migration (V3.2 and earlier – kept for backward compat)
    # ------------------------------------------------------------------

    def migrate(self) -> None:
        """Additive, non-destructive schema/data migration for existing SQLite
        databases created before the multi-project model existed.
        """
        if not self.url.startswith("sqlite"):
            return
        from app.database import models  # noqa: F401
        from app.database.models import (
            Conversation,
            ConversationParticipant,
            DEFAULT_PROJECT_NAME,
            Memory,
            Message,
            Person,
            Project,
        )

        def _ensure_column(table: str, column_sql: str, name: str) -> None:
            with self.engine.connect() as conn:
                columns = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_sql}"))
                    conn.commit()

        _ensure_column("persons", "project_id INTEGER REFERENCES projects(id)", "project_id")
        _ensure_column("conversations", "project_id INTEGER REFERENCES projects(id)", "project_id")
        _ensure_column("memories", "project_id INTEGER REFERENCES projects(id)", "project_id")
        _ensure_column("persons", "participant_role VARCHAR(20) DEFAULT ''", "participant_role")
        _ensure_column("messages", "message_origin VARCHAR(30) DEFAULT 'imported'", "message_origin")

        # Ensure conversation_participants table exists
        with self.engine.connect() as conn:
            tables = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))]
            if "conversation_participants" not in tables:
                conn.execute(text("""
                    CREATE TABLE conversation_participants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                        person_id INTEGER NOT NULL REFERENCES persons.id,
                        role VARCHAR(20) DEFAULT 'OTHER',
                        display_name_at_import VARCHAR(200) DEFAULT ''
                    )
                """))
                conn.execute(text("CREATE INDEX ix_conversation_participants_conversation_id ON conversation_participants(conversation_id)"))
                conn.execute(text("CREATE INDEX ix_conversation_participants_person_id ON conversation_participants(person_id)"))
                conn.commit()

        with self.session_ctx() as session:
            if session.scalar(select(Project.id).limit(1)) is None:
                session.add(Project(name=DEFAULT_PROJECT_NAME, user_id="local"))
                session.flush()
            default_id = session.scalar(select(Project.id).order_by(Project.id.asc()).limit(1))

            session.execute(update(Person).where(Person.project_id.is_(None)).values(project_id=default_id))
            session.execute(
                update(Conversation).where(Conversation.project_id.is_(None)).values(project_id=default_id)
            )
            memory_project = (
                select(Person.project_id).where(Person.id == Memory.person_id).correlate(Memory).scalar_subquery()
            )
            session.execute(
                update(Memory).where(Memory.project_id.is_(None)).values(project_id=memory_project)
            )

            existing_participants = set(
                session.execute(
                    select(ConversationParticipant.conversation_id).distinct()
                ).scalars().all()
            )
            legacy_conversations = session.execute(
                select(Conversation.id, Conversation.person_id).where(
                    Conversation.id.notin_(existing_participants)
                )
            ).all()
            for conv_id, person_id in legacy_conversations:
                if person_id is not None:
                    person = session.get(Person, person_id)
                    display_name = person.name if person else ""
                    session.add(ConversationParticipant(
                        conversation_id=conv_id,
                        person_id=person_id,
                        role="ME",
                        display_name_at_import=display_name,
                    ))
                    senders = session.execute(
                        select(Message.sender).where(
                            Message.conversation_id == conv_id
                        ).distinct()
                    ).scalars().all()
                    me_name_lower = display_name.strip().lower() if display_name else ""
                    for sender_name in senders:
                        if sender_name and sender_name.strip().lower() != me_name_lower:
                            from app.database.repositories import PersonRepository
                            person_repo = PersonRepository(session)
                            other_person = person_repo.find_or_create(
                                sender_name, relationship="unknown"
                            )
                            if other_person.project_id is None and person is not None:
                                other_person.project_id = person.project_id
                            session.add(ConversationParticipant(
                                conversation_id=conv_id,
                                person_id=other_person.id,
                                role="OTHER",
                                display_name_at_import=sender_name,
                            ))
                            session.execute(
                                update(Message).where(
                                    Message.conversation_id == conv_id,
                                    Message.sender == sender_name,
                                ).values(person_id=other_person.id)
                            )
            for conv_id in existing_participants:
                existing_roles = {
                    cp.role for cp in session.execute(
                        select(ConversationParticipant).where(
                            ConversationParticipant.conversation_id == conv_id
                        )
                    ).scalars().all()
                }
                if "OTHER" not in existing_roles:
                    conv = session.get(Conversation, conv_id)
                    if conv is None:
                        continue
                    me_participant = session.execute(
                        select(ConversationParticipant).where(
                            ConversationParticipant.conversation_id == conv_id,
                            ConversationParticipant.role == "ME",
                        )
                    ).scalar_one_or_none()
                    if me_participant is None:
                        continue
                    me_person = session.get(Person, me_participant.person_id)
                    me_name = (me_person.name or "").strip().lower() if me_person else ""
                    senders = session.execute(
                        select(Message.sender).where(
                            Message.conversation_id == conv_id
                        ).distinct()
                    ).scalars().all()
                    for sender_name in senders:
                        if sender_name and sender_name.strip().lower() != me_name:
                            from app.database.repositories import PersonRepository
                            person_repo = PersonRepository(session)
                            other_person = person_repo.find_or_create(
                                sender_name, relationship="unknown"
                            )
                            if other_person.project_id is None and me_person is not None:
                                other_person.project_id = me_person.project_id
                            session.add(ConversationParticipant(
                                conversation_id=conv_id,
                                person_id=other_person.id,
                                role="OTHER",
                                display_name_at_import=sender_name,
                            ))
                            session.execute(
                                update(Message).where(
                                    Message.conversation_id == conv_id,
                                    Message.sender == sender_name,
                                ).values(person_id=other_person.id)
                            )
            if legacy_conversations or existing_participants:
                session.flush()

            cols = {row[1] for row in session.execute(text("PRAGMA table_info(conversations)")).fetchall()}
            if "fingerprint" not in cols:
                session.execute(text("ALTER TABLE conversations ADD COLUMN fingerprint VARCHAR(64)"))
                from app.utils.fingerprint import compute_conversation_fingerprint
                convs = session.execute(select(Conversation.id, Conversation.project_id, Conversation.source)).all()
                for conv_id, conv_proj, conv_source in convs:
                    senders = [s for s in session.execute(
                        select(Message.sender).where(Message.conversation_id == conv_id).distinct()
                    ).scalars().all() if s]
                    msg_count = session.scalar(
                        select(func.count(Message.id)).where(Message.conversation_id == conv_id)
                    ) or 0
                    fp = compute_conversation_fingerprint(
                        project_id=conv_proj,
                        source=conv_source or "",
                        participant_names=senders,
                        message_count=msg_count,
                    )
                    session.execute(
                        update(Conversation).where(Conversation.id == conv_id).values(fingerprint=fp)
                    )
                session.flush()

    # ------------------------------------------------------------------
    # V3.3 Phase 1 migrations
    # ------------------------------------------------------------------

    def _v3_3_001_clean_orphaned_fks(self) -> None:
        """Clean orphaned source_message_id references in memories and
        memory_versions before FK enforcement is turned on.

        These references point to messages that were deleted or never existed.
        We SET NULL to preserve the memory record while removing the broken FK.
        """
        with self.engine.connect() as conn:
            # Orphaned memories.source_message_id
            result = conn.execute(text("""
                UPDATE memories
                SET source_message_id = NULL
                WHERE source_message_id IS NOT NULL
                  AND source_message_id NOT IN (SELECT id FROM messages)
            """))
            mem_orphans = result.rowcount

            # Orphaned memory_versions.source_message_id
            result = conn.execute(text("""
                UPDATE memory_versions
                SET source_message_id = NULL
                WHERE source_message_id IS NOT NULL
                  AND source_message_id NOT IN (SELECT id FROM messages)
            """))
            ver_orphans = result.rowcount

            conn.commit()

    def _ensure_fts5(self) -> None:
        """Create the FTS5 virtual table for message full-text search.

        Uses an external-content FTS5 table backed by the messages table.
        This avoids data duplication while enabling efficient full-text search.
        """
        with self.engine.connect() as conn:
            # Check if FTS5 table already exists
            exists = conn.execute(text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages_fts'"
            )).fetchone()
            if exists:
                return

            # Create external-content FTS5 table
            conn.execute(text("""
                CREATE VIRTUAL TABLE messages_fts USING fts5(
                    content,
                    sender,
                    conversation_id UNINDEXED,
                    person_id UNINDEXED,
                    timestamp UNINDEXED,
                    message_id UNINDEXED,
                    content=messages,
                    content_rowid=id,
                    tokenize='unicode61 remove_diacritics 2'
                )
            """))

            # Populate with existing messages
            conn.execute(text("""
                INSERT INTO messages_fts (rowid, content, sender, conversation_id, person_id, timestamp, message_id)
                SELECT id, content, sender, conversation_id, person_id, timestamp, id FROM messages
            """))
            conn.commit()

    def _ensure_fts_sync(self) -> None:
        """Create triggers to keep FTS5 synchronized with the messages table.

        Handles INSERT, UPDATE, and DELETE operations on messages.
        """
        with self.engine.connect() as conn:
            # Check if triggers already exist
            existing = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'messages_fts_%'"
            )).fetchall()
            existing_names = {row[0] for row in existing}

            if "messages_fts_ai" not in existing_names:
                conn.execute(text("""
                    CREATE TRIGGER messages_fts_ai AFTER INSERT ON messages BEGIN
                        INSERT INTO messages_fts (rowid, content, sender, conversation_id, person_id, timestamp, message_id)
                        VALUES (new.id, new.content, new.sender, new.conversation_id, new.person_id, new.timestamp, new.id);
                    END
                """))

            if "messages_fts_ad" not in existing_names:
                conn.execute(text("""
                    CREATE TRIGGER messages_fts_ad AFTER DELETE ON messages BEGIN
                        INSERT INTO messages_fts (messages_fts, rowid, content, sender, conversation_id, person_id, timestamp, message_id)
                        VALUES ('delete', old.id, old.content, old.sender, old.conversation_id, old.person_id, old.timestamp, old.id);
                    END
                """))

            if "messages_fts_au" not in existing_names:
                conn.execute(text("""
                    CREATE TRIGGER messages_fts_au AFTER UPDATE ON messages BEGIN
                        INSERT INTO messages_fts (messages_fts, rowid, content, sender, conversation_id, person_id, timestamp, message_id)
                        VALUES ('delete', old.id, old.content, old.sender, old.conversation_id, old.person_id, old.timestamp, old.id);
                        INSERT INTO messages_fts (rowid, content, sender, conversation_id, person_id, timestamp, message_id)
                        VALUES (new.id, new.content, new.sender, new.conversation_id, new.person_id, new.timestamp, new.id);
                    END
                """))
            conn.commit()

    def _ensure_indexes(self) -> None:
        """Create composite indexes on verified hot query paths.

        Each index is justified by an actual query pattern in repositories.py
        or services/. No speculative indexes are created.
        """
        indexes = [
            # messages: conversation lookup sorted by timestamp (list_by_conversation)
            ("ix_messages_conversation_ts", "messages", "(conversation_id, timestamp, id)"),
            # messages: project-scoped person lookup (list_all with person_id)
            ("ix_messages_person_ts", "messages", "(person_id, timestamp DESC, id DESC)"),
            # messages: sender-based queries (search, participant detection)
            ("ix_messages_sender_conv", "messages", "(sender, conversation_id)"),
            # messages: message_origin filtering (chat_service, import)
            ("ix_messages_origin", "messages", "(message_origin)"),
            # memories: project+person+type active lookup (search, list_active)
            ("ix_memories_proj_person_type", "memories", "(project_id, person_id, memory_type, status)"),
            # memories: status+updated_at (list_active ordering)
            ("ix_memories_status_updated", "memories", "(status, updated_at DESC)"),
            # memories: source_message_id (list_by_source_messages)
            ("ix_memories_source_msg", "memories", "(source_message_id)"),
            # conversations: project+started_at (list_all ordering)
            ("ix_conversations_proj_started", "conversations", "(project_id, started_at)"),
            # conversation_participants: unique constraint (person per conversation)
            ("ix_cp_conv_person", "conversation_participants", "(conversation_id, person_id)"),
            # memory_versions: memory_id+revision (version history)
            ("ix_mv_memory_revision", "memory_versions", "(memory_id, revision)"),
        ]

        with self.engine.connect() as conn:
            existing_indexes = {
                row[0] for row in conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )).fetchall()
            }
            for idx_name, table, cols in indexes:
                if idx_name not in existing_indexes:
                    conn.execute(text(f"CREATE INDEX {idx_name} ON {table}{cols}"))
            conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def session(self) -> Session:
        return self.session_factory()

    @contextmanager
    def session_ctx(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
