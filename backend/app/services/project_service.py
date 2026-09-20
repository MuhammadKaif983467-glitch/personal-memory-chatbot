"""Project (workspace) service.

Projects isolate people, conversations, memories, and their vectors. Deleting
a project removes only its own records plus the corresponding embeddings and
vectors; other projects are untouched.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.database.models import (
    Conversation,
    DEFAULT_PROJECT_NAME,
    EmbeddingRecord,
    Memory,
    MemoryVersion,
    Message,
    Person,
    PersonProfile,
    Project,
    WritingStyle,
)
from app.database.repositories import ProjectRepository
from app.schemas.project import ME_ROLE, OTHER_ROLE, ProjectDeleteResult
from app.services.embedding_service import EmbeddingService


class ProjectService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = ProjectRepository(session)

    def create(
        self,
        name: str,
        user_id: str = "local",
        participants: Optional[Sequence[dict]] = None,
    ) -> Project:
        """Create a project and, when participants are given, its two persons.

        A two-person project holds exactly one ME ("the user") and one OTHER
        participant. Legacy projects (no participants) keep the single-participant
        behaviour used by the existing import/chat flows.
        """
        project = self.projects.create(name, user_id)
        self.session.flush()
        if participants:
            for participant in participants:
                role = ME_ROLE if str(participant["role"]).strip().casefold() in ("me", "self") else OTHER_ROLE
                self.session.add(
                    Person(
                        project_id=project.id,
                        name=str(participant["name"]).strip(),
                        relationship_type="self" if role == ME_ROLE else "friend",
                        participant_role=role,
                    )
                )
            self.session.flush()
        self.session.commit()
        return project

    def detail(self, project_id: int) -> Project:
        project = self.projects.get(project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        return project

    def participants(self, project: Project) -> Sequence[Person]:
        return self.session.query(Person).filter(Person.project_id == project.id).order_by(Person.id).all()

    def delete(self, project_id: int, embeddings: Optional[EmbeddingService]) -> ProjectDeleteResult:
        project = self.projects.get(project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        if (project.name or "").strip() == DEFAULT_PROJECT_NAME:
            raise ForbiddenError(f"The '{DEFAULT_PROJECT_NAME}' project cannot be deleted.")

        persons = list(self.session.query(Person).filter(Person.project_id == project_id).all())
        conversations = list(
            self.session.query(Conversation).filter(Conversation.project_id == project_id).all()
        )
        memories = list(self.session.query(Memory).filter(Memory.project_id == project_id).all())
        person_ids = [p.id for p in persons]
        message_count = 0
        for conversation in conversations:
            message_count += (
                self.session.query(Message)
                .filter(Message.conversation_id == conversation.id)
                .count()
            )

        deleted_vectors = 0
        deleted_embeddings = 0
        for memory in memories:
            record = self.session.query(EmbeddingRecord).filter(
                EmbeddingRecord.memory_id == memory.id
            ).first()
            if record is not None:
                if embeddings is not None:
                    embeddings.vector_store.delete([record.vector_id], session=self.session)
                self.session.delete(record)
                deleted_vectors += 1
                deleted_embeddings += 1
            self.session.query(MemoryVersion).filter(MemoryVersion.memory_id == memory.id).delete()
            self.session.delete(memory)

        for conversation in conversations:
            for message in self.session.query(Message).filter(
                Message.conversation_id == conversation.id
            ).all():
                self.session.delete(message)
            self.session.delete(conversation)

        for pid in person_ids:
            profile = self.session.query(PersonProfile).filter(PersonProfile.person_id == pid).first()
            if profile is not None:
                self.session.delete(profile)
            style = self.session.query(WritingStyle).filter(WritingStyle.person_id == pid).first()
            if style is not None:
                self.session.delete(style)

        for person in persons:
            self.session.delete(person)

        self.session.delete(project)
        self.session.commit()

        return ProjectDeleteResult(
            project_id=project_id,
            deleted_persons=len(persons),
            deleted_conversations=len(conversations),
            deleted_messages=message_count,
            deleted_memories=len(memories),
            deleted_vectors=deleted_vectors,
            deleted_embeddings=deleted_embeddings,
        )