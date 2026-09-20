"""Schemas for import / export."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from pydantic import BaseModel, Field, field_validator

ALLOWED_MESSAGE_TYPES = {
    "text", "text_emoji", "sticker", "image", "video", "audio", "voice",
    "location", "contact", "file", "link", "system", "",
}


class ImportedConversationInfo(BaseModel):
    title: str = "Imported Chat"
    person: str
    source: str = "import"


class ImportedMessage(BaseModel):
    sender: str = ""
    timestamp: object = None
    content: str = Field("", max_length=200_000)
    message_type: str = "text"
    # Stable identifier from the source system (e.g. the dataset message_id).
    # Used by the safe import mode to skip records that already exist.
    source_id: str = ""
    # Arbitrary passthrough metadata (topic, duplicate flag, ...) preserved on
    # the stored message so imports stay traceable.
    metadata: dict = Field(default_factory=dict)

    @field_validator("message_type")
    @classmethod
    def _type_allowed(cls, value: str) -> str:
        v = str(value).strip().casefold()
        if v not in ALLOWED_MESSAGE_TYPES:
            v = "file"
        return v


class ImportPayload(BaseModel):
    consent_confirmed: bool
    conversation: ImportedConversationInfo
    messages: Sequence[ImportedMessage]
    project_id: Optional[int] = None


class ImportResult(BaseModel):
    ok: bool = True
    conversation_id: Optional[int] = None
    person_id: Optional[int] = None
    person_name: str = ""
    conversation_title: str = ""
    total: int = 0
    imported: int = 0
    skipped: int = 0
    removed_empty: int = 0
    removed_duplicates: int = 0
    removed_system: int = 0
    spam_flagged: int = 0
    cleaned: int = 0
    messages_created: int = 0
    errors: Sequence[str] = Field(default_factory=list)
    warnings: Sequence[str] = Field(default_factory=list)


class ImportPreviewItem(BaseModel):
    line: int = 0
    sender: str = ""
    timestamp: object = None
    content: str = ""
    message_type: str = "text"
    issue: str = ""


class ImportPreviewResult(BaseModel):
    source: str = "unknown"
    person: str = ""
    file_name: str = ""
    total_records: int = 0
    valid_messages: int = 0
    malformed: int = 0
    empty: int = 0
    preview: Sequence[ImportPreviewItem] = []
    warnings: Sequence[str] = []
    consent_required: bool = False
    messages_previewed: int = 0


class AnalyzeResult(BaseModel):
    person_id: int
    messages_analyzed: int
    memories_created: int
    memories_total: int
    embeddings_created: int
    profile_generated: bool
    style_generated: bool
    memories_extracted: int = 0
    chunks_created: int = 0
    chunks_total: int = 0


class DatasetImportResult(ImportResult):
    """Richer report for full-dataset imports (multi-participant histories)."""

    dataset_name: str = ""
    dataset_version: str = ""
    dry_run: bool = False
    mode: str = "safe"
    persons: Sequence[str] = Field(default_factory=list)
    valid_messages: int = 0
    invalid_messages: int = 0
    duplicates_detected: int = 0
    new_messages: int = 0
    skipped_existing: int = 0
    messages_per_person: dict = Field(default_factory=dict)
    memories_created: int = 0
    memories_extracted: int = 0
    memories_before: int = 0
    seeded_memories: int = 0
    corrected_memories: int = 0
    superseded_memories: int = 0
    active_memories: int = 0
    chunks_created: int = 0
    chunks_total: int = 0
    embeddings_created: int = 0
    profile_generated: bool = False
    style_generated: bool = False
    warnings: Sequence[str] = Field(default_factory=list)