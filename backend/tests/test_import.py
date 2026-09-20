"""Import / export API tests (JSON + CSV + consent + validation)."""

from __future__ import annotations

import json

import pytest

from tests.conftest import SAMPLE_JSON

CSV_TEXT = """sender,timestamp,content,message_type
Ali,2026-01-02 12:00:00,Hello! How are you?,text
Ali,2026-01-02 12:05:00,I prefer chai over coffee,text
Ali,2026-01-02 12:06:00,I like playing football,text
"""


def _sample_body(consent: bool = True):
    payload = json.loads(SAMPLE_JSON.read_text(encoding="utf-8"))
    payload["consent_confirmed"] = consent
    return payload


def test_import_valid_json(client):
    response = client.post("/import/json", json=_sample_body())
    assert response.status_code == 200, response.text
    report = response.json()

    assert report["total"] == 16
    assert report["imported"] == 12
    assert report["removed_empty"] == 1
    assert report["removed_system"] == 1
    assert report["removed_duplicates"] == 1
    assert report["spam_flagged"] == 1
    assert report["person_name"] == "Ali"

    people = client.get("/people").json()
    assert any(p["name"] == "Ali" for p in people)
    messages = client.get("/messages", params={"person_id": report["person_id"]}).json()
    assert len(messages) == 12
    # original content preserved for the whitespace test case
    original = [m for m in messages if "Hello" in m["original_content"]]
    assert original and (original[0]["content"] == original[0]["content"].strip())


def test_import_without_consent_rejected(client):
    response = client.post("/import/json", json=_sample_body(consent=False))
    assert response.status_code == 403
    assert "consent" in response.json()["detail"]["message"].lower()


def test_import_invalid_json_rejected(client):
    response = client.post("/import/json", content="this is not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_import_malformed_payload_rejected(client):
    body = _sample_body()
    body["messages"] = [{"timestamp": "2026-01-01", "content": "no sender"}]
    response = client.post("/import/json", json=body)
    assert response.status_code == 422


def test_import_missing_person_rejected(client):
    body = _sample_body()
    body["conversation"]["person"] = ""
    response = client.post("/import/json", json=body)
    assert response.status_code in (422,)


def test_import_csv(client):
    response = client.post(
        "/import/csv",
        files={"file": ("chat.csv", CSV_TEXT, "text/csv")},
        data={"person": "Ali", "consent_confirmed": "true", "title": "CSV chat"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["person_name"] == "Ali"
    assert report["total"] == 3
    assert report["imported"] == 3


def test_import_csv_missing_columns(client):
    bad_csv = "who,timestamp\nAli,2026-01-01\n"
    response = client.post(
        "/import/csv",
        files={"file": ("bad.csv", bad_csv, "text/csv")},
        data={"person": "Ali", "consent_confirmed": "true"},
    )
    assert response.status_code == 422
    assert "sender" in response.json()["detail"]["message"]


def test_import_csv_no_consent(client):
    response = client.post(
        "/import/csv",
        files={"file": ("chat.csv", CSV_TEXT, "text/csv")},
        data={"person": "Ali", "consent_confirmed": "false"},
    )
    assert response.status_code == 403


def test_exports(client, imported_alias):
    for endpoint in ("/export/messages", "/export/memories", "/export/people", "/export/conversations"):
        response = client.get(endpoint)
        assert response.status_code == 200
        body = response.json()
        assert "exported_at" in body
        assert body["count"] >= 1


def test_never_drops_messages_silently(client):
    body = _sample_body()
    # two rows are broken on purpose; they must be reported, not dropped silently
    body["messages"].append({"sender": "", "content": "bad row", "timestamp": "2026-01-01T00:00:00"})
    body["messages"].append({"sender": "Ali", "content": "q", "timestamp": "2026-01-01T00:00:00"})
    response = client.post("/import/json", json=body)
    assert response.status_code == 422
    assert "messages[16].sender" in response.json()["detail"]["details"][0]