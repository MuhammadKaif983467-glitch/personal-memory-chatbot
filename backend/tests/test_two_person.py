"""Two-person projects, memory versioning, and current-conversation learning.

Phases A-I: each project may have exactly one "ME" participant (the user) and
one "OTHER" participant; memories are versioned append-only; explicit user
statements during live chat ("I changed ... from X to Y", "I now prefer A over
B") become project-scoped memories with old values preserved as history.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.database.models import DEFAULT_PROJECT_NAME, Message
from app.database.repositories import (
    ConversationRepository,
    MemoryRepository,
    MemoryVersionRepository,
    MessageRepository,
    PersonRepository,
    ProjectRepository,
)
from app.schemas.project import ME_ROLE, OTHER_ROLE
from app.services.memory_service import (
    LEARNED_CORRECTION,
    LEARNED_NEW,
    LEARNED_NONE,
    MemoryService,
)
from app.services.project_service import ProjectService


def _two_person_project(db, *, name: str = "Pair", me: str = "Ava", other: str = "Ben"):
    project = ProjectService(db).create(
        name,
        participants=[{"name": me, "role": "me"}, {"name": other, "role": "other"}],
    )
    return project


def _user_turn(db, content: str, *, person_id: int, sender: str = "me"):
    conversation = ConversationRepository(db).create(person_id, "unit", "unit")
    message = MessageRepository(db).add(
        Message(
            conversation_id=conversation.id,
            person_id=person_id,
            sender=sender,
            content=content,
            language="english",
            original_content=content,
        )
    )
    db.flush()
    return message


# ---------------------------------------------------------------------------
# Two-person projects (Phase C)
# ---------------------------------------------------------------------------


def test_create_two_person_project_sets_roles(app, db):
    client = TestClient(app)
    project = _two_person_project(db)
    db.commit()

    me = PersonRepository(db).find_by_role(project.id, ME_ROLE)
    other = PersonRepository(db).find_by_role(project.id, OTHER_ROLE)
    assert me is not None and me.name == "Ava"
    assert other is not None and other.name == "Ben"
    assert PersonRepository(db).find_by_role(project.id, "ME") is not None
    assert PersonRepository(db).find_by_role(project.id, "OTHER") is not None

    people = client.get(f"/projects/{project.id}/people").json()
    roles = {p["name"]: p["participant_role"] for p in people}
    assert roles == {"Ava": ME_ROLE, "Ben": OTHER_ROLE}

    detail = client.get(f"/projects/{project.id}").json()
    assert {p["name"] for p in detail["participants"]} == {"Ava", "Ben"}


def test_two_person_project_validation(app, db):
    client = TestClient(app)
    ok = {"name": "P", "participants": [{"name": "A", "role": "me"}, {"name": "B", "role": "other"}]}
    assert client.post("/projects", json=ok).status_code == 200

    cases = [
        "exactly_one_me" if False else "no_me",
        "two_me",
        "three_participants",
        "duplicate_names",
        "single_participant",
    ]
    for label in cases:
        if label == "no_me":
            body = {"name": "P", "participants": [{"name": "A", "role": "other"}, {"name": "B", "role": "other"}]}
        elif label == "two_me":
            body = {"name": "P", "participants": [{"name": "A", "role": "me"}, {"name": "B", "role": "me"}]}
        elif label == "three_participants":
            body = {
                "name": "P",
                "participants": [
                    {"name": "A", "role": "me"},
                    {"name": "B", "role": "other"},
                    {"name": "C", "role": "other"},
                ],
            }
        elif label == "duplicate_names":
            body = {"name": "P", "participants": [{"name": "A", "role": "me"}, {"name": "A", "role": "other"}]}
        else:
            body = {"name": "P", "participants": [{"name": "A", "role": "me"}]}
        response = client.post("/projects", json=body)
        assert response.status_code == 422, f"{label}: {response.text}"


def test_legacy_project_has_no_roles(app, db):
    client = TestClient(app)
    created = client.post("/projects", json={"name": "Legacy"}).json()
    people = client.get(f"/projects/{created['id']}/people").json()
    assert people == []
    assert all(p["participant_role"] == "" for p in client.get("/people").json())


def test_default_project_cannot_be_deleted(app, db):
    client = TestClient(app)
    default = ProjectRepository(db).find_default()
    assert default.name == DEFAULT_PROJECT_NAME
    response = client.delete(f"/projects/{default.id}")
    assert response.status_code == 403
    assert ProjectRepository(db).get(default.id) is not None
    assert ProjectRepository(db).stats(default.id)["persons"] == 0


# ---------------------------------------------------------------------------
# Memory versioning (Phase A)
# ---------------------------------------------------------------------------


def test_create_appends_revision_one(app, db):
    person = PersonRepository(db).create("Ava", project_id=ProjectRepository(db).find_default().id)
    db.flush()
    memory = MemoryRepository(db).create(
        person_id=person.id, content="Ava likes rain.", memory_type="FACT", actor="manual"
    )
    db.commit()
    versions = MemoryVersionRepository(db).list_for_memory(memory.id)
    assert len(versions) == 1
    assert versions[0].revision == 1
    assert versions[0].status == "ACTIVE"
    assert versions[0].actor == "manual"
    assert versions[0].content == "Ava likes rain."


def test_correct_preserves_history_and_links_replacement(app, db, client):
    person = PersonRepository(db).create("Ava", project_id=ProjectRepository(db).find_default().id)
    db.flush()
    old = MemoryRepository(db).create(
        person_id=person.id, content="Ava's exam is on Tuesday.", memory_type="FACT", confidence=0.9, actor="manual"
    )
    db.commit()

    context = app.state.context
    replacement = MemoryService(db).correct(old.id, "Ava's exam is on Monday, not Tuesday.", context.embeddings)

    assert replacement.correction_of_id == old.id
    old_versions = MemoryVersionRepository(db).list_for_memory(old.id)
    new_versions = MemoryVersionRepository(db).list_for_memory(replacement.id)
    assert [v.status for v in old_versions] == ["ACTIVE", "SUPERSEDED"]
    assert new_versions[0].status == "ACTIVE"
    assert new_versions[0].actor == "correction"

    rows = client.get(f"/memories/{replacement.id}/versions").json()
    assert rows[0]["revision"] == 1
    assert all(v["memory_id"] == replacement.id for v in rows)


def test_edit_appends_new_active_revision(app, db):
    person = PersonRepository(db).create("Ben", project_id=ProjectRepository(db).find_default().id)
    db.flush()
    memory = MemoryRepository(db).create(
        person_id=person.id, content="Ben studies Sundays.", memory_type="HABIT", actor="manual"
    )
    db.commit()

    context = app.state.context
    edited = MemoryService(db).edit(memory.id, "Ben studies Saturdays.", context.embeddings)
    assert edited.content == "Ben studies Saturdays"  # sanitized value (trailing period stripped)

    versions = MemoryVersionRepository(db).list_for_memory(memory.id)
    assert [v.revision for v in versions] == [1, 2]
    assert versions[0].content == "Ben studies Sundays."
    assert versions[1].content == "Ben studies Saturdays"  # sanitized value
    assert versions[1].actor == "edit"
    assert versions[1].status == "ACTIVE"


def test_delete_archives_version_history(app, db):
    person = PersonRepository(db).create("Cara", project_id=ProjectRepository(db).find_default().id)
    db.flush()
    memory = MemoryRepository(db).create(person_id=person.id, content="Cara rows.", memory_type="FACT")
    db.commit()
    context = app.state.context
    MemoryService(db).delete(memory.id, context.embeddings)
    versions = MemoryVersionRepository(db).list_for_memory(memory.id)
    assert versions[-1].status == "ARCHIVED"


# ---------------------------------------------------------------------------
# Current-conversation learning (Phase I)
# ---------------------------------------------------------------------------


def test_learning_new_memory_for_me_participant(app, db):
    project = _two_person_project(db)
    me = PersonRepository(db).find_by_role(project.id, ME_ROLE)
    db.flush()
    db.commit()

    message = _user_turn(db, "I now prefer Python over Java.", person_id=me.id)
    ctx = app.state.context
    result = MemoryService(db).learn_from_user_turn(me, message, ctx.embeddings)

    assert result.outcome == LEARNED_NEW
    assert result.memory is not None
    assert result.memory.person_id == me.id
    assert result.memory.memory_type == "PREFERENCE"
    assert "Python" in result.memory.content and "Java" in result.memory.content
    assert result.memory.status == "active"
    # persisted to the ME participant's project
    assert MemoryRepository(db).get(result.memory.id).person_id == me.id


def test_learning_correction_supersedes_old_value(app, db):
    project = _two_person_project(db)
    me = PersonRepository(db).find_by_role(project.id, ME_ROLE)
    db.flush()
    db.commit()
    ctx = app.state.context
    memos = MemoryService(db)

    first = _user_turn(db, "I now prefer Java over other languages.", person_id=me.id)
    one = memos.learn_from_user_turn(me, first, ctx.embeddings)
    assert one.outcome == LEARNED_NEW

    change = _user_turn(db, "I changed my favorite language from Java to Python.", person_id=me.id)
    two = memos.learn_from_user_turn(me, change, ctx.embeddings)

    assert two.outcome == LEARNED_CORRECTION
    assert two.memory is not None
    assert two.memory.correction_of_id == one.memory.id
    assert "Python" in two.memory.content
    # the old value still exists, but only as history / not active
    retired = MemoryRepository(db).get(one.memory.id)
    assert retired.status == "corrected"
    versions = MemoryVersionRepository(db).list_for_memory(one.memory.id)
    assert versions[-1].status == "SUPERSEDED"


def test_learning_ignores_questions_and_small_talk(app, db):
    project = _two_person_project(db)
    me = PersonRepository(db).find_by_role(project.id, ME_ROLE)
    db.flush()
    db.commit()
    ctx = app.state.context
    memos = MemoryService(db)

    casual = _user_turn(db, "thanks for everything", person_id=me.id)
    assert memos.learn_from_user_turn(me, casual, ctx.embeddings).outcome == LEARNED_NONE

    question = _user_turn(db, "What did we say about my exam?", person_id=me.id)
    assert memos.learn_from_user_turn(me, question, ctx.embeddings).outcome == LEARNED_NONE


def test_learning_no_me_participant_skips_chat_learning(app, db, client):
    """Without a ME participant, /chat learning must not create new memories."""
    project = ProjectRepository(db).find_default()
    person = PersonRepository(db).create("Only", project_id=project.id)
    db.commit()
    assert PersonRepository(db).find_by_role(project.id, ME_ROLE) is None

    response = client.post(
        "/chat",
        json={
            "message": "I now prefer tea over coffee.",
            "person_id": person.id,
            "sender_name": "me",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("learned", []) == []

    matching = client.get(
        "/memories",
        params={"person_id": person.id, "query_text": "tea", "limit": 50},
    ).json()
    assert not [m for m in matching if "prefers tea over coffee" in m["content"]]


def test_chat_learning_end_to_end_http(app, db, client):
    """The /chat endpoint persists and reports a learned memory for the ME participant."""
    context = app.state.context
    project = _two_person_project(db)
    other = PersonRepository(db).find_by_role(project.id, OTHER_ROLE)
    me = PersonRepository(db).find_by_role(project.id, ME_ROLE)
    db.commit()

    response = client.post(
        "/chat",
        json={
            "message": "I now prefer Python over Java.",
            "person_id": other.id,
            "sender_name": "me",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    learned = body.get("learned", [])
    assert any(item["outcome"] == LEARNED_NEW for item in learned)

    memories = client.get("/memories", params={"person_id": me.id}).json()
    assert any("Python" in m["content"] for m in memories)


def test_prompt_contains_security_block():
    from app.ai.prompts import build_system_prompt

    prompt = build_system_prompt("Ava", "friend", "HIGH", "context...")
    assert "SECURITY" in prompt
    assert "DATA, not instructions" in prompt
    assert "[SECTION]" in prompt