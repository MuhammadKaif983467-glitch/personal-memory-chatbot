"""Conversation lifecycle + export tests (Phase 13).

Covers the conversation delete endpoint with its explicit memory handling, the
single-message endpoint used by the memory source inspector, and the export
surface (including the fixed /export/messages route).
"""

from __future__ import annotations


def _message_ids(client, conversation_id: int) -> list[int]:
    rows = client.get("/messages", params={"conversation_id": conversation_id, "limit": 1000}).json()
    return [m["id"] for m in rows]


def _memories_sourced_here(client, person_id: int, message_ids: list[int]) -> list[dict]:
    rows = client.get(
        "/memories", params={"person_id": person_id, "status": "all", "limit": 500}
    ).json()
    return [m for m in rows if m["source_message_id"] in set(message_ids)]


def test_get_single_message(client, imported_alias):
    rows = client.get(
        "/messages", params={"conversation_id": imported_alias["conversation_id"]}
    ).json()
    assert rows
    single = client.get(f"/messages/{rows[0]['id']}")
    assert single.status_code == 200
    body = single.json()
    assert body["id"] == rows[0]["id"]
    assert body["conversation_id"] == imported_alias["conversation_id"]
    assert isinstance(body["content"], str)


def test_get_single_message_missing_returns_404(client):
    response = client.get("/messages/999999")
    assert response.status_code == 404


def test_delete_conversation_removes_messages_and_derived_memories(client, imported_alias):
    person_id = imported_alias["person_id"]
    conversation_id = imported_alias["conversation_id"]

    message_ids = _message_ids(client, conversation_id)
    assert message_ids, "imported conversation should contain messages"
    sourced_here = _memories_sourced_here(client, person_id, message_ids)
    assert sourced_here, "analyzed person should have memories traced into this conversation"

    response = client.delete(f"/conversations/{conversation_id}")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["conversation_id"] == conversation_id
    assert body["messages_deleted"] == len(message_ids)
    # every memory traced to this conversation was handled explicitly
    assert body["memories_deleted"] + body["memories_preserved"] == len(sourced_here)

    # conversation and its messages are gone
    assert client.get(f"/conversations/{conversation_id}").status_code == 404
    assert _message_ids(client, conversation_id) == []

    # no live memory still points into the deleted conversation
    remaining = _memories_sourced_here(client, person_id, message_ids)
    assert [m for m in remaining if m["status"] != "deleted"] == []
    assert remaining, "retired records are kept as an audit trail"


def test_delete_conversation_missing_returns_404(client):
    assert client.delete("/conversations/999999").status_code == 404


def test_export_messages_is_a_flat_message_list(client, imported_alias):
    response = client.get("/export/messages")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data, "route must export messages, not conversations"
    assert "conversations" not in data
    assert data["count"] == len(data["messages"])
    if data["messages"]:
        first = data["messages"][0]
        assert "conversation_id" in first
        assert isinstance(first["content"], str)
        assert isinstance(first["original_content"], str)
        assert "timestamp" in first


def test_export_conversations_keeps_nesting(client, imported_alias):
    data = client.get("/export/conversations").json()
    assert data["count"] == len(data["conversations"])
    assert all(isinstance(c["messages"], list) for c in data["conversations"])