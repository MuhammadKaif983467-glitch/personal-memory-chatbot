"""Chat service - the orchestrator of the whole workflow.

Flow per user message:

  persist user message
  -> retrieve relevant memories (vector search)
  -> build bounded context
  -> run confidence check
  -> call the AI provider
  -> attach disclosure hints
  -> persist assistant reply
  -> update memories (small, safe extraction)

Business logic lives here; endpoints stay thin.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.prompts import build_system_prompt
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger, safe_snippet
from app.core.metrics import Metrics
from app.database.models import Message
from app.database.repositories import (
    ConversationRepository,
    MessageRepository,
    PersonProfileRepository,
    PersonRepository,
    WritingStyleRepository,
)
from app.schemas.chat import (
    ChatDebugOut,
    ChatPreviewResponse,
    ChatRequest,
    ChatResponse,
    LearnedMemoryOut,
    MemorySourceOut,
    PendingMemoryOut,
    RetrievedMemoryOut,
)
from app.schemas.memory import ConfidenceOut
from app.services.confidence_service import interpret as interpret_confidence
from app.services.context_service import build_context
from app.services.disclosure_service import build_indicator, build_sources
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import LEARNED_CORRECTION, LEARNED_NONE, MemoryService
from app.services.retrieval_service import RetrievalService
from app.utils.text import detect_language
from app.vectorstore.base import VectorStore

logger = get_logger("chat")


class ChatService:
    def __init__(
        self,
        settings: Settings,
        provider: AIProvider,
        embeddings: EmbeddingService,
        vector_store: VectorStore,
        metrics: Optional[Metrics] = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.embeddings = embeddings
        self.metrics = metrics or Metrics()
        self.retrieval = RetrievalService(
            embeddings,
            vector_store,
            min_confidence=settings.memory_min_confidence,
            default_limit=settings.retrieval_limit,
        )

    def handle(self, session: Session, request: ChatRequest) -> ChatResponse:
        started = time.time()
        people = PersonRepository(session)
        person = people.get(request.person_id) if request.person_id else None
        if person is None:
            raise NotFoundError(
                "A person is required to ask about. Pick a person or import a conversation first."
            )

        conversation_repo = ConversationRepository(session)
        message_repo = MessageRepository(session)
        now = datetime.now(timezone.utc)

        if request.conversation_id:
            conversation = conversation_repo.get(request.conversation_id)
            if conversation is None or conversation.person_id != person.id:
                raise NotFoundError("Conversation not found for this person.")
        else:
            conversation = conversation_repo.create(
                person.id, f"Chat with {person.name}", source="chat"
            )
            conversation_repo.update_range(conversation.id, now, now)

        # 1. Persist the user's message.
        language, _ = detect_language(request.message)
        user_message = Message(
            conversation_id=conversation.id,
            person_id=None,
            sender=request.sender_name or "me",
            content=request.message,
            original_content=request.message,
            timestamp=now,
            message_type="text",
            message_origin="live_user",
            is_duplicate=False,
            is_spam=False,
            language=language,
            msg_metadata={"live": True},
        )
        message_repo.add(user_message)
        conversation_repo.update_range(conversation.id, None, now)
        session.commit()
        self.metrics.inc("messages_created")

        # 2. Retrieve relevant memories.
        self.metrics.inc("retrieval_count")
        retrieved = self.retrieval.retrieve(
            session, request.message, person_id=person.id,
            conversation_id=conversation.id,
        )

        # 3. Recent conversation for context.
        recent = message_repo.recent_by_conversation(conversation.id, self.settings.recent_conversation_messages)

        # 4. Build bounded context.
        profile = PersonProfileRepository(session).get_for_person(person.id)
        style = WritingStyleRepository(session).get_for_person(person.id)
        confidence: ConfidenceOut = interpret_confidence(retrieved)
        context = build_context(
            question=request.message,
            recent_messages=recent,
            retrieved=retrieved,
            person=person,
            profile=profile,
            style=style,
            confidence=confidence,
            budget_chars=self.settings.context_budget_chars,
            recent_limit=self.settings.recent_conversation_messages,
        )

        # 5. Call the AI provider.
        self.metrics.inc("ai_requests")
        history = [
            {"role": "assistant" if m.is_assistant else "user", "content": (m.content or "")[-2000:]}
            for m in recent
        ]
        system_prompt = build_system_prompt(
            person.name, person.relationship_type, confidence.level, context.text, style=style
        )
        reply = self.provider.generate(system_prompt, history)

        # 6. Persist the assistant reply.
        assistant_message = Message(
            conversation_id=conversation.id,
            person_id=None,
            sender="assistant",
            content=reply,
            original_content=reply,
            timestamp=datetime.now(timezone.utc),
            message_type="text",
            message_origin="generated",
            is_duplicate=False,
            is_spam=False,
            language="english",
            msg_metadata={"live": True},
        )
        message_repo.add(assistant_message)
        session.commit()
        self.metrics.inc("messages_created")

        # 7. Disclosure + visible memory sources.
        indicator = build_indicator(retrieved)
        if self.settings.show_memory_sources:
            sources = build_sources(retrieved)
        else:
            sources = []
        logger.info(
            "Chat reply for person=%s question=%s confidence=%s source_count=%d time=%.2fs",
            person.id, safe_snippet(request.message), confidence.level, len(retrieved), time.time() - started,
        )

        # 8. Post-chat memory update + current-conversation learning, honouring
        #    the configured memory mode:
        #      disabled -> nothing is learned from this turn
        #      ask      -> a proposed memory is returned for user confirmation
        #      auto     -> small, safe extractions + high-confidence learning
        memos = MemoryService(session)
        memory_mode = (self.settings.memory_mode or "auto").strip().casefold()
        me_person = None
        if person.project_id is not None:
            me_person = PersonRepository(session).find_by_role(person.project_id, "ME")

        learned: list[LearnedMemoryOut] = []
        pending_memory = None
        if memory_mode == "disabled":
            pass  # explicit opt-out: no memory learned from this turn
        elif memory_mode == "ask" and me_person is not None:
            try:
                plan = memos.plan_learning(me_person, user_message)
                if plan is not None:
                    pending_memory = PendingMemoryOut(
                        message_id=plan.message_id,
                        person_id=plan.person_id,
                        person_name=plan.person_name,
                        content=plan.content,
                        memory_type=plan.memory_type,
                        confidence=plan.confidence,
                        importance=plan.importance,
                    )
            except Exception:
                logger.exception("Learning proposal failed (non-fatal).")
        else:
            try:
                memos.update_from_messages(person, [user_message])
            except Exception:
                logger.exception("Post-chat memory update failed (non-fatal).")
            if me_person is not None:
                try:
                    result = memos.learn_from_user_turn(me_person, user_message, self.embeddings)
                    if result.outcome != LEARNED_NONE:
                        logger.info(
                            "Current-conversation learning: outcome=%s person=%s memory=%s source=%s",
                            result.outcome,
                            safe_snippet(me_person.name),
                            result.memory.id if result.memory else "-",
                            safe_snippet(request.message),
                        )
                    learned = [self._to_learned_out(result)]
                except Exception:
                    logger.exception("Current-conversation learning failed (non-fatal).")

        debug = None
        if request.debug:
            debug = ChatDebugOut(
                retrieved=[self._to_retrieved_out(item) for item in retrieved[:10]],
                context_chars=context.used_chars,
                context_sample=context.text[:1500],
            )

        return ChatResponse(
            reply=reply,
            conversation_id=conversation.id,
            confidence=confidence,
            memory_indicator=indicator,
            show_memory_sources=self.settings.show_memory_sources,
            sources=[MemorySourceOut(**s.model_dump()) for s in sources],
            learned=learned,
            memory_mode=memory_mode,
            pending_memory=pending_memory,
            debug=debug,
        )

    def answer_preview(self, session: Session, request: ChatRequest) -> ChatPreviewResponse:
        """Read-only chat turn used for evaluation and probing.

        Runs the same retrieve -> rank -> context -> confidence -> provider
        pipeline as :meth:`handle` but performs no writes at all: it never
        persists a chat message, creates a memory, updates a profile, or
        touches embeddings. Safe to call against live data.
        """
        person = PersonRepository(session).get(request.person_id) if request.person_id else None
        if person is None:
            raise NotFoundError(
                "A person is required to ask about. Pick a person or import a conversation first."
            )

        # Retrieve + rank (read-only).
        retrieved = self.retrieval.retrieve(
            session, request.message, person_id=person.id,
            conversation_id=request.conversation_id,
        )

        # Recent conversation is optional and only read when a valid
        # conversation for this person is supplied; nothing is created.
        recent: list = []
        if request.conversation_id:
            conversation = ConversationRepository(session).get(request.conversation_id)
            if conversation is not None and conversation.person_id == person.id:
                recent = list(
                    MessageRepository(session).recent_by_conversation(
                        conversation.id, self.settings.recent_conversation_messages
                    )
                )

        profile = PersonProfileRepository(session).get_for_person(person.id)
        style = WritingStyleRepository(session).get_for_person(person.id)
        confidence = interpret_confidence(retrieved)
        context = build_context(
            question=request.message,
            recent_messages=recent,
            retrieved=retrieved,
            person=person,
            profile=profile,
            style=style,
            confidence=confidence,
            budget_chars=self.settings.context_budget_chars,
            recent_limit=self.settings.recent_conversation_messages,
        )

        history = [
            {"role": "assistant" if m.is_assistant else "user", "content": (m.content or "")[-2000:]}
            for m in recent
        ]
        # The provider treats the last turn as the question. ``handle`` gets this
        # from the persisted user message; here we supply it without persisting.
        history.append({"role": "user", "content": request.message})
        system_prompt = build_system_prompt(
            person.name, person.relationship_type, confidence.level, context.text, style=style
        )
        reply = self.provider.generate(system_prompt, history)

        indicator = build_indicator(retrieved)
        sources = build_sources(retrieved) if self.settings.show_memory_sources else []

        return ChatPreviewResponse(
            person_id=person.id,
            person_name=person.name,
            reply=reply,
            confidence=confidence,
            memory_indicator=indicator,
            show_memory_sources=self.settings.show_memory_sources,
            sources=[MemorySourceOut(**s.model_dump()) for s in sources],
            retrieved=[self._to_retrieved_out(item) for item in retrieved],
            context_chars=context.used_chars,
        )

    def _to_learned_out(self, result) -> LearnedMemoryOut:
        memory = result.memory
        superseded_id = None
        if result.reason and result.reason.startswith("superseded memory "):
            superseded_id = int(result.reason.split("superseded memory ")[1])
        return LearnedMemoryOut(
            outcome=result.outcome,
            memory_id=memory.id if memory else None,
            person_id=memory.person_id if memory else None,
            content=memory.content if memory else "",
            memory_type=memory.memory_type if memory else "",
            superseded_memory_id=superseded_id,
            reason=result.reason,
        )

    def _to_retrieved_out(self, item) -> RetrievedMemoryOut:
        memory = item.memory
        source_timestamp = None
        if memory.created_at:
            ts = memory.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            source_timestamp = ts
        return RetrievedMemoryOut(
            memory_id=memory.id,
            content=memory.content,
            memory_type=memory.memory_type,
            confidence=memory.confidence,
            importance=memory.importance,
            source_message_id=memory.source_message_id,
            source_timestamp=source_timestamp,
            similarity=item.similarity,
            rank=item.rank,
        )