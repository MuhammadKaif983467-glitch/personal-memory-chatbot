"""Memory service.

Memory lifecycle:
  - extraction: rule-based candidate memories from messages (facts,
    preferences, interests, relationships, habits, events, opinions),
  - analysis: the full person pipeline (profile + style + memories +
    chunking + embeddings),
  - correction: mark the old memory corrected, store a replacement, refresh
    the vector store so the old memory is never retrieved as current fact,
  - deletion & editing.

All memory records are traced to a source message id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import ImportValidationError, NotFoundError
from app.core.logging import get_logger
from app.database.models import Memory
from app.database.repositories import (
    MemoryRepository,
    MemoryVersionRepository,
    MessageRepository,
    PersonRepository,
)
from app.schemas.import_export import AnalyzeResult
from app.services.chunking_service import chunk_messages
from app.services.embedding_service import EmbeddingService
from app.services.profile_service import ProfileService
from app.services.style_service import StyleService

logger = get_logger("memory")

# First-person patterns found in the friend's messages.
# Each entry: (compiled regex, memory_type, confidence, value_template)
_MEMORY_PATTERNS = [
    # Interests
    (re.compile(r"\bi (?:really )?(?:like|love) (.{2,45}?)(?:[.,!?]|\s*$)", re.I), "INTEREST", 0.72, "{name} likes {value}"),
    # Preferences
    (re.compile(r"\bi prefer (?:to )?(.{2,45}?)(?:[.,!?]|\s*$)", re.I), "PREFERENCE", 0.72, "{name} prefers {value}"),
    (re.compile(r"\bi (?:don't|dont|do not) like (.{2,45}?)(?:[.,!?]|\s*$)", re.I), "PREFERENCE", 0.7, "{name} does not like {value}"),
    # Facts about identity
    (re.compile(r"\bi am (\d{1,3}) years? old", re.I), "FACT", 0.85, "{name} is {value} years old"),
    (re.compile(r"\bmy name is ([A-Za-z][A-Za-z ]{1,30})[.,!?]?", re.I), "FACT", 0.9, "{name}'s name is {value}"),
    (re.compile(r"\bi (?:study|read) at ([A-Za-z ]{2,40})[.,!?]?", re.I), "FACT", 0.75, "{name} studies at {value}"),
    (re.compile(r"\bi (?:work|am working) (at|in) (.{2,45}?)(?:[.,!?]|\s*$)", re.I), "FACT", 0.75, "{name} works {prep} {value}"),
    (re.compile(r"\bi (?:live|am living) (?:in|at) (.{2,45}?)(?:[.,!?]|\s*$)", re.I), "FACT", 0.7, "{name} lives in {value}"),
    (re.compile(r"\bi was born in (.{2,45}?)(?:[.,!?]|\s*$)", re.I), "FACT", 0.72, "{name} was born in {value}"),
    (re.compile(r"\bmy birthday (?:is|falls on) (.{2,45}?)(?:[.,!?]|\s*$)", re.I), "FACT", 0.8, "{name}'s birthday is {value}"),
    # Relationships
    (re.compile(r"\bmy (brother|sister|mother|father|mom|dad|wife|husband|uncle|aunt|cousin|best friend|friend) (?:is (?:called|named)|is|works) (.{2,45}?)(?:[.,!?]|\s*$)", re.I), "RELATIONSHIP", 0.7, "{name}'s {relation} {tail}"),
    # Habits
    (re.compile(r"\bi (always|usually|often|never|sometimes) (.{2,45}?)(?:[.,!?]|\s*$)", re.I), "HABIT", 0.62, "{name} {adverb} {value}"),
    # Opinions
    (re.compile(r"\bi (?:think|feel) (?:that )?(.{2,60}?)(?:[.,!?]|\s*$)", re.I), "OPINION", 0.45, "{name} thinks {value}"),
    # Events
    (re.compile(r"\bi (?:had|went (?:to )?|visited|attended|celebrated|travelled to) (.{2,45}?)(?:[.,!?]|\s*$)", re.I), "EVENT", 0.55, "{name} had {value}"),
]

# User messages that instruct us to remember something about the person.
_NOTE_PATTERN = re.compile(r"\b(?:remember|note)\s+(?:that\s+)?(.{2,120}?)[.,!?]?\s*$", re.I)

# Messages where the *user* (the "ME" participant) reveals something about
# themselves during the current conversation. These feed current-conversation
# learning: new memory, update, or correction (old value preserved).
# Ordering matters: more specific change statements are matched first.
_USER_LEARNING_PATTERNS = [
    # "I changed my favorite language from Java to Python."
    (re.compile(r"\bi (?:changed|switched) my (?:favorite )?(.+?) from (.+?) to (.+?)(?:[.,!?]|\s*$)", re.I),
     "CORRECTION"),
    # "I now prefer X over Y" / "I prefer X more than Y"
    (re.compile(r"\bi (?:now )?(?:prefer|like|love|enjoy) (.+?) over (.+?)(?:[.,!?]|\s*$)", re.I),
     "PREFERENCE"),
    # "My favorite subject is now Python."
    (re.compile(r"\bmy favorite (.+?) is now (.+?)(?:[.,!?]|\s*$)", re.I), "INTEREST"),
    # "I changed my mind about X - it's Y now." (second clause)
    (re.compile(r"\bi changed my (?:opinion|mind)[^.]*? now (?:it'?s|its) (.+?)(?:[.,!?]|\s*$)", re.I),
     "OPINION"),
]

_IMPORTANCE = {
    "FACT": 0.7,
    "PREFERENCE": 0.6,
    "INTEREST": 0.6,
    "RELATIONSHIP": 0.8,
    "EVENT": 0.7,
    "HABIT": 0.6,
    "OPINION": 0.45,
    "CONVERSATION": 0.4,
    "TEMPORARY": 0.3,
    "GOAL": 0.7,
    "PLAN": 0.7,
    "DATE": 0.8,
    "COMMITMENT": 0.75,
    "DECISION": 0.7,
    "PROJECT": 0.7,
    "EDUCATION": 0.75,
    "WORK": 0.75,
    "LOCATION": 0.7,
    "CORRECTION": 0.75,
    "OTHER": 0.5,
}


@dataclass
class CandidateMemory:
    content: str
    memory_type: str
    confidence: float
    importance: float
    source_message_id: int


# Outcomes of the current-conversation learning pipeline (Phase I).
LEARNED_NEW = "NEW_MEMORY"
LEARNED_UPDATED = "UPDATED_MEMORY"
LEARNED_CORRECTION = "CORRECTION"
LEARNED_NONE = "NO_MEMORY"


@dataclass
class LearnedMemory:
    outcome: str
    memory: Optional[Memory]
    reason: str = ""


@dataclass
class LearningPlan:
    """A proposed memory derived from the user's own turn (ask-before-save).

    Created read-only; the API layer decides whether to persist via
    :meth:`MemoryService.learn_from_user_turn`.
    """

    content: str
    memory_type: str
    confidence: float
    importance: float
    message_id: int
    person_id: int
    person_name: str


def _render(template: str, name: str, **values) -> str:
    if not template:
        return ""
    return template.format(name=name, **values).strip()


def extract_candidates_from_message(person_name: str, message, is_user_message: bool = False) -> list[CandidateMemory]:
    """Produce candidate memories for a single message.

    ``is_user_message=True`` only trusts explicit "remember/note that ..."
    instructions (that mention the person) so the bot never turns casual live
    chat into confirmed facts.
    """
    content = (message.content or "").strip()
    if not content or message.is_duplicate or message.is_spam or message.is_assistant:
        return []

    if is_user_message:
        match = _NOTE_PATTERN.search(content)
        if not match or person_name.casefold() not in content.casefold():
            return []
        value = match.group(1).strip()
        if not value:
            return []
        return [
            CandidateMemory(
                content=value,
                memory_type="FACT",
                confidence=0.7,
                importance=0.7,
                source_message_id=message.id,
            )
        ]

    candidates: list[CandidateMemory] = []
    for regex, memory_type, confidence, template in _MEMORY_PATTERNS:
        match = regex.search(content)
        if not match:
            continue
        groups = match.groups()
        value = _sanitize_value(groups[-1])
        if not value:
            continue

        text_args: dict = {"value": value}
        if memory_type == "RELATIONSHIP":
            text_args["relation"] = groups[0]
            tail = _sanitize_value(groups[1]) if len(groups) > 1 else ""
            text_args["tail"] = tail or ("is " + value)
        elif memory_type == "HABIT":
            text_args["adverb"] = groups[0]
        elif memory_type == "FACT" and len(groups) > 1:
            text_args["prep"] = groups[0]

        rendered = _render(template, person_name, **text_args)
        if not rendered or len(rendered) > 200 or rendered.casefold() == content.casefold():
            continue
        candidates.append(
            CandidateMemory(
                content=rendered,
                memory_type=memory_type,
                confidence=confidence if confidence else 0.55,
                importance=_IMPORTANCE.get(memory_type, 0.5),
                source_message_id=message.id,
            )
        )
        break  # one memory per message keeps extraction conservative
    return candidates


def _sanitize_value(raw: str) -> str:
    value = re.sub(r"\s+", " ", raw).strip(" .,!?;")
    value = value.strip("'\"")
    if len(value) > 60:
        value = value[:60].rsplit(" ", 1)[0]
    return value.strip()


class MemoryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.memories_repo = MemoryRepository(session)
        self.people = PersonRepository(session)
        self.messages_repo = MessageRepository(session)

    # ---- creation / dedupe ----

    def create_memory(self, candidate: CandidateMemory, person_id: int, actor: str = "system") -> Memory:
        existing = self.memories_repo.find_duplicate(person_id, candidate.content, candidate.memory_type)
        if existing is not None:
            return existing
        return self.memories_repo.create(
            person_id=person_id,
            content=candidate.content,
            memory_type=candidate.memory_type,
            source_message_id=candidate.source_message_id,
            importance=candidate.importance,
            confidence=candidate.confidence,
            actor=actor or "system",
        )

    def create_manual(
        self, *, person_id: int, content: str, memory_type: str, importance: float, confidence: float
    ) -> Memory:
        return self.memories_repo.create(
            person_id=person_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            confidence=confidence,
            actor="manual",
        )

    # ---- full person analysis ----

    def analyze_person(
        self,
        person_id: int,
        embeddings: EmbeddingService,
        *,
        chunk_options: Optional[dict] = None,
    ) -> AnalyzeResult:
        person = self.people.get(person_id)
        if person is None:
            raise NotFoundError("Person not found.")

        messages = [
            m for m in self.messages_repo.all_for_person(person_id)
            if m.message_type == "text" and not m.is_duplicate and not m.is_spam and m.content.strip()
        ]

        profile_service = ProfileService(self.session)
        style_service = StyleService(self.session)
        profile = profile_service.build(person_id, messages) if messages else profile_service.get_or_none(person_id)
        style = style_service.analyze(person_id, messages) if messages else style_service.get_or_none(person_id)

        created_memories = 0
        memories_extracted = 0
        for message in messages:
            for candidate in extract_candidates_from_message(person.name, message):
                memories_extracted += 1
                if self.memories_repo.find_duplicate(person_id, candidate.content, candidate.memory_type) is None:
                    self.create_memory(candidate, person_id, actor="analyze")
                    created_memories += 1

        # Chunked conversation memories give retrieval larger blocks to match.
        chunks_created = 0
        chunks_total = 0
        for chunk in chunk_messages(messages, **(chunk_options or {})):
            if not chunk.content.strip():
                continue
            if self.memories_repo.find_duplicate(person_id, chunk.content, "CONVERSATION") is not None:
                chunks_total += 1
                continue
            self.memories_repo.create(
                person_id=person_id,
                content=chunk.content,
                memory_type="CONVERSATION",
                source_message_id=chunk.message_ids[0],
                importance=0.4,
                confidence=0.6,
                actor="analyze",
            )
            created_memories += 1
            chunks_created += 1
            chunks_total += 1

        self.session.commit()

        # Embed all active memories (idempotent thanks to checksums).
        embeddings_created = 0
        for memory in self.memories_repo.list_active(person_id):
            if embeddings.ensure_memory_embedding(self.session, memory):
                embeddings_created += 1

        total = self.memories_repo.count_active(person_id)
        logger.info(
            "Analyzed person=%s messages=%d memories_created=%d total=%d embeds=%d",
            person_id, len(messages), created_memories, total, embeddings_created,
        )
        return AnalyzeResult(
            person_id=person_id,
            messages_analyzed=len(messages),
            memories_created=created_memories,
            memories_total=total,
            embeddings_created=embeddings_created,
            profile_generated=profile is not None,
            style_generated=style is not None,
            memories_extracted=memories_extracted,
            chunks_created=chunks_created,
            chunks_total=chunks_total,
        )

    # ---- post-chat incremental update ----

    def update_from_messages(self, person, messages: Sequence) -> list[Memory]:
        """Persist any new, defensible information from a finished chat turn."""
        created: list[Memory] = []
        for message in messages:
            if message.is_duplicate or message.is_spam:
                continue
            is_user = not message.is_assistant and message.person_id is None
            for candidate in extract_candidates_from_message(person.name, message, is_user_message=is_user):
                if self.memories_repo.find_duplicate(person.id, candidate.content, candidate.memory_type) is None:
                    created.append(self.create_memory(candidate, person.id, actor="chat"))
        self.session.commit()
        if created:
            logger.info("Created %d new memories from conversation update.", len(created))
        return created

    # ---- current-conversation learning (Phase I) ----

    def _evaluate_user_turn(self, content: str) -> Optional[tuple]:
        """Return (kind, match) for the first learning pattern hit, else None."""
        if not content.strip() or len(content.strip()) < 6 or content.rstrip().endswith("?"):
            return None
        for regex, kind in _USER_LEARNING_PATTERNS:
            match = regex.search(content)
            if match:
                return (kind, match)
        return None

    def _render_learning(self, kind: str, match, me_person) -> tuple[str, str, list[str]]:
        """Turn a pattern match into (rendered text, memory_type, supersede terms)."""
        rendered = ""
        memory_type = ""
        terms: list[str] = []
        if kind == "CORRECTION":
            memory_type = "PREFERENCE"
            subject, old_value, new_value = (_sanitize_value(g) for g in match.groups())
            rendered = f"{me_person.name}'s {subject.casefold()} changed from {old_value} to {new_value}."
            terms = [old_value, subject]
        elif kind == "PREFERENCE":
            memory_type = "PREFERENCE"
            a, b = (_sanitize_value(match.group(1)), _sanitize_value(match.group(2)))
            rendered = f"{me_person.name} prefers {a} over {b}."
            terms = [b]  # the previously preferred value
        elif kind == "INTEREST":
            memory_type = "INTEREST"
            a, b = (_sanitize_value(match.group(1)), _sanitize_value(match.group(2)))
            rendered = f"{me_person.name}'s favorite {a.casefold()} is now {b}."
            terms = [a]
        else:  # OPINION
            memory_type = "OPINION"
            value = _sanitize_value(match.group(1))
            rendered = f"{me_person.name} now thinks {value.casefold()}."
            terms = []
        return rendered, memory_type, terms

    def plan_learning(self, me_person, message) -> Optional[LearningPlan]:
        """Derive a proposed memory from a chat turn without writing anything.

        Used by ``memory_mode="ask"``: the proposal is returned to the user and
        persisted only after explicit confirmation.
        """
        content = (message.content or "").strip()
        if (
            not content
            or message.is_duplicate
            or message.is_spam
            or message.is_assistant
            or content.rstrip().endswith("?")
            or len(content) < 6
        ):
            return None

        detected = self._evaluate_user_turn(content)
        if detected is None:
            return None

        kind, match = detected
        rendered, memory_type, _terms = self._render_learning(kind, match, me_person)
        if not rendered or len(rendered) > 240:
            return None

        # No point proposing a memory that already exists verbatim.
        if self.memories_repo.find_duplicate(me_person.id, rendered, memory_type) is not None:
            return None

        return LearningPlan(
            content=rendered,
            memory_type=memory_type,
            confidence=0.7,
            importance=0.6,
            message_id=message.id,
            person_id=me_person.id,
            person_name=me_person.name,
        )

    def learn_from_user_turn(self, me_person, message, embeddings: EmbeddingService) -> LearnedMemory:
        """Detect and persist a desirable memory from the user's own message.

        This is deliberately conservative: casual chat does not become memory.
        Only explicit statements about the user's own preferences / interests /
        changes ("I changed my favorite language from Java to Python", "I now
        prefer X over Y") produce a memory, and any previous conflicting value
        is preserved as a SUPERSEDED version instead of being overwritten.

        Returns a :class:`LearnedMemory` describing the outcome.
        """
        content = (message.content or "").strip()
        if not content or message.is_duplicate or message.is_spam or message.is_assistant:
            return LearnedMemory(LEARNED_NONE, None, "empty or filtered message")
        if content.rstrip().endswith("?") or len(content) < 6:
            return LearnedMemory(LEARNED_NONE, None, "not a memory candidate")

        detected = self._evaluate_user_turn(content)
        if detected is None:
            return LearnedMemory(LEARNED_NONE, None, "no candidate detected")

        kind, match = detected
        rendered, memory_type, terms = self._render_learning(kind, match, me_person)

        if not rendered or len(rendered) > 240:
            return LearnedMemory(LEARNED_NONE, None, "candidate too vague")

        # Already known verbatim -> nothing to store.
        existing = self.memories_repo.find_duplicate(me_person.id, rendered, memory_type)
        if existing is not None:
            return LearnedMemory(LEARNED_NONE, existing, "already known")

        # An active memory of the same kind that mentions a now-outdated value is
        # superseded: the old record (and its versions) is preserved as history.
        conflict = self._find_related_active(me_person.id, memory_type, terms)
        had_old_reference = bool(conflict is not None and any(
            t and t.casefold() in (conflict.content or "").casefold() for t in terms if t
        ))

        if conflict is not None:
            conflict_id = conflict.id
            self.memories_repo.set_status(conflict.id, "corrected", actor="correction")
            replacement = self.memories_repo.create(
                person_id=me_person.id,
                content=rendered,
                memory_type=memory_type,
                source_message_id=message.id,
                importance=0.6,
                confidence=0.75,
                note="learnt from live conversation (correction)",
                correction_of_id=conflict_id,
                actor="chat",
            )
            self.session.commit()
            embeddings.remove_memory_embedding(self.session, conflict_id)
            embeddings.ensure_memory_embedding(self.session, replacement)
            outcome = LEARNED_CORRECTION if had_old_reference else LEARNED_UPDATED
            return LearnedMemory(outcome, replacement, f"superseded memory {conflict_id}")

        memory = self.memories_repo.create(
            person_id=me_person.id,
            content=rendered,
            memory_type=memory_type,
            source_message_id=message.id,
            importance=0.6,
            confidence=0.7,
            note="learnt from live conversation",
            actor="chat",
        )
        self.session.commit()
        embeddings.ensure_memory_embedding(self.session, memory)
        return LearnedMemory(LEARNED_NEW, memory, "new memory")

    def _find_related_active(self, person_id: int, memory_type: str, terms: Sequence[str]) -> Optional[Memory]:
        """Best active memory of the same kind whose content mentions a term."""
        best: Optional[Memory] = None
        best_weight = 0
        for memory in self.memories_repo.list_active(person_id):
            if memory.memory_type != memory_type:
                continue
            low = (memory.content or "").casefold()
            for term in terms:
                if term and term.casefold() in low:
                    weight = 2 if term == terms[0] else 1
                    if weight > best_weight:
                        best, best_weight = memory, weight
        return best

    # ---- correction / edit / delete ----

    def correct(self, memory_id: int, correction: str, embeddings: EmbeddingService) -> Memory:
        memory = self.require_active(memory_id)
        correction_text = _sanitize_value(correction)
        if not correction_text:
            raise ImportValidationError("Correction text is empty.")

        # 1) Retire the old memory and remember why (a SUPERSEDED version is
        #    appended automatically by set_status -- history is never erased).
        self.memories_repo.set_status(memory.id, "corrected", actor="correction")
        memory.note = "user correction"

        # 2) Store the replacement memory (gets ACTIVE revision 1).
        replacement = self.memories_repo.create(
            person_id=memory.person_id,
            content=correction_text,
            memory_type=memory.memory_type,
            source_message_id=memory.source_message_id,
            importance=0.75,
            confidence=0.9,
            note="replaces corrected memory",
            correction_of_id=memory.id,
            actor="correction",
        )
        self.session.commit()

        # 3) Keep the vector store consistent: the old memory must never be
        #    retrieved as current fact again.
        embeddings.remove_memory_embedding(self.session, memory.id)
        embeddings.ensure_memory_embedding(self.session, replacement)
        logger.info("Corrected memory %s -> %s", memory.id, replacement.id)
        return replacement

    def delete(self, memory_id: int, embeddings: EmbeddingService) -> None:
        memory = self.require_active(memory_id)
        self.memories_repo.set_status(memory.id, "deleted", actor="delete")
        # Release the SQLite write lock before the vector store touches the DB.
        self.session.commit()
        embeddings.remove_memory_embedding(self.session, memory.id)
        self.session.commit()
        logger.info("Deleted memory %s", memory_id)

    def delete_conversation_memories(self, conversation_id: int, embeddings: EmbeddingService) -> tuple[int, int]:
        """Retire memories whose source message lives in a conversation.

        Deleting a conversation never silently drops unrelated memory records:
        only memories sourced from that conversation are handled, and only when
        nothing depends on them. Active memories are retired (``status="deleted"``)
        and their embedding removed; already-retired memories and memories that
        another memory supersedes (correction chains) are preserved.

        Returns ``(deleted, preserved)`` counts.
        """
        source_ids = [m.id for m in MessageRepository(self.session).list_by_conversation(conversation_id)]
        memories = self.memories_repo.list_by_source_messages(source_ids)
        deleted = 0
        preserved = 0
        for memory in memories:
            if memory.status != "active" or self.memories_repo.is_correction_reference(memory.id):
                preserved += 1
                continue
            self.delete(memory.id, embeddings)
            deleted += 1
        if memories:
            logger.info(
                "Conversation %s cleanup: %d remembered source messages, %d memory records retired, %d preserved",
                conversation_id,
                len(source_ids),
                deleted,
                preserved,
            )
        return deleted, preserved

    def edit(self, memory_id: int, new_content: str, embeddings: EmbeddingService) -> Memory:
        memory = self.require_active(memory_id)
        content = _sanitize_value(new_content)
        if not content:
            raise ImportValidationError("Edited content is empty.")
        memory.content = content
        self.session.commit()
        # Append a new ACTIVE version so the previous wording is preserved.
        MemoryVersionRepository(self.session).append(
            memory,
            status="ACTIVE",
            actor="edit",
            note=f"memory edited (was revision {MemoryVersionRepository(self.session).latest_revision(memory.id) - 1})",
        )
        self.session.commit()
        # Replace the old vector in place.
        embeddings.remove_memory_embedding(self.session, memory.id)
        embeddings.ensure_memory_embedding(self.session, memory)
        return memory

    def require_active(self, memory_id: int) -> Memory:
        memory = self.memories_repo.get(memory_id)
        if memory is None or memory.status != "active":
            raise NotFoundError("Memory not found or already retired.")
        return memory

    def archive(self, memory_id: int, embeddings: EmbeddingService) -> Memory:
        """Archive a memory: kept in history, no longer retrieved as current fact.

        Unlike ``delete``, an archived memory stays visible in the Memories
        page and can be restored with :meth:`restore`.
        """
        memory = self.require_active(memory_id)
        self.memories_repo.set_status(memory.id, "archived", actor="archive")
        self.session.commit()
        embeddings.remove_memory_embedding(self.session, memory_id)
        self.session.commit()
        logger.info("Archived memory %s", memory_id)
        memory = self.memories_repo.get(memory_id)
        return memory

    def restore(self, memory_id: int, embeddings: EmbeddingService) -> Memory:
        """Bring an archived memory back as active (vector restored)."""
        memory = self.memories_repo.get(memory_id)
        if memory is None or memory.status != "archived":
            raise NotFoundError("Memory not found or not archived.")
        self.memories_repo.set_status(memory.id, "active", actor="restore")
        self.session.commit()
        embeddings.ensure_memory_embedding(self.session, memory)
        self.session.commit()
        logger.info("Restored memory %s", memory_id)
        return memory