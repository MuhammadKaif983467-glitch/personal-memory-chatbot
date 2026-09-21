"""People, identity, profile and writing-style endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AppContext, get_context, get_db
from app.core.exceptions import NotFoundError
from app.database.repositories import MessageRepository, PersonRepository, PersonProfileRepository, WritingStyleRepository
from app.schemas.person import MergePeopleRequest, MergeResult, PersonOut, ProfileOut, StyleOut, to_person_out
from app.services.identity_service import IdentityService
from app.services.memory_service import MemoryService
from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("/people", response_model=list[PersonOut])
def list_people(db: Session = Depends(get_db)):
    people_repo = PersonRepository(db)
    message_repo = MessageRepository(db)
    return [
        to_person_out(person, message_repo.count_for_person(person.id))
        for person in people_repo.list_all()
    ]


@router.get("/people/{person_id}", response_model=PersonOut)
def get_person(person_id: int, db: Session = Depends(get_db)):
    person = PersonRepository(db).get(person_id)
    if person is None:
        raise NotFoundError("Person not found.")
    return to_person_out(person, MessageRepository(db).count_for_person(person_id))


@router.get("/people/{person_id}/profile", response_model=ProfileOut)
def get_profile(person_id: int, db: Session = Depends(get_db)):
    profile = PersonProfileRepository(db).get_for_person(person_id)
    if profile is None:
        raise NotFoundError("No profile yet - run analysis first.")
    return ProfileOut(
        person_id=person_id,
        interests=list(profile.interests or []),
        preferences=list(profile.preferences or []),
        important_facts=list(profile.important_facts or []),
        communication_habits=list(profile.communication_habits or []),
        topics=list(profile.topics or []),
        generated_at=profile.generated_at,
    )


@router.get("/people/{person_id}/style", response_model=StyleOut)
def get_style(person_id: int, db: Session = Depends(get_db)):
    style = WritingStyleRepository(db).get_for_person(person_id)
    if style is None:
        raise NotFoundError("No style analysis yet - run analysis first.")
    return StyleOut(
        person_id=person_id,
        common_words=list(style.common_words or []),
        common_phrases=list(style.common_phrases or []),
        emoji_usage=style.emoji_usage or {},
        sticker_usage=style.sticker_usage or {},
        average_message_length=style.average_message_length,
        average_words_per_message=style.average_words_per_message,
        language_mix=style.language_mix or {},
        tone=style.tone or "neutral",
        punctuation_style=style.punctuation_style or {},
        common_greetings=list(style.common_greetings or []),
        common_endings=list(style.common_endings or []),
        analyzed_at=style.analyzed_at,
    )


@router.post("/people/{person_id}/analyze")
def analyze_person(
    person_id: int,
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    """Run the full analysis: profile, style, memories, chunks, embeddings."""
    result = MemoryService(db).analyze_person(person_id, context.embeddings)
    context.metrics.inc("analysis_runs")
    return result


@router.post("/people/merge", response_model=MergeResult)
def merge_people(request: MergePeopleRequest, db: Session = Depends(get_db)):
    """Manual identity correction: merge two person records into one."""
    return IdentityService(db).merge_people(request.from_person_id, request.to_person_id)