"""SQLAlchemy ORM models for the relational database.

JSON columns store structured analysis results (profiles, styles, memory
metadata). Imported data is always preserved: every message keeps
``original_content`` next to its cleaned form.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_PROJECT_NAME = "Demo / Regression"


class Project(Base):
    """A workspace isolating a set of people, conversations and memories.

    Existing data is backfilled into the first ("default") project so the
    regression dataset is preserved without any schema rewrite.
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    user_id: Mapped[str] = mapped_column(String(100), default="local", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    # Role within the (two-person) project: "ME" / "OTHER". Empty for legacy
    # participants created before roles existed; never treated as a default ME.
    participant_role: Mapped[str] = mapped_column(String(20), default="")
    # Alternate names collected when two records are merged; lookups by any of
    # these still resolve to this person.
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    relationship_type: Mapped[str] = mapped_column(String(100), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    # Cascade: deleting a person removes their profile and style, but
    # conversations and messages are preserved (person_id SET NULL via FK).
    project: Mapped["Project"] = relationship()
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="person")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(300), default="Untitled")
    source: Mapped[str] = mapped_column(String(100), default="chat")
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Cascade: deleting a conversation removes its messages and participants.
    project: Mapped["Project"] = relationship()
    person: Mapped["Person"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    participants: Mapped[list["ConversationParticipant"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class ConversationParticipant(Base):
    """Authoritative participant model for two-person conversations.

    Replaces the implicit ``conversation.person_id`` as the primary way to
    discover who is in a conversation. Legacy conversations are backfilled by
    the migration so that existing data keeps working.
    """

    __tablename__ = "conversation_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="OTHER")  # ME | OTHER
    display_name_at_import: Mapped[str] = mapped_column(String(200), default="")

    conversation: Mapped["Conversation"] = relationship(back_populates="participants")
    person: Mapped["Person"] = relationship()


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True)
    sender: Mapped[str] = mapped_column(String(200), index=True)
    content: Mapped[str] = mapped_column(Text, default="")          # cleaned content
    original_content: Mapped[str] = mapped_column(Text, default="")  # raw imported content
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    message_type: Mapped[str] = mapped_column(String(50), default="text")
    message_origin: Mapped[str] = mapped_column(String(30), default="imported")  # imported | live_user | generated
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(30), default="unknown")
    msg_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Cascade: deleting a message removes its embedding records and versions.
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    @property
    def is_assistant(self) -> bool:
        return self.sender.lower() == "assistant"


class PersonProfile(Base):
    __tablename__ = "person_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Cascade: deleting a person removes their profile.
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), unique=True, index=True)
    interests: Mapped[list] = mapped_column(JSON, default=list)          # list of Fact dicts
    preferences: Mapped[list] = mapped_column(JSON, default=list)        # list of Fact dicts
    important_facts: Mapped[list] = mapped_column(JSON, default=list)    # list of Fact dicts
    communication_habits: Mapped[list] = mapped_column(JSON, default=list)
    topics: Mapped[list] = mapped_column(JSON, default=list)             # [{value, confidence}]
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WritingStyle(Base):
    __tablename__ = "writing_styles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Cascade: deleting a person removes their writing style.
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), unique=True, index=True)
    common_words: Mapped[list] = mapped_column(JSON, default=list)
    common_phrases: Mapped[list] = mapped_column(JSON, default=list)
    emoji_usage: Mapped[dict] = mapped_column(JSON, default=dict)        # common_emojis, frequency
    sticker_usage: Mapped[dict] = mapped_column(JSON, default=dict)      # count
    average_message_length: Mapped[float] = mapped_column(Float, default=0.0)   # chars
    average_words_per_message: Mapped[float] = mapped_column(Float, default=0.0)
    language_mix: Mapped[dict] = mapped_column(JSON, default=dict)       # {english, urdu, roman_urdu, ...}
    tone: Mapped[str] = mapped_column(String(50), default="neutral")
    punctuation_style: Mapped[dict] = mapped_column(JSON, default=dict)
    common_greetings: Mapped[list] = mapped_column(JSON, default=list)
    common_endings: Mapped[list] = mapped_column(JSON, default=list)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    source_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    memory_type: Mapped[str] = mapped_column(String(50), index=True)  # FACT / PREFERENCE / ...
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | corrected | deleted
    correction_of_id: Mapped[int | None] = mapped_column(ForeignKey("memories.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EmbeddingRecord(Base):
    __tablename__ = "embedding_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Cascade: deleting a memory removes its embedding record.
    memory_id: Mapped[int] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), unique=True, index=True)
    vector_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    model: Mapped[str] = mapped_column(String(100), default="")
    checksum: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# Lifecycle statuses recorded on each version of a memory. They mirror the
# memory table's status column but use the explicit versioning vocabulary from
# the memory-versioning spec: ACTIVE / HISTORICAL / SUPERSEDED / UNCERTAIN /
# ARCHIVED. ``set_status`` maps the legacy values (active/corrected/deleted).
VERSION_STATUS_ACTIVE = "ACTIVE"
VERSION_STATUS_HISTORICAL = "HISTORICAL"
VERSION_STATUS_SUPERSEDED = "SUPERSEDED"
VERSION_STATUS_UNCERTAIN = "UNCERTAIN"
VERSION_STATUS_ARCHIVED = "ARCHIVED"


class MemoryVersion(Base):
    """Append-only history for a memory.

    Every time a memory is created, corrected, edited, or retired a new row is
    recorded. Old values are never destroyed: "what did I previously prefer?"
    is answered by reading earlier versions of the same memory chain.
    """

    __tablename__ = "memory_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    memory_id: Mapped[int] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default=VERSION_STATUS_ACTIVE)
    content: Mapped[str] = mapped_column(Text, default="")
    memory_type: Mapped[str] = mapped_column(String(50), default="FACT")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    source_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(30), default="system")  # import|analyze|chat|correction|edit|manual
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ConversationSummary(Base):
    """Derived summary of a conversation.

    Summaries are bounded summaries of conversation content. They never
    replace original messages. Summaries are regenerated incrementally
    when new messages arrive past a configurable threshold.
    """

    __tablename__ = "conversation_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    message_start_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_end_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(String(100), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# Relationship type constants for memory_relationships
RELATIONSHIP_SUPPORTS = "supports"
RELATIONSHIP_CONTRADICTS = "contradicts"
RELATIONSHIP_SUPERSEDES = "supersedes"
RELATIONSHIP_RELATED_TO = "related_to"
RELATIONSHIP_DERIVED_FROM = "derived_from"
RELATIONSHIP_CLARIFIES = "clarifies"

VALID_RELATIONSHIP_TYPES = {
    RELATIONSHIP_SUPPORTS,
    RELATIONSHIP_CONTRADICTS,
    RELATIONSHIP_SUPERSEDES,
    RELATIONSHIP_RELATED_TO,
    RELATIONSHIP_DERIVED_FROM,
    RELATIONSHIP_CLARIFIES,
}


class MemoryRelationship(Base):
    """Directed relationship between two memories in the same project.

    Relationships are project-scoped and validated. Cross-project
    relationships are rejected at the service layer.

    Directionality:
    - supports: source supports/targets target
    - contradicts: source contradicts target
    - supersedes: source replaces target as current truth
    - related_to: symmetric (either direction is fine)
    - derived_from: source was derived from target
    - clarifies: source clarifies/extends target
    """

    __tablename__ = "memory_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    source_memory_id: Mapped[int] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    target_memory_id: Mapped[int] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)