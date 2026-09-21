"""Repositories: thin data-access objects over SQLAlchemy sessions.

They keep the SQL out of the service layer so services stay readable and
unit-testable with a plain in-memory SQLite session.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.database.models import (
    Conversation,
    ConversationParticipant,
    EmbeddingRecord,
    Memory,
    MemoryVersion,
    Message,
    Person,
    PersonProfile,
    Project,
    VERSION_STATUS_ACTIVE,
    VERSION_STATUS_ARCHIVED,
    VERSION_STATUS_SUPERSEDED,
    VERSION_STATUS_UNCERTAIN,
    WritingStyle,
    utcnow,
)


def _version_status_for(legacy_status: str) -> str:
    """Map the memory table's status values onto versioning vocabulary."""
    return {
        "active": VERSION_STATUS_ACTIVE,
        "corrected": VERSION_STATUS_SUPERSEDED,
        "deleted": VERSION_STATUS_ARCHIVED,
        "uncertain": VERSION_STATUS_UNCERTAIN,
        "archived": VERSION_STATUS_ARCHIVED,
    }.get(str(legacy_status).casefold(), VERSION_STATUS_ACTIVE)


def _resolve_default_project_id(session: Session) -> Optional[int]:
    """Return the first project id (the backfilled default project)."""
    return session.scalar(select(Project.id).order_by(Project.id.asc()).limit(1))


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, project_id: int) -> Optional[Project]:
        return self.session.get(Project, project_id)

    def find_default(self) -> Optional[Project]:
        return self.session.scalar(select(Project).order_by(Project.id.asc()).limit(1))

    def list_all(self) -> Sequence[Project]:
        return self.session.scalars(select(Project).order_by(Project.created_at.asc(), Project.id.asc())).all()

    def create(self, name: str, user_id: str = "local") -> Project:
        project = Project(name=name, user_id=user_id)
        self.session.add(project)
        self.session.flush()
        return project

    def stats(self, project_id: int) -> dict:
        person_count = self.session.scalar(
            select(func.count(Person.id)).where(Person.project_id == project_id)
        ) or 0
        conversation_ids = select(Conversation.id).where(Conversation.project_id == project_id)
        message_count = self.session.scalar(
            select(func.count(Message.id)).where(Message.conversation_id.in_(conversation_ids))
        ) or 0
        memory_count = self.session.scalar(
            select(func.count(Memory.id)).where(Memory.project_id == project_id)
        ) or 0
        active_memory_count = self.session.scalar(
            select(func.count(Memory.id)).where(Memory.project_id == project_id, Memory.status == "active")
        ) or 0
        memory_ids = select(Memory.id).where(Memory.project_id == project_id)
        embedding_count = self.session.scalar(
            select(func.count(EmbeddingRecord.id)).where(EmbeddingRecord.memory_id.in_(memory_ids))
        ) or 0
        return {
            "persons": person_count,
            "conversations": self.session.scalar(
                select(func.count(Conversation.id)).where(Conversation.project_id == project_id)
            ) or 0,
            "messages": message_count,
            "memories": memory_count,
            "active_memories": active_memory_count,
            "embeddings": embedding_count,
        }


class PersonRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, person_id: int) -> Optional[Person]:
        return self.session.get(Person, person_id)

    def get_by_name(self, name: str) -> Optional[Person]:
        return self.session.scalar(select(Person).where(Person.name == name))

    def get_by_normalized_name(self, normalized: str) -> Optional[Person]:
        people = self.session.scalars(select(Person)).all()
        for person in people:
            names = [person.name, *(person.aliases or [])]
            if any(PersonRepository.normalize(n) == normalized for n in names):
                return person
        return None

    @staticmethod
    def normalize(name: str) -> str:
        return " ".join(str(name).strip().casefold().split())

    def add_alias(self, person: Person, alias: str) -> Person:
        alias = str(alias).strip()
        if alias and PersonRepository.normalize(alias) != PersonRepository.normalize(person.name):
            aliases = list(person.aliases or [])
            if alias not in aliases:
                aliases.append(alias)
                person.aliases = aliases
        return person

    def list_all(self, project_id: Optional[int] = None) -> Sequence[Person]:
        query = select(Person)
        if project_id is not None:
            query = query.where(Person.project_id == project_id)
        return self.session.scalars(query.order_by(Person.name)).all()

    def create(
        self, name: str, relationship: str = "unknown", project_id: Optional[int] = None, participant_role: str = ""
    ) -> Person:
        if project_id is None:
            project_id = _resolve_default_project_id(self.session)
        person = Person(
            name=name,
            relationship_type=relationship,
            project_id=project_id,
            participant_role=participant_role,
        )
        self.session.add(person)
        self.session.flush()
        return person

    def find_or_create(
        self, name: str, relationship: str = "unknown", participant_role: str = ""
    ) -> Person:
        normalized = self.normalize(name)
        existing = self.get_by_normalized_name(normalized)
        if existing:
            return existing
        return self.create(name, relationship, participant_role=participant_role)

    def find_by_role(self, project_id: int, role: str) -> Optional[Person]:
        return self.session.scalar(
            select(Person).where(Person.project_id == project_id, Person.participant_role == role)
        )

    def update(self, person: Person, **fields) -> Person:
        for key, value in fields.items():
            setattr(person, key, value)
        person.updated_at = utcnow()
        self.session.flush()
        return person

    def delete(self, person: Person) -> None:
        self.session.delete(person)


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, conversation_id: int) -> Optional[Conversation]:
        return self.session.get(Conversation, conversation_id)

    def create(self, person_id: int, title: str, source: str, project_id: Optional[int] = None) -> Conversation:
        if project_id is None:
            person = self.session.get(Person, person_id)
            project_id = (
                person.project_id
                if person is not None and person.project_id is not None
                else _resolve_default_project_id(self.session)
            )
        conversation = Conversation(person_id=person_id, title=title, source=source, project_id=project_id)
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def list_all(self, project_id: Optional[int] = None) -> Sequence[Conversation]:
        query = select(Conversation)
        if project_id is not None:
            query = query.where(Conversation.project_id == project_id)
        return self.session.scalars(query.order_by(Conversation.id.desc())).all()

    def find_by_source(self, source: str) -> Optional[Conversation]:
        """Locate a previously-imported conversation by its stable source key."""
        return self.session.scalar(
            select(Conversation).where(Conversation.source == source).order_by(Conversation.id.asc())
        )

    def find_duplicate(
        self, project_id: Optional[int], title: str, source: str, fingerprint: Optional[str] = None
    ) -> Optional[Conversation]:
        """Find an existing conversation that matches project + title + source.

        Used for deduplication: importing the same file twice should not create
        a second conversation.  For generic imports where no external ID exists,
        we match on normalised title + source within the same project.

        If a fingerprint is provided and there's an existing conversation with
        that fingerprint in the same project, that's a strong match (same
        conversation imported under a different name).
        """
        # 1. Try fingerprint match (strongest: same conversation, different filename).
        if fingerprint:
            fp_query = select(Conversation).where(
                Conversation.fingerprint == fingerprint,
            )
            if project_id is not None:
                fp_query = fp_query.where(Conversation.project_id == project_id)
            fp_match = self.session.scalar(fp_query.order_by(Conversation.id.asc()))
            if fp_match is not None:
                return fp_match

        # 2. Fall back to title + source match ONLY if the new import has no
        #    fingerprint (legacy import path) to avoid false-positive merges
        #    when two genuinely different conversations share a title.
        if not fingerprint:
            normalised = title.strip().lower() if title else ""
            query = select(Conversation).where(
                Conversation.source == source,
            )
            if project_id is not None:
                query = query.where(Conversation.project_id == project_id)
            if normalised:
                query = query.where(func.lower(Conversation.title) == normalised)
            # Only match conversations that also have no fingerprint.
            query = query.where(Conversation.fingerprint.is_(None))
            return self.session.scalar(query.order_by(Conversation.id.asc()))

        return None

    def message_count(self, conversation_id: int) -> int:
        return self.session.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        ) or 0

    def update_range(self, conversation_id: int, started_at, ended_at) -> None:
        self.session.execute(
            update(Conversation).where(Conversation.id == conversation_id).values(
                started_at=started_at, ended_at=ended_at
            )
        )

    def reassign(self, from_person_id: int, to_person_id: int) -> int:
        rows = self.session.execute(
            update(Conversation).where(Conversation.person_id == from_person_id).values(person_id=to_person_id)
        ).rowcount
        self.session.flush()
        return rows if rows else 0


