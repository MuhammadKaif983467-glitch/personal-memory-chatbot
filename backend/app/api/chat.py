"""Chat + conversation + message endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AppContext, get_context, get_db
from app.core.exceptions import NotFoundError
from app.database.repositories import ConversationRepository, MessageRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.message import (
    ConversationDeleteResult,
    ConversationOut,
    MessageOut,
    to_conversation_out,
    to_message_out,
)
from app.services.memory_service import MemoryService

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db), context: AppContext = Depends(get_context)):
    response = context.chat_service.handle(db, request)
    context.metrics.inc("chat_requests")
    return response


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db)):
    conversation_repo = ConversationRepository(db)
    return [
        to_conversation_out(conversation, conversation_repo.message_count(conversation.id))
        for conversation in conversation_repo.list_all()
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = ConversationRepository(db).get(conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation not found.")
    return to_conversation_out(conversation, ConversationRepository(db).message_count(conversation_id))


@router.get("/messages", response_model=list[MessageOut])
def list_messages(
    person_id: Optional[int] = None,
    conversation_id: Optional[int] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = MessageRepository(db).list_all(
        person_id=person_id, conversation_id=conversation_id, limit=limit, offset=offset
    )
    return [to_message_out(m) for m in rows]


@router.get("/messages/{message_id}", response_model=MessageOut)
def get_message(message_id: int, db: Session = Depends(get_db)):
    """Fetch a single message (e.g. to inspect the source of a memory)."""
    message = MessageRepository(db).get(message_id)
    if message is None:
        raise NotFoundError("Message not found.")
    return to_message_out(message)


@router.delete("/conversations/{conversation_id}", response_model=ConversationDeleteResult)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    """Delete a conversation and the messages it contains.

    Memories are handled explicitly (see ConversationDeleteResult): memories
    sourced from this conversation are retired and de-embedded unless another
    memory depends on them or they are already retired.
    """
    conversation_repo = ConversationRepository(db)
    conversation = conversation_repo.get(conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation not found.")

    memories_deleted, memories_preserved = MemoryService(db).delete_conversation_memories(
        conversation_id, context.embeddings
    )

    messages = MessageRepository(db).list_by_conversation(conversation_id)
    for message in messages:
        db.delete(message)
    db.delete(conversation)
    db.commit()
    context.metrics.inc("conversations_deleted")
    return ConversationDeleteResult(
        conversation_id=conversation_id,
        messages_deleted=len(messages),
        memories_deleted=memories_deleted,
        memories_preserved=memories_preserved,
    )


@router.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: int, db: Session = Depends(get_db)):
    """Delete a single message (used to roll back a chat proof turn)."""
    message = MessageRepository(db).get(message_id)
    if message is None:
        raise NotFoundError("Message not found.")
    MessageRepository(db).delete(message)
    db.commit()