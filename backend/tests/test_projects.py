"""Tests for the multi-project (workspace) model.

Projects isolate people / conversations / memories / vectors. The existing
regression data is backfilled into the default "Demo / Regression" project, so
all prior behaviour (including the sample-chat fixtures) keeps working while
new projects can be created, listed, queried and deleted independently.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.database.models import DEFAULT_PROJECT_NAME, Message
from app.database.repositories import (
    ConversationRepository,
    MemoryRepository,
    MessageRepository,
    PersonRepository,
    ProjectRepository,
)
from app.services.retrieval_service import RetrievalService


def _seed_project_data(db, project_id: int, person_name: str, content: str, *, messages: int = 1):
    """Create a person + conversation + a couple of messages + a memory inside one project."""
    person = PersonRepository(db).create(person_name, project_id=project_id)
    conversation = ConversationRepository(db).create(
        person.id, f"{person_name} chat", "unit", project_id=project_id
    )
    for i in range(messages):
        MessageRepository(db).add(
            Message(conversation_id=conversation.id, sender="me" if i % 2 == 0 else "them",
                    content=f"line {i} from {person_name}")
        )
    memory = MemoryRepository(db).create(
        person_id=person.id,
        content=content,
        memory_type="PREFERENCE",
        project_id=project_id,
    )
    db.flush()
    return memory.id, person.id, conversation.id


def test_default_project_bootstrap(app, db):
    projects = ProjectRepository(db).list_all()
    assert len(projects) == 1
    assert projects[0].name == DEFAULT_PROJECT_NAME
    assert ProjectRepository(db).stats(projects[0].id)["messages"] == 0


def test_create_and_list_projects(client):
    created = client.post("/projects", json={"name": "Travel plans"}).json()
    assert created["name"] == "Travel plans"
    assert created["stats"] == {
        "persons": 0,
        "conversations": 0,
        "messages": 0,
        "memories": 0,
        "active_memories": 0,
        "embeddings": 0,
    }
    names = {p["name"] for p in client.get("/projects").json()}
    assert DEFAULT_PROJECT_NAME in names
    assert "Travel plans" in names


def test_get_project_not_found(client):
    assert client.get("/projects/99999").status_code == 404
    assert client.delete("/projects/99999").status_code == 404


def test_update_project_name(client):
    created = client.post("/projects", json={"name": "Old Name"}).json()
    pid = created["id"]
    assert created["name"] == "Old Name"

    resp = client.patch(f"/projects/{pid}", json={"name": "New Name"})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "New Name"
    assert updated["id"] == pid

    fetched = client.get(f"/projects/{pid}").json()
    assert fetched["name"] == "New Name"


def test_update_project_name_validation(client):
    created = client.post("/projects", json={"name": "Valid"}).json()
    pid = created["id"]

    resp = client.patch(f"/projects/{pid}", json={"name": ""})
    assert resp.status_code == 422

    resp = client.patch(f"/projects/{pid}", json={"name": "   "})
    assert resp.status_code == 422


def test_update_project_not_found(client):
    resp = client.patch("/projects/99999", json={"name": "X"})
    assert resp.status_code == 404


def test_project_isolation_between_two_projects(app, db):
    client = TestClient(app)
    default_id = ProjectRepository(db).find_default().id
    pid_b = client.post("/projects", json={"name": "Solo study"}).json()["id"]

    _seed_project_data(db, default_id, "Ali", "Ali prefers hiking.")
    _seed_project_data(db, pid_b, "Zoe", "Zoe likes snowboarding.")
    db.commit()

    default_people = [p.name for p in PersonRepository(db).list_all(project_id=default_id)]
    project_b_people = [p.name for p in PersonRepository(db).list_all(project_id=pid_b)]
    assert "Zoe" in project_b_people
    assert "Zoe" not in default_people
    assert "Ali" not in project_b_people

    default_memories = [m.content for m in MemoryRepository(db).list_active(project_id=default_id)]
    project_b_memories = [m.content for m in MemoryRepository(db).list_active(project_id=pid_b)]
    assert "Zoe likes snowboarding." in project_b_memories
    assert "Zoe likes snowboarding." not in default_memories
    assert "Ali prefers hiking." not in project_b_memories


def test_nested_project_endpoints(app, db):
    client = TestClient(app)
    default_id = ProjectRepository(db).find_default().id
    pid_b = client.post("/projects", json={"name": "Isolated"}).json()["id"]
    _, person_b, conv_b = _seed_project_data(db, pid_b, "Noah", "Noah studies Arabic.")
    db.commit()

    people = client.get(f"/projects/{pid_b}/people").json()
    assert [p["name"] for p in people] == ["Noah"]

    conversations = client.get(f"/projects/{pid_b}/conversations").json()
    assert [c["id"] for c in conversations] == [conv_b]

    memories = client.get(f"/projects/{pid_b}/memories").json()
    assert [m["content"] for m in memories] == ["Noah studies Arabic."]

    default_conversations = client.get(f"/projects/{default_id}/conversations").json()
    default_memories = client.get(f"/projects/{default_id}/memories").json()
    assert all(c["id"] != conv_b for c in default_conversations)
    assert all(m["person_id"] != person_b for m in default_memories)

    # missing project -> 404 on nested routes as well
    assert client.get("/projects/424242/people").status_code == 404
    assert client.get("/projects/424242/memories").status_code == 404


def test_project_memories_status_filter(app, db):
    client = TestClient(app)
    pid_b = client.post("/projects", json={"name": "History"}).json()["id"]
    memory_id, _, _ = _seed_project_data(db, pid_b, "Mina", "Mina runs mornings.")
    db.commit()
    MemoryRepository(db).set_status(memory_id, "corrected")
    db.commit()

    active = client.get(f"/projects/{pid_b}/memories?status=active").json()
    assert active == []
    all_rows = client.get(f"/projects/{pid_b}/memories?status=all").json()
    assert len(all_rows) == 1
    assert all_rows[0]["status"] == "corrected"


def test_delete_project_cascade(app, db):
    client = TestClient(app)
    default_id = ProjectRepository(db).find_default().id
    # default project holds the "existing world" data that must survive the delete
    _seed_project_data(db, default_id, "Ali", "Ali prefers hiking.", messages=3)
    db.commit()
    default_before = ProjectRepository(db).stats(default_id)
    assert default_before["messages"] == 3

    pid_b = client.post("/projects", json={"name": "Throwaway"}).json()["id"]
    _, person_b, _ = _seed_project_data(db, pid_b, "Rye", "Rye plays violin.")
    MemoryRepository(db).create(
        person_id=person_b,
        content="Rye history.",
        memory_type="FACT",
        project_id=pid_b,
    )
    db.commit()

    response = client.delete(f"/projects/{pid_b}")
    assert response.status_code == 200
    result = response.json()
    assert result["deleted_persons"] == 1
    assert result["deleted_conversations"] == 1
    assert result["deleted_memories"] == 2

    assert client.get(f"/projects/{pid_b}").status_code == 404
    assert ProjectRepository(db).stats(default_id) == default_before
    assert "Ali" in {p["name"] for p in client.get("/people").json()}


def test_retrieval_is_isolated_by_project(app, db):
    """Two projects with identical memory text never leak across retrieval."""
    context = app.state.context
    default_id = ProjectRepository(db).find_default().id
    pid_b = ProjectRepository(db).create("Second", user_id="local").id
    db.flush()

    shared = "The shared topic: hiking in the mountains."
    _, ali_person, _ = _seed_project_data(db, default_id, "Ali", shared)
    _, sara_person, _ = _seed_project_data(db, pid_b, "Sara", shared)
    db.commit()

    context.embeddings.ensure_memory_embeddings(db, list(MemoryRepository(db).list_active()), chunk_size=2)

    retrieval = RetrievalService(context.embeddings, context.vector_store)
    hits_default = retrieval.retrieve(db, shared, project_id=default_id, limit=3)
    hits_b = retrieval.retrieve(db, shared, project_id=pid_b, limit=3)

    assert hits_default and hits_b
    assert all(h.memory.project_id == default_id for h in hits_default)
    assert all(h.memory.project_id == pid_b for h in hits_b)
    assert {h.memory.person_id for h in hits_default} == {ali_person}
    assert {h.memory.person_id for h in hits_b} == {sara_person}


def test_vector_metadata_carries_project_id(app, db):
    context = app.state.context
    default_id = ProjectRepository(db).find_default().id
    memory_id, _, _ = _seed_project_data(db, default_id, "Tom", "Tom reads novels.")
    db.commit()
    context.embeddings.ensure_memory_embedding(db, MemoryRepository(db).get(memory_id))

    embedding = context.embeddings.embed_texts(["novels reading"])[0]
    hits = context.vector_store.query(embedding, n_results=10)
    matching = [h for h in hits if h.memory_id == memory_id]
    assert matching
    assert matching[0].metadata.get("project_id") == str(default_id)