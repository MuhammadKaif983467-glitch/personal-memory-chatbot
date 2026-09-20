"""Project (workspace) management + project-scoped resource endpoints.

Projects isolate people / conversations / memories / vectors. The legacy
top-level endpoints continue to operate over all data (backfilled into the
default project); these nested routes expose explicit per-project access.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AppContext, get_context, get_db
from app.database.repositories import (
    ConversationRepository,
    MemoryRepository,
    MessageRepository,
    PersonRepository,
    ProjectRepository,
)
from app.schemas.memory import MemoryOut, MemoryVersionOut, to_memory_out, to_memory_version_out
from app.schemas.message import ConversationOut, to_conversation_out
from app.schemas.person import PersonOut, to_person_out
from app.schemas.project import ProjectCreate, ProjectDeleteResult, ProjectDetailOut, ProjectOut, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter()


def _project_out(project_id: int, db: Session) -> ProjectOut:
    project = ProjectRepository(db).get(project_id)
    if project is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Project not found.")
    return ProjectOut(
        id=project.id,
        name=project.name,
        user_id=project.user_id,
        created_at=project.created_at,
        stats=ProjectRepository(db).stats(project.id),
    )


def _participants(project, db: Session) -> list[PersonOut]:
    people_repo = PersonRepository(db)
    message_repo = MessageRepository(db)
    return [
        to_person_out(person, message_repo.count_for_person(person.id))
        for person in people_repo.list_all(project_id=project.id)
    ]


@router.post("/projects", response_model=ProjectOut)
def create_project(request: ProjectCreate, db: Session = Depends(get_db)):
    participants = [
        {"name": p.name, "role": p.role}
        for p in request.participants
    ]
    project = ProjectService(db).create(request.name, participants=participants or None)
    return ProjectOut(
        id=project.id,
        name=project.name,
        user_id=project.user_id,
        created_at=project.created_at,
        stats=ProjectRepository(db).stats(project.id),
    )


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return [
        ProjectOut(
            id=p.id,
            name=p.name,
            user_id=p.user_id,
            created_at=p.created_at,
            stats=ProjectRepository(db).stats(p.id),
        )
        for p in ProjectRepository(db).list_all()
    ]


@router.get("/projects/{project_id}", response_model=ProjectDetailOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = ProjectRepository(db).get(project_id)
    if project is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Project not found.")
    base = _project_out(project_id, db)
    return ProjectDetailOut(
        id=base.id,
        name=base.name,
        user_id=base.user_id,
        created_at=base.created_at,
        stats=base.stats,
        participants=_participants(project, db),
    )


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, request: ProjectUpdate, db: Session = Depends(get_db)):
    project = ProjectRepository(db).get(project_id)
    if project is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Project not found.")
    project.name = request.name.strip()
    db.commit()
    db.refresh(project)
    return ProjectOut(
        id=project.id,
        name=project.name,
        user_id=project.user_id,
        created_at=project.created_at,
        stats=ProjectRepository(db).stats(project.id),
    )


@router.delete("/projects/{project_id}", response_model=ProjectDeleteResult)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    return ProjectService(db).delete(project_id, context.embeddings)


@router.get("/projects/{project_id}/people", response_model=list[PersonOut])
def list_project_people(project_id: int, db: Session = Depends(get_db)):
    _project_out(project_id, db)  # 404 when the project does not exist
    people_repo = PersonRepository(db)
    message_repo = MessageRepository(db)
    return [
        to_person_out(person, message_repo.count_for_person(person.id))
        for person in people_repo.list_all(project_id=project_id)
    ]


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationOut])
def list_project_conversations(project_id: int, db: Session = Depends(get_db)):
    _project_out(project_id, db)  # 404 when the project does not exist
    conversation_repo = ConversationRepository(db)
    return [
        to_conversation_out(conversation, conversation_repo.message_count(conversation.id))
        for conversation in conversation_repo.list_all(project_id=project_id)
    ]


@router.get("/projects/{project_id}/memories", response_model=list[MemoryOut])
def list_project_memories(
    project_id: int,
    status: str = Query("active", description="active | corrected | all"),
    person_id: Optional[int] = None,
    memory_type: Optional[str] = None,
    query_text: str = Query("", description="Full-text filter"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    _project_out(project_id, db)  # 404 when the project does not exist
    rows = MemoryRepository(db).search(
        project_id=project_id,
        person_id=person_id,
        memory_type=memory_type,
        query_text=query_text,
        status=status,
        limit=limit,
    )
    return [to_memory_out(m, _person_name(db, m.person_id)) for m in rows]


def _person_name(db: Session, person_id: int) -> str:
    person = PersonRepository(db).get(person_id)
    return person.name if person else ""