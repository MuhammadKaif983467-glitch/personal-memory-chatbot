"""Memory relationship endpoints.

Provides CRUD for directed relationships between memories in the same
project. Cross-project relationships are rejected.

V3.3 Phase 3 — Backup, Recovery, Summarization & Memory Relationships.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import AppContext, get_context, get_db
from app.core.exceptions import NotFoundError
from app.database.models import VALID_RELATIONSHIP_TYPES
from app.database.repositories import MemoryRelationshipRepository, MemoryRepository

router = APIRouter(prefix="/memory-relationships", tags=["memory-relationships"])


class RelationshipCreateRequest(BaseModel):
    project_id: Optional[int] = None
    source_memory_id: int
    target_memory_id: int
    relationship_type: str
    confidence: float = 0.5
    note: str = ""


class RelationshipOut(BaseModel):
    id: int
    project_id: Optional[int] = None
    source_memory_id: int
    target_memory_id: int
    relationship_type: str
    confidence: float
    note: str = ""
    created_at: str = ""


@router.post("", response_model=RelationshipOut)
def create_relationship(
    req: RelationshipCreateRequest,
    db: Session = Depends(get_db),
):
    if req.relationship_type not in VALID_RELATIONSHIP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid relationship type: {req.relationship_type}. "
                   f"Valid types: {sorted(VALID_RELATIONSHIP_TYPES)}",
        )

    repo = MemoryRelationshipRepository(db)
    try:
        obj = repo.create(
            project_id=req.project_id,
            source_memory_id=req.source_memory_id,
            target_memory_id=req.target_memory_id,
            relationship_type=req.relationship_type,
            confidence=req.confidence,
            note=req.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RelationshipOut(
        id=obj.id,
        project_id=obj.project_id,
        source_memory_id=obj.source_memory_id,
        target_memory_id=obj.target_memory_id,
        relationship_type=obj.relationship_type,
        confidence=obj.confidence,
        note=obj.note,
        created_at=obj.created_at.isoformat() if obj.created_at else "",
    )


@router.get("/{memory_id}", response_model=list[RelationshipOut])
def get_relationships(
    memory_id: int,
    db: Session = Depends(get_db),
):
    repo = MemoryRelationshipRepository(db)
    rels = repo.get_for_memory(memory_id)
    return [
        RelationshipOut(
            id=r.id,
            project_id=r.project_id,
            source_memory_id=r.source_memory_id,
            target_memory_id=r.target_memory_id,
            relationship_type=r.relationship_type,
            confidence=r.confidence,
            note=r.note,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rels
    ]


@router.get("/project/{project_id}", response_model=list[RelationshipOut])
def get_project_relationships(
    project_id: int,
    db: Session = Depends(get_db),
):
    repo = MemoryRelationshipRepository(db)
    rels = repo.get_by_project(project_id)
    return [
        RelationshipOut(
            id=r.id,
            project_id=r.project_id,
            source_memory_id=r.source_memory_id,
            target_memory_id=r.target_memory_id,
            relationship_type=r.relationship_type,
            confidence=r.confidence,
            note=r.note,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rels
    ]


@router.delete("/{relationship_id}")
def delete_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
):
    repo = MemoryRelationshipRepository(db)
    deleted = repo.delete(relationship_id)
    if not deleted:
        raise NotFoundError("Relationship not found.")
    return {"deleted": True}
