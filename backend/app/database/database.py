"""Database engine and session management.

The engine/session factory is created per application (dependency injection),
so tests can spin up isolated databases without touching a module-level engine.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, func, select, text, update
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

    def init(self) -> None:
        """Create tables and apply additive migrations (idempotent).

        Import models first so they register on Base.
        """
        # noqa: F401 - importing registers the models on Base.metadata
        from app.database import models  # noqa: F401
        Base.metadata.create_all(self.engine)
        self.migrate()

    def migrate(self) -> None:
        """Additive, non-destructive schema/data migration for existing SQLite
        databases created before the multi-project model existed.

        * adds a ``project_id`` column to persons / conversations / memories,
        * adds the ``participant_role`` column to persons (ME / OTHER setup),
        * adds ``message_origin`` to messages (imported / live_user / generated),
        * creates the ``conversation_participants`` table if missing,
        * backfills legacy conversations with participant records,
        * ensures a default ("Demo / Regression") project exists,
        * backfills every untagged row into that project so no data is ever
          stranded outside an isolation boundary.
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

            # Backfill legacy conversations: create ConversationParticipant records
            # for conversations that have no participants yet, and add missing
            # OTHER participants for conversations that only have ME.
            existing_participants = set(
                session.execute(
                    select(ConversationParticipant.conversation_id).distinct()
                ).scalars().all()
            )
            # Conversations with zero participants need full backfill.
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
            # Also add missing OTHER participants for conversations that have ME
            # but are missing OTHER (partial backfill from earlier migration).
            for conv_id in existing_participants:
                existing_roles = {
                    cp.role for cp in session.execute(
                        select(ConversationParticipant).where(
                            ConversationParticipant.conversation_id == conv_id
                        )
                    ).scalars().all()
                }
                if "OTHER" not in existing_roles:
                    # This conversation has ME but no OTHER - detect from messages.
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
                            # Update message person_id for OTHER sender.
                            session.execute(
                                update(Message).where(
                                    Message.conversation_id == conv_id,
                                    Message.sender == sender_name,
                                ).values(person_id=other_person.id)
                            )
            if legacy_conversations or existing_participants:
                session.flush()

            # Add fingerprint column if missing (idempotent).
            cols = {row[1] for row in session.execute(text("PRAGMA table_info(conversations)")).fetchall()}
            if "fingerprint" not in cols:
                session.execute(text("ALTER TABLE conversations ADD COLUMN fingerprint VARCHAR(64)"))
                # Backfill fingerprints for existing conversations.
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