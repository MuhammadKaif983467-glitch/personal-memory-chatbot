"""Export service.

Serializes clean data (messages, conversations, people/profiles/styles,
memories) to plain JSON. Original + cleaned message content is both included.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.repositories import (
    ConversationRepository,
    MemoryRepository,
    MessageRepository,
    PersonProfileRepository,
    PersonRepository,
    WritingStyleRepository,
)
from app.utils.timestamps import format_timestamp


class ExportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def conversations(self, project_id: int | None = None) -> dict:
        conversations = ConversationRepository(self.session).list_all(project_id=project_id)
        messages_repo = MessageRepository(self.session)
        data = []
        for conversation in conversations:
            rows = messages_repo.list_by_conversation(conversation.id)
            data.append(
                {
                    "id": conversation.id,
                    "person_id": conversation.person_id,
                    "title": conversation.title,
                    "source": conversation.source,
                    "started_at": format_timestamp(conversation.started_at),
                    "ended_at": format_timestamp(conversation.ended_at),
                    "messages": [
                        {
                            "id": m.id,
                            "sender": m.sender,
                            "content": m.content,
                            "original_content": m.original_content,
                            "timestamp": format_timestamp(m.timestamp),
                            "message_type": m.message_type,
                            "is_duplicate": m.is_duplicate,
                            "is_spam": m.is_spam,
                            "language": m.language,
                            "metadata": m.msg_metadata or {},
                        }
                        for m in rows
                    ],
                }
            )
        return _wrap("conversations", data)

    def messages(self, project_id: int | None = None) -> dict:
        """Flat export of stored messages, optionally scoped to a project."""
        messages_repo = MessageRepository(self.session)
        if project_id is not None:
            conv_ids = [c.id for c in ConversationRepository(self.session).list_all(project_id=project_id)]
            from sqlalchemy import select
            from app.database.models import Message
            all_msgs = self.session.scalars(
                select(Message)
                .where(Message.conversation_id.in_(conv_ids))
                .order_by(Message.timestamp.asc(), Message.id.asc())
            ).all()
        else:
            all_msgs = messages_repo.all_for_export()
        rows = [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "person_id": m.person_id,
                "sender": m.sender,
                "content": m.content,
                "original_content": m.original_content,
                "timestamp": format_timestamp(m.timestamp),
                "message_type": m.message_type,
                "is_duplicate": m.is_duplicate,
                "is_spam": m.is_spam,
                "language": m.language,
                "metadata": m.msg_metadata or {},
            }
            for m in all_msgs
        ]
        return _wrap("messages", rows)

    def memories(self, project_id: int | None = None) -> dict:
        people = {p.id: p.name for p in PersonRepository(self.session).list_all()}
        memories_repo = MemoryRepository(self.session)
        rows = []
        for memory in memories_repo.list_all_include_non_active():
            if project_id is not None and memory.project_id != project_id:
                continue
            rows.append(
                {
                    "id": memory.id,
                    "person_id": memory.person_id,
                    "person_name": people.get(memory.person_id, ""),
                    "content": memory.content,
                    "memory_type": memory.memory_type,
                    "importance": memory.importance,
                    "confidence": memory.confidence,
                    "status": memory.status,
                    "source_message_id": memory.source_message_id,
                    "correction_of_id": memory.correction_of_id,
                    "created_at": format_timestamp(memory.created_at),
                    "updated_at": format_timestamp(memory.updated_at),
                }
            )
        return _wrap("memories", rows)

    def people(self, project_id: int | None = None) -> dict:
        people_repo = PersonRepository(self.session)
        rows = []
        for person in people_repo.list_all():
            if project_id is not None and person.project_id != project_id:
                continue
            profile = PersonProfileRepository(self.session).get_for_person(person.id)
            style = WritingStyleRepository(self.session).get_for_person(person.id)
            rows.append(
                {
                    "id": person.id,
                    "name": person.name,
                    "relationship": person.relationship_type,
                    "created_at": format_timestamp(person.created_at),
                    "profile": profile.interests if profile else [],
                    "writing_style": style.language_mix if style else {},
                }
            )
        return _wrap("people", rows)


def _wrap(kind: str, items: list) -> dict:
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        kind: items,
        "count": len(items),
    }