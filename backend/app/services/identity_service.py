"""Identity service.

Groups messages to people. Matching is conservative:
  - exact name match first
  - normalized name match second (case/diacritics/whitespace-insensitive)
  - a new person record is only created when explicitly allowed
The merge endpoint exists for manual correction; automatic merges are never
based on weak evidence.
"""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.database.models import Conversation, Memory, Message, Person, PersonProfile, WritingStyle
from app.database.repositories import (
    ConversationRepository,
    MemoryRepository,
    MessageRepository,
    PersonProfileRepository,
    PersonRepository,
)
from app.schemas.person import MergeResult
from app.services.cleaning_service import normalize_sender

IDENTITY_PATTERNS = {
    # strong evidence for a same person is a matching sender name
    "exact": lambda a, b: (a or "").strip().casefold() == (b or "").strip().casefold(),
}


class IdentityService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.people = PersonRepository(session)

    def find_person(self, raw_name: str):
        """Locate an existing person record for a sender name, if any."""
        name = normalize_sender(raw_name) or (raw_name or "").strip()
        if not name:
            return None
        exact = self.people.get_by_name(name)
        if exact:
            return exact
        return self.people.get_by_normalized_name(name.casefold())

    def find_or_create_person(self, raw_name: str, relationship: str = "unknown") -> Person:
        """Identify the person or create a fresh record (import path only)."""
        existing = self.find_person(raw_name)
        if existing:
            return existing
        name = normalize_sender(raw_name) or (raw_name or "").strip() or "Unknown"
        return self.people.create(name, relationship)

    def merge_people(self, from_person_id: int, to_person_id: int) -> MergeResult:
        if from_person_id == to_person_id:
            raise NotFoundError("The two person ids must be different.")
        source = self.people.get(from_person_id)
        target = self.people.get(to_person_id)
        if source is None or target is None:
            raise NotFoundError("One of the persons was not found.")

        moved_messages = MessageRepository(self.session).reassign(from_person_id, to_person_id)
        moved_conversations = ConversationRepository(self.session).reassign(from_person_id, to_person_id)
        MemoryRepository(self.session).reassign(from_person_id, to_person_id)

        # Profiles / styles have a unique person_id: move the source record
        # only when the target does not already have one.
        moved_profile = False
        if PersonProfileRepository(self.session).get_for_person(to_person_id) is None:
            self.session.execute(
                update(PersonProfile).where(PersonProfile.person_id == from_person_id).values(person_id=to_person_id)
            )
            moved_profile = True
        if (
            self.session.query(WritingStyle).filter(WritingStyle.person_id == to_person_id).first() is None
        ):
            self.session.execute(
                update(WritingStyle).where(WritingStyle.person_id == from_person_id).values(person_id=to_person_id)
            )

        # Keep the merged names resolvable so future imports/messages that use
        # the old spelling still find the surviving record.
        for alias in [source.name, *(source.aliases or [])]:
            self.people.add_alias(target, alias)

        self.people.delete(source)
        self.session.flush()
        return MergeResult(
            from_person_id=from_person_id,
            to_person_id=to_person_id,
            moved_messages=moved_messages,
            moved_conversations=moved_conversations,
            merged_profiles=moved_profile,
        )