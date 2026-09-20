"""Full pipeline integration test using the offline mock provider.

Covers: import -> analysis -> retrieval -> chat -> disclosure -> memory
correction -> re-retrieval. No network and no API key required.
"""

from __future__ import annotations


def test_full_pipeline(client, imported_alias):
    person_id = imported_alias["person_id"]

    # 1. Memories were created during analysis.
    memories = client.get("/memories", params={"person_id": person_id}).json()
    assert memories

    # 2. Ask the chatbot a history question.
    chat = client.post(
        "/chat",
        json={"message": "What does Ali like to drink?", "person_id": person_id, "debug": True},
    )
    assert chat.status_code == 200
    reply = chat.json()
    assert reply["reply"]
    assert reply["memory_indicator"] in (None, "Based on an earlier conversation with this person...")

    # 3. Sources show which memories influenced the reply (setting enabled).
    sources = reply["sources"]
    assert sources

    # 4. Debug exposes retrieved memories with closeness scores.
    debug = reply["debug"]
    assert debug is not None
    assert len(debug["retrieved"]) > 0
    assert all(r["rank"] >= 1 for r in debug["retrieved"])

    # 5. User corrects a wrong memory ("I don't like tea" style repair).
    chai_memory = next(
        m for m in client.get("/memories", params={"person_id": person_id}).json()
        if "chai" in m["content"]
    )
    corrected = client.post(
        f"/memories/{chai_memory['id']}/correct",
        json={"correction": "Ali prefers coffee, not chai"},
    ).json()

    # 6. The corrected value is now the current memory; old one retired.
    active = client.get("/memories", params={"person_id": person_id}).json()
    assert any(m["content"] == "Ali prefers coffee, not chai" for m in active)
    assert all(m["id"] != chai_memory["id"] for m in active)

    # 7. Embeddings stay consistent after the repair.
    health = client.get("/health").json()
    assert health["vector_count"] >= 1

    # 8. Chat again - corrected memory is part of context but the bot still
    #    works even with an offline (mock) provider.
    again = client.post(
        "/chat", json={"message": "remind me about Ali's drink preference", "person_id": person_id}
    )
    assert again.status_code == 200
    assert again.json()["reply"]