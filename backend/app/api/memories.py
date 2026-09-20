"""Memory management endpoints (list, create, correct, edit, delete, search)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AppContext, get_context, get_db
from app.core.exceptions import ImportValidationError, NotFoundError
from app.database.repositories import (
    MemoryRepository,
    MemoryVersionRepository,
    MessageRepository,
    PersonRepository,
)
from app.schemas.chat import MemoryConfirmOut, MemoryConfirmRequest
from app.schemas.memory import (
    MemoryCorrectRequest,
    MemoryCreateRequest,
    MemoryEditRequest,
    MemoryOut,
    MemorySearchRequest,
    MemoryVersionOut,
    to_memory_out,
    to_memory_version_out,
)
from app.services.memory_service import MemoryService

router = APIRouter()


def _person_name(db: Session, person_id: int) -> str:
    person = PersonRepository(db).get(person_id)
    return person.name if person else ""


@router.get("/memories", response_model=list[MemoryOut])
def list_memories(
    person_id: Optional[int] = None,
    memory_type: Optional[str] = None,
    query_text: str = Query("", description="Full-text filter"),
    min_confidence: float = 0.0,
    status: str = Query("active", description="active | corrected | all"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = MemoryRepository(db).search(
        query_text=query_text,
        person_id=person_id,
        memory_type=memory_type,
        min_confidence=min_confidence,
        status=status,
        limit=limit,
    )
    return [to_memory_out(m, _person_name(db, m.person_id)) for m in rows]


@router.get("/memories/{memory_id}", response_model=MemoryOut)
def get_memory(memory_id: int, db: Session = Depends(get_db)):
    memory = MemoryRepository(db).get(memory_id)
    if memory is None:
        raise NotFoundError("Memory not found.")
    return to_memory_out(memory, _person_name(db, memory.person_id))


@router.get("/memories/{memory_id}/versions", response_model=list[MemoryVersionOut])
def get_memory_versions(memory_id: int, db: Session = Depends(get_db)):
    """Append-only version history for a memory (revision 1 .. latest)."""
    memory = MemoryRepository(db).get(memory_id)
    if memory is None:
        raise NotFoundError("Memory not found.")
    versions = MemoryVersionRepository(db).list_for_memory(memory_id)
    return [to_memory_version_out(v) for v in versions]


@router.post("/memories", response_model=MemoryOut)
def create_memory(request: MemoryCreateRequest, db: Session = Depends(get_db)):
    person = PersonRepository(db).get(request.person_id)
    if person is None:
        raise NotFoundError("Person not found.")
    memory = MemoryService(db).create_manual(
        person_id=request.person_id,
        content=request.content,
        memory_type=request.memory_type,
        importance=request.importance,
        confidence=request.confidence,
    )
    db.commit()
    return to_memory_out(memory, person.name)


@router.post("/memories/{memory_id}/correct", response_model=MemoryOut)
def correct_memory(memory_id: int, request: MemoryCorrectRequest, db: Session = Depends(get_db), context: AppContext = Depends(get_context)):
    """Repair a wrong memory: retire the old one and store the corrected value."""
    replacement = MemoryService(db).correct(memory_id, request.correction, context.embeddings)
    return to_memory_out(replacement, _person_name(db, replacement.person_id))


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
def edit_memory(memory_id: int, request: MemoryEditRequest, db: Session = Depends(get_db), context: AppContext = Depends(get_context)):
    """Edit a memory in place (content replaced, vector refreshed)."""
    memory = MemoryService(db).edit(memory_id, request.content, context.embeddings)
    return to_memory_out(memory, _person_name(db, memory.person_id))


@router.delete("/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: int, db: Session = Depends(get_db), context: AppContext = Depends(get_context)):
    MemoryService(db).delete(memory_id, context.embeddings)
    return None


@router.post("/memories/{memory_id}/archive", response_model=MemoryOut)
def archive_memory(memory_id: int, db: Session = Depends(get_db), context: AppContext = Depends(get_context)):
    """Archive a memory: kept in history, no longer retrieved as current fact."""
    memory = MemoryService(db).archive(memory_id, context.embeddings)
    return to_memory_out(memory, _person_name(db, memory.person_id))


@router.post("/memories/{memory_id}/restore", response_model=MemoryOut)
def restore_memory(memory_id: int, db: Session = Depends(get_db), context: AppContext = Depends(get_context)):
    """Restore an archived memory back to active."""
    memory = MemoryService(db).restore(memory_id, context.embeddings)
    return to_memory_out(memory, _person_name(db, memory.person_id))


@router.post("/memories/confirm", response_model=MemoryConfirmOut)
def confirm_memory(
    request: MemoryConfirmRequest,
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    """Confirm a proposed memory from a chat turn (memory_mode="ask").

    ``save`` persists the learned memory (idempotent), ``edit`` stores the
    user-edited text instead, and ``discard`` stores nothing.
    """
    message = MessageRepository(db).get(request.message_id)
    if message is None:
        raise NotFoundError("The chat turn was not found.")
    me_person = PersonRepository(db).get(request.person_id)
    if me_person is None:
        raise NotFoundError("Person not found.")

    # The source turn must belong to the same project as the person the memory
    # is about, otherwise confirmation could cross project boundaries.
    conversation = message.conversation
    friend = PersonRepository(db).get(conversation.person_id) if conversation is not None else None
    if friend is None or friend.project_id != me_person.project_id:
        raise NotFoundError("That chat turn does not belong to this person's project.")

    service = MemoryService(db)
    if request.action == "discard":
        return MemoryConfirmOut(saved=False, action="discard")

    if request.action == "edit":
        content = (request.content or "").strip()
        if not content:
            raise ImportValidationError("Edited memory text is empty.")
        memory = service.create_manual(
            person_id=me_person.id,
            content=content,
            memory_type=(request.memory_type or "FACT"),
            importance=0.6,
            confidence=0.7,
        )
        db.commit()
        return MemoryConfirmOut(
            saved=True,
            action="edit",
            memory_id=memory.id,
            content=memory.content,
            memory_type=memory.memory_type,
        )

    result = service.learn_from_user_turn(me_person, message, context.embeddings)
    if result.memory is None:
        return MemoryConfirmOut(saved=False, action="save")
    return MemoryConfirmOut(
        saved=True,
        action="save",
        memory_id=result.memory.id,
        content=result.memory.content,
        memory_type=result.memory.memory_type,
    )


@router.post("/memories/search", response_model=list[MemoryOut])
def search_memories(request: MemorySearchRequest, db: Session = Depends(get_db)):
    rows = MemoryRepository(db).search(
        query_text=request.query,
        person_id=request.person_id,
        memory_type=request.memory_type,
        min_confidence=request.min_confidence,
        limit=request.limit,
    )
    return [to_memory_out(m, _person_name(db, m.person_id)) for m in rows]