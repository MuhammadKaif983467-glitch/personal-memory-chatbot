"""Conversation summarization endpoints.

Provides summary generation and retrieval for conversations.
Summaries are derived data that never replace original messages.

V3.3 Phase 3 — Backup, Recovery, Summarization & Memory Relationships.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import AppContext, get_context, get_db
from app.core.exceptions import NotFoundError
from app.database.repositories import ConversationRepository
from app.services.summarization_service import SummarizationService

router = APIRouter(prefix="/summaries", tags=["summaries"])


class SummaryOut(BaseModel):
    conversation_id: int
    summary: str
    message_count: int
    message_start_id: Optional[int] = None
    message_end_id: Optional[int] = None
    version: int
    model: str = ""
    created_at: str = ""
    updated_at: str = ""


class SummaryGenerateRequest(BaseModel):
    conversation_id: int
    project_id: Optional[int] = None


@router.get("/{conversation_id}", response_model=SummaryOut)
def get_summary(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    conv = ConversationRepository(db).get(conversation_id)
    if conv is None:
        raise NotFoundError("Conversation not found.")

    svc = SummarizationService(db)
    summary = svc.get_summary(conversation_id)
    if summary is None:
        raise NotFoundError("No summary available for this conversation.")

    return SummaryOut(
        conversation_id=summary.conversation_id,
        summary=summary.summary,
        message_count=summary.message_count,
        message_start_id=summary.message_start_id,
        message_end_id=summary.message_end_id,
        version=summary.version,
        model=summary.model,
        created_at=summary.created_at.isoformat() if summary.created_at else "",
        updated_at=summary.updated_at.isoformat() if summary.updated_at else "",
    )


@router.post("/generate", response_model=SummaryOut)
def generate_summary(
    req: SummaryGenerateRequest,
    db: Session = Depends(get_db),
):
    conv = ConversationRepository(db).get(req.conversation_id)
    if conv is None:
        raise NotFoundError("Conversation not found.")

    svc = SummarizationService(db)
    summary = svc.generate_summary(
        req.conversation_id,
        project_id=req.project_id or conv.project_id,
    )
    if summary is None:
        raise NotFoundError("No messages to summarize.")

    return SummaryOut(
        conversation_id=summary.conversation_id,
        summary=summary.summary,
        message_count=summary.message_count,
        message_start_id=summary.message_start_id,
        message_end_id=summary.message_end_id,
        version=summary.version,
        model=summary.model,
        created_at=summary.created_at.isoformat() if summary.created_at else "",
        updated_at=summary.updated_at.isoformat() if summary.updated_at else "",
    )


@router.delete("/{conversation_id}")
def delete_summary(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    svc = SummarizationService(db)
    deleted = svc.delete_summary(conversation_id)
    return {"deleted": deleted}