class ConversationParticipantRepository:
    """Manages the authoritative participant records for conversations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_conversation(self, conversation_id: int) -> Sequence[ConversationParticipant]:
        return self.session.scalars(
            select(ConversationParticipant)
            .where(ConversationParticipant.conversation_id == conversation_id)
            .order_by(ConversationParticipant.id)
        ).all()

    def add(
        self,
        conversation_id: int,
        person_id: int,
        role: str = "OTHER",
        display_name_at_import: str = "",
    ) -> ConversationParticipant:
        cp = ConversationParticipant(
            conversation_id=conversation_id,
            person_id=person_id,
            role=role,
            display_name_at_import=display_name_at_import,
        )
        self.session.add(cp)
        self.session.flush()
        return cp

    def has_participants(self, conversation_id: int) -> bool:
        return self.session.scalar(
            select(func.count(ConversationParticipant.id))
            .where(ConversationParticipant.conversation_id == conversation_id)
        ) > 0

    def delete_for_conversation(self, conversation_id: int) -> int:
        """Delete all participant records for a conversation. Returns count deleted."""
        stmt = delete(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id
        )
        result = self.session.execute(stmt)
        return result.rowcount


class MessageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def bulk_create(self, rows: Sequence[Message]) -> int:
        self.session.add_all(rows)
        self.session.flush()
        return len(rows)

    def add(self, message: Message) -> Message:
        self.session.add(message)
        self.session.flush()
        return message

    def delete(self, message: Message) -> None:
        # Null out FK references from memories and memory_versions before deleting.
        self.session.execute(
            update(Memory).where(Memory.source_message_id == message.id).values(source_message_id=None)
        )
        self.session.execute(
            update(MemoryVersion).where(MemoryVersion.source_message_id == message.id).values(source_message_id=None)
        )
        self.session.delete(message)
        self.session.flush()

    def get(self, message_id: int) -> Optional[Message]:
        return self.session.get(Message, message_id)

    def list_by_conversation(self, conversation_id: int, limit: Optional[int] = None) -> Sequence[Message]:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc(), Message.id.asc())
        )
        if limit is not None:
            query = query.limit(limit)
        return self.session.scalars(query).all()

    def recent_by_conversation(self, conversation_id: int, limit: int) -> Sequence[Message]:
        rows = self.session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.desc(), Message.id.desc())
            .limit(limit)
        ).all()
        return list(reversed(rows))

    def list_all(
        self,
        *,
        person_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[Message]:
        query = select(Message)
        if person_id is not None:
            query = query.where(Message.person_id == person_id)
        if conversation_id is not None:
            query = query.where(Message.conversation_id == conversation_id)
        return self.session.scalars(query.order_by(Message.timestamp.desc(), Message.id.desc()).limit(limit).offset(offset)).all()

    def count(
        self,
        *,
        person_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> int:
        stmt = select(func.count(Message.id))
        if person_id is not None:
            stmt = stmt.where(Message.person_id == person_id)
        if conversation_id is not None:
            stmt = stmt.where(Message.conversation_id == conversation_id)
        return self.session.scalar(stmt) or 0

    def search(
        self,
        query_text: str,
        *,
        conversation_id: Optional[int] = None,
        person_id: Optional[int] = None,
        limit: int = 50,
    ) -> Sequence[Message]:
        stmt = select(Message).where(Message.content.ilike(f"%{query_text}%"))
        if conversation_id is not None:
            stmt = stmt.where(Message.conversation_id == conversation_id)
        if person_id is not None:
            stmt = stmt.where(Message.person_id == person_id)
        return self.session.scalars(stmt.order_by(Message.timestamp.desc()).limit(limit)).all()

    def all_for_person(self, person_id: int) -> Sequence[Message]:
        return self.session.scalars(
            select(Message).where(Message.person_id == person_id).order_by(Message.timestamp.asc(), Message.id.asc())
        ).all()

    def all_for_export(self) -> Sequence[Message]:
        return self.session.scalars(select(Message).order_by(Message.timestamp.asc(), Message.id.asc())).all()

    def count_for_person(self, person_id: int) -> int:
        return self.session.scalar(
            select(func.count(Message.id)).where(Message.person_id == person_id)
        ) or 0

    def reassign(self, from_person_id: int, to_person_id: int) -> int:
        rows = self.session.execute(
            update(Message).where(Message.person_id == from_person_id).values(person_id=to_person_id)
        ).rowcount
        self.session.flush()
        return rows if rows else 0

    # ------------------------------------------------------------------
    # FTS5 search (V3.3 Phase 1)
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_fts_query(query_text: str) -> str:
        """Sanitize user input for FTS5 MATCH queries.

        FTS5 interprets special characters (*, ", AND, OR, NOT, NEAR) as
        operators.  We strip them and use simple term matching to prevent
        unexpected behavior or injection.
        """
        import re as _re
        # Remove FTS5 special operators and syntax characters
        sanitized = _re.sub(r'["*(){}^~\\:;\[\]<>\-+=|]', ' ', query_text)
        # Remove FTS5 boolean/proximity keywords
        sanitized = _re.sub(r'\b(AND|OR|NOT|NEAR)\b', ' ', sanitized, flags=_re.IGNORECASE)
        # Collapse whitespace
        sanitized = _re.sub(r'\s+', ' ', sanitized).strip()
        return sanitized

    def fts_search(
        self,
        query_text: str,
        *,
        project_id: Optional[int] = None,
        person_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        limit: int = 50,
    ) -> Sequence[Message]:
        """Full-text search using FTS5 with fallback to LIKE.

        Project isolation is enforced via subquery on conversations table.
        """
        sanitized = self._sanitize_fts_query(query_text)
        if not sanitized:
            return []

        terms = sanitized.split()
        if not terms:
            return []

        # Limit term count and individual term length to prevent abuse
        terms = [t[:100] for t in terms[:8]]

        fts_expr = " OR ".join(f'"{t}"' for t in terms)

        try:
            # Build raw SQL with proper parameterization for FTS5 MATCH
            where_clauses = ["m.id IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH :expr)"]
            params: dict = {"expr": fts_expr, "limit": limit}

            if project_id is not None:
                where_clauses.append("m.conversation_id IN (SELECT id FROM conversations WHERE project_id = :project_id)")
                params["project_id"] = project_id
            if person_id is not None:
                where_clauses.append("m.person_id = :person_id")
                params["person_id"] = person_id
            if conversation_id is not None:
                where_clauses.append("m.conversation_id = :conversation_id")
                params["conversation_id"] = conversation_id

            where_sql = " AND ".join(where_clauses)
            sql = text(f"""
                SELECT m.id FROM messages m
                WHERE {where_sql}
                ORDER BY m.timestamp DESC NULLS LAST, m.id DESC
                LIMIT :limit
            """)
            result = self.session.execute(sql, params)
            ids = [row[0] for row in result.fetchall()]
            if not ids:
                return []
            return list(self.session.scalars(select(Message).where(Message.id.in_(ids))).all())
        except Exception:
            # Fallback to LIKE-based search if FTS5 is unavailable
            return self.search(
                sanitized,
                conversation_id=conversation_id,
                person_id=person_id,
                limit=limit,
            )

    def fts_rebuild(self) -> int:
        """Rebuild the FTS5 index from the messages table. Returns row count."""
        try:
            # For external-content FTS5, use the rebuild command.
            self.session.execute(text("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')"))
            self.session.flush()
            return self.session.scalar(text("SELECT count(*) FROM messages")) or 0
        except Exception:
            return 0


class PersonProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_person(self, person_id: int) -> Optional[PersonProfile]:
        return self.session.scalar(select(PersonProfile).where(PersonProfile.person_id == person_id))

    def upsert(self, person_id: int, *, interests=None, preferences=None, important_facts=None,
               communication_habits=None, topics=None) -> PersonProfile:
        profile = self.get_for_person(person_id)
        if profile is None:
            profile = PersonProfile(person_id=person_id)
            self.session.add(profile)
        if interests is not None:
            profile.interests = interests
        if preferences is not None:
            profile.preferences = preferences
        if important_facts is not None:
            profile.important_facts = important_facts
        if communication_habits is not None:
            profile.communication_habits = communication_habits
        if topics is not None:
            profile.topics = topics
        profile.generated_at = utcnow()
        self.session.flush()
        return profile


class WritingStyleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_person(self, person_id: int) -> Optional[WritingStyle]:
        return self.session.scalar(select(WritingStyle).where(WritingStyle.person_id == person_id))

    def upsert(self, person_id: int, **fields) -> WritingStyle:
        style = self.get_for_person(person_id)
        if style is None:
            style = WritingStyle(person_id=person_id)
            self.session.add(style)
        for key, value in fields.items():
            if value is not None:
                setattr(style, key, value)
        style.analyzed_at = utcnow()
        self.session.flush()
        return style


class MemoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, memory_id: int) -> Optional[Memory]:
        return self.session.get(Memory, memory_id)

    def create(
        self,
        *,
        person_id: int,
        content: str,
        memory_type: str,
        source_message_id: Optional[int] = None,
        importance: float = 0.5,
        confidence: float = 0.5,
        note: str = "",
        correction_of_id: Optional[int] = None,
        project_id: Optional[int] = None,
        actor: str = "system",
    ) -> Memory:
        if project_id is None:
            person = self.session.get(Person, person_id)
            project_id = (
                person.project_id
                if person is not None and person.project_id is not None
                else _resolve_default_project_id(self.session)
            )
        memory = Memory(
            person_id=person_id,
            project_id=project_id,
            content=content,
            memory_type=memory_type,
            source_message_id=source_message_id,
            importance=importance,
            confidence=confidence,
            note=note,
            correction_of_id=correction_of_id,
        )
        self.session.add(memory)
        self.session.flush()
        MemoryVersionRepository(self.session).append(
            memory,
            status=VERSION_STATUS_ACTIVE,
            actor=actor or "system",
            note=note or "created",
        )
        return memory

    def find_duplicate(self, person_id: int, content: str, memory_type: str) -> Optional[Memory]:
        return self.session.scalar(
            select(Memory).where(
                Memory.person_id == person_id,
                Memory.content == content,
                Memory.memory_type == memory_type,
                Memory.status == "active",
            )
        )

    def find_any(self, person_id: int, content: str, memory_type: str) -> Optional[Memory]:
        """Look up a memory by content/type ignoring status.

        Seeding must stay idempotent even after a memory has been superseded:
        a retired memory still counts as "already seeded", so it is never
        re-created as a fresh active record.
        """
        return self.session.scalar(
            select(Memory).where(
                Memory.person_id == person_id,
                Memory.content == content,
                Memory.memory_type == memory_type,
            )
        )

    def list_for_person(self, person_id: int, project_id: Optional[int] = None) -> Sequence[Memory]:
        """Every memory for a person, active or retired (correction history)."""
        query = select(Memory).where(Memory.person_id == person_id)
        if project_id is not None:
            query = query.where(Memory.project_id == project_id)
        return self.session.scalars(query.order_by(Memory.id.asc())).all()

    def list_active(self, person_id: Optional[int] = None, project_id: Optional[int] = None) -> Sequence[Memory]:
        query = select(Memory).where(Memory.status == "active")
        if person_id is not None:
            query = query.where(Memory.person_id == person_id)
        if project_id is not None:
            query = query.where(Memory.project_id == project_id)
        return self.session.scalars(query.order_by(Memory.updated_at.desc())).all()

    def list_all_include_non_active(self, project_id: Optional[int] = None) -> Sequence[Memory]:
        query = select(Memory)
        if project_id is not None:
            query = query.where(Memory.project_id == project_id)
        return self.session.scalars(query.order_by(Memory.updated_at.desc())).all()

    def search(
        self,
        *,
        query_text: str = "",
        person_id: Optional[int] = None,
        project_id: Optional[int] = None,
        memory_type: Optional[str] = None,
        min_confidence: float = 0.0,
        status: Optional[str] = "active",
        limit: int = 100,
    ) -> Sequence[Memory]:
        # ``status="active"`` (default) preserves prior behaviour; ``"all"`` or
        # ``None`` includes retired (corrected/superseded) memories for audit.
        q = select(Memory).where(Memory.confidence >= min_confidence)
        if status and status != "all":
            q = q.where(Memory.status == status)
        if person_id is not None:
            q = q.where(Memory.person_id == person_id)
        if project_id is not None:
            q = q.where(Memory.project_id == project_id)
        if memory_type:
            q = q.where(Memory.memory_type == memory_type)
        if query_text:
            q = q.where(Memory.content.ilike(f"%{query_text}%"))
        return self.session.scalars(q.order_by(Memory.updated_at.desc()).limit(limit)).all()

    def get_by_ids(self, memory_ids: Sequence[int]) -> Sequence[Memory]:
        if not memory_ids:
            return []
        return self.session.scalars(select(Memory).where(Memory.id.in_(memory_ids))).all()

    def list_by_source_messages(self, message_ids: Sequence[int]) -> Sequence[Memory]:
        if not message_ids:
            return []
        return self.session.scalars(
            select(Memory).where(Memory.source_message_id.in_(list(message_ids)))
        ).all()

    def is_correction_reference(self, memory_id: int) -> bool:
        """True when another memory supersedes this one (correction chain)."""
        return bool(
            self.session.scalar(
                select(func.count(Memory.id)).where(Memory.correction_of_id == memory_id)
            )
        )

    def set_status(self, memory_id: int, status: str, actor: str = "system") -> None:
        self.session.execute(update(Memory).where(Memory.id == memory_id).values(status=status, updated_at=utcnow()))
        self.session.flush()
        memory = self.session.get(Memory, memory_id)
        if memory is not None:
            MemoryVersionRepository(self.session).append(
                memory,
                status=_version_status_for(status),
                actor=actor or "system",
                note=f"status -> {status}",
            )
            self.session.flush()

    def reassign(self, from_person_id: int, to_person_id: int) -> int:
        rows = self.session.execute(
            update(Memory).where(Memory.person_id == from_person_id).values(person_id=to_person_id)
        ).rowcount
        self.session.flush()
        return rows if rows else 0

    def count_active(self, person_id: Optional[int] = None) -> int:
        q = select(func.count(Memory.id)).where(Memory.status == "active")
        if person_id is not None:
            q = q.where(Memory.person_id == person_id)
        return self.session.scalar(q) or 0


class EmbeddingRecordRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> Sequence[EmbeddingRecord]:
        return self.session.scalars(select(EmbeddingRecord)).all()

    def get_by_memory(self, memory_id: int) -> Optional[EmbeddingRecord]:
        return self.session.scalar(select(EmbeddingRecord).where(EmbeddingRecord.memory_id == memory_id))

    def upsert(self, *, memory_id: int, vector_id: str, model: str, checksum: str) -> EmbeddingRecord:
        record = self.get_by_memory(memory_id)
        if record is None:
            record = EmbeddingRecord(memory_id=memory_id, vector_id=vector_id, model=model, checksum=checksum)
            self.session.add(record)
        else:
            record.vector_id = vector_id
            record.model = model
            record.checksum = checksum
        self.session.flush()
        return record

    def delete_by_memory(self, memory_id: int) -> bool:
        record = self.get_by_memory(memory_id)
        if record is None:
            return False
        self.session.delete(record)
        self.session.flush()
        return True


class MemoryVersionRepository:
    """Append-only history of memory records.

    A version is a snapshot of the memory's content at one point in time.
    Revision 1 is recorded on creation; corrections/edits/status changes append
    later revisions so "what changed" can always be answered from history.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def append(
        self,
        memory: Memory,
        *,
        status: str,
        actor: str = "system",
        note: str = "",
        source_message_id: Optional[int] = None,
    ) -> MemoryVersion:
        revision = (
            self.session.scalar(
                select(func.count(MemoryVersion.id)).where(MemoryVersion.memory_id == memory.id)
            )
            or 0
        ) + 1
        version = MemoryVersion(
            memory_id=memory.id,
            revision=revision,
            status=status,
            content=memory.content or "",
            memory_type=memory.memory_type or "FACT",
            confidence=memory.confidence if memory.confidence is not None else 0.5,
            importance=memory.importance if memory.importance is not None else 0.5,
            source_message_id=source_message_id if source_message_id is not None else memory.source_message_id,
            note=note or "",
            actor=actor or "system",
        )
        self.session.add(version)
        self.session.flush()
        return version

    def list_for_memory(self, memory_id: int) -> Sequence[MemoryVersion]:
        return self.session.scalars(
            select(MemoryVersion)
            .where(MemoryVersion.memory_id == memory_id)
            .order_by(MemoryVersion.revision.asc(), MemoryVersion.id.asc())
        ).all()

    def latest_revision(self, memory_id: int) -> int:
        return (
            self.session.scalar(
                select(MemoryVersion.revision).where(MemoryVersion.memory_id == memory_id).order_by(
                    MemoryVersion.revision.desc(), MemoryVersion.id.desc()
                )
            )
            or 0
        )


class StatsRepository:
    """Simple counts for health inspection / observability."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def snapshot(self) -> dict:
        return {
            "persons": self.session.scalar(select(func.count(Person.id))) or 0,
            "conversations": self.session.scalar(select(func.count(Conversation.id))) or 0,
            "messages": self.session.scalar(select(func.count(Message.id))) or 0,
            "memories": self.session.scalar(select(func.count(Memory.id)).where(Memory.status == "active")) or 0,
            "embeddings": self.session.scalar(select(func.count(EmbeddingRecord.id))) or 0,
        }


class ConversationSummaryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_conversation(self, conversation_id: int) -> Optional["ConversationSummary"]:
        from app.database.models import ConversationSummary
        return self.session.scalar(
            select(ConversationSummary).where(
                ConversationSummary.conversation_id == conversation_id
            ).order_by(ConversationSummary.version.desc()).limit(1)
        )

    def upsert(self, conversation_id: int, *, summary: str, project_id: Optional[int] = None,
               message_start_id: Optional[int] = None, message_end_id: Optional[int] = None,
               message_count: int = 0, model: str = "") -> "ConversationSummary":
        from app.database.models import ConversationSummary
        existing = self.get_for_conversation(conversation_id)
        if existing:
            existing.summary = summary
            existing.message_start_id = message_start_id
            existing.message_end_id = message_end_id
            existing.message_count = message_count
            existing.model = model
            existing.version += 1
            return existing
        obj = ConversationSummary(
            conversation_id=conversation_id,
            project_id=project_id,
            summary=summary,
            message_start_id=message_start_id,
            message_end_id=message_end_id,
            message_count=message_count,
            model=model,
        )
        self.session.add(obj)
        self.session.flush()
        return obj

    def list_all(self, project_id: Optional[int] = None) -> list["ConversationSummary"]:
        from app.database.models import ConversationSummary
        q = select(ConversationSummary)
        if project_id is not None:
            q = q.where(ConversationSummary.project_id == project_id)
        return list(self.session.scalars(q).all())

    def delete_for_conversation(self, conversation_id: int) -> int:
        from app.database.models import ConversationSummary
        result = self.session.execute(
            delete(ConversationSummary).where(ConversationSummary.conversation_id == conversation_id)
        )
        return result.rowcount


class MemoryRelationshipRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, project_id: Optional[int], source_memory_id: int,
               target_memory_id: int, relationship_type: str,
               confidence: float = 0.5, note: str = "") -> "MemoryRelationship":
        from app.database.models import MemoryRelationship, VALID_RELATIONSHIP_TYPES
        if relationship_type not in VALID_RELATIONSHIP_TYPES:
            raise ValueError(f"Invalid relationship type: {relationship_type}")
        if source_memory_id == target_memory_id:
            raise ValueError("Cannot create self-relationship")

        # Verify both memories exist and are in the same project
        src_mem = self.session.get(Memory, source_memory_id)
        tgt_mem = self.session.get(Memory, target_memory_id)
        if src_mem is None:
            raise ValueError(f"Source memory {source_memory_id} not found")
        if tgt_mem is None:
            raise ValueError(f"Target memory {target_memory_id} not found")
        if src_mem.project_id != tgt_mem.project_id:
            raise ValueError("Cannot create cross-project relationship")
        if project_id is not None and src_mem.project_id != project_id:
            raise ValueError("Source memory does not belong to specified project")

        # Check for duplicate
        existing = self.session.scalar(
            select(MemoryRelationship).where(
                MemoryRelationship.source_memory_id == source_memory_id,
                MemoryRelationship.target_memory_id == target_memory_id,
                MemoryRelationship.relationship_type == relationship_type,
            )
        )
        if existing:
            return existing

        obj = MemoryRelationship(
            project_id=project_id or src_mem.project_id,
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relationship_type=relationship_type,
            confidence=confidence,
            note=note,
        )
        self.session.add(obj)
        self.session.flush()
        return obj

    def get_for_memory(self, memory_id: int) -> list["MemoryRelationship"]:
        from app.database.models import MemoryRelationship
        return list(self.session.scalars(
            select(MemoryRelationship).where(
                or_(
                    MemoryRelationship.source_memory_id == memory_id,
                    MemoryRelationship.target_memory_id == memory_id,
                )
            )
        ).all())

    def get_related(self, memory_id: int, *, relationship_type: Optional[str] = None) -> list["MemoryRelationship"]:
        """Get all relationships where this memory is the source."""
        from app.database.models import MemoryRelationship
        q = select(MemoryRelationship).where(MemoryRelationship.source_memory_id == memory_id)
        if relationship_type:
            q = q.where(MemoryRelationship.relationship_type == relationship_type)
        return list(self.session.scalars(q).all())

    def get_by_project(self, project_id: int) -> list["MemoryRelationship"]:
        from app.database.models import MemoryRelationship
        return list(self.session.scalars(
            select(MemoryRelationship).where(MemoryRelationship.project_id == project_id)
        ).all())

    def delete(self, relationship_id: int) -> bool:
        from app.database.models import MemoryRelationship
        obj = self.session.get(MemoryRelationship, relationship_id)
        if obj is None:
            return False
        self.session.delete(obj)
        return True

    def delete_for_project(self, project_id: int) -> int:
        from app.database.models import MemoryRelationship
        result = self.session.execute(
            delete(MemoryRelationship).where(MemoryRelationship.project_id == project_id)
        )
        return result.rowcount