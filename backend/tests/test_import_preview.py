"""Read-only import preview + TXT/ZIP import endpoints (Phase H).

Previewing must never write anything. Importing a TXT log or a ZIP archive is
the real path: it parses, validates, stores the conversation under a person,
and optionally analyses it (analysis is disabled in the test profile).
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ImportValidationError
from app.database.repositories import PersonRepository
from app.services.import_preview_service import ImportPreviewService

PREVIEW = ImportPreviewService()

TXT_LOG = "Kai: good morning\r\nZoe: hello!\n\nKai: how was the trip?\njust a freeform line\n"


@pytest.fixture
def zipped_txt() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("chat/export.txt", TXT_LOG)
    return buf.getvalue()


def test_preview_txt_is_read_only_and_counts(db):
    before_persons = PersonRepository(db).list_all(project_id=None)
    result = PREVIEW.preview_txt(TXT_LOG.encode("utf-8"), file_name="chat.txt", person="Zoe")

    assert result.source == "txt"
    assert result.person == "Zoe"
    assert result.valid_messages == 4
    assert result.empty == 0
    assert result.total_records == 4
    assert all(item.content for item in result.preview if not item.issue)
    # no writes happened during preview
    assert PersonRepository(db).list_all(project_id=None) == before_persons


def test_preview_csv_detects_malformed_rows():
    csv_text = "sender,timestamp,content\nKai,2024-01-01,hello\n,2024-01-01,no sender\nZoe,,second\n"
    result = PREVIEW.preview_csv(csv_text.encode("utf-8"), file_name="log.csv", person="Zoe")
    assert result.valid_messages == 2
    assert result.malformed == 1
    issues = [item.issue for item in result.preview if item.issue]
    assert "sender is empty" in issues


def test_preview_csv_rejects_missing_columns():
    with pytest.raises(ImportValidationError):
        PREVIEW.preview_csv(b"a,b\n1,2\n", file_name="bad.csv", person="Zoe")


def test_preview_zip_picks_text_member(zipped_txt):
    result = PREVIEW.preview_zip(zipped_txt, file_name="export.zip")
    assert result.source == "txt"
    assert result.valid_messages == 4
    assert "export" in result.person


def test_preview_zip_rejects_non_zip():
    with pytest.raises(ImportValidationError):
        PREVIEW.preview_zip(b"this is not a zip", file_name="not.zip", person="Zoe")


def test_preview_zip_rejects_oversized_member():
    buf = io.BytesIO()
    # a genuinely large member defeats the size guard
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("big.txt", b"\0" * (30 * 1024 * 1024))
    raw = buf.getvalue()
    with pytest.raises(ImportValidationError):
        PREVIEW.preview_zip(raw, file_name="big.zip", person="Zoe")


def test_txt_to_messages_assigns_person_to_freeform_lines():
    messages = PREVIEW.txt_to_messages(TXT_LOG.encode("utf-8"), person="Zoe")
    senders = {m.sender for m in messages}
    assert senders >= {"Kai", "Zoe"}
    assert any(m.content == "how was the trip?" for m in messages)


def test_zip_to_messages_parses_inner_txt(zipped_txt):
    messages = PREVIEW.zip_to_messages(zipped_txt, person="Zoe")
    assert len(messages) >= 4


def test_import_txt_endpoint_creates_conversation(app, db, client):
    response = client.post(
        "/import/txt",
        files={"file": ("chat.txt", TXT_LOG.encode("utf-8"), "text/plain")},
        data={"person": "Zoe", "consent_confirmed": "true", "title": "Trip talk"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["imported"] == 4
    assert report["person_name"] == "Zoe"
    assert report["messages_created"] == 4
    persons = client.get("/people").json()
    assert any(p["name"] == "Zoe" for p in persons)


def test_import_txt_requires_consent(tmp_path):
    from fastapi.testclient import TestClient

    from app.factory import create_app

    overrides = {
        "database_url": f"sqlite:///{(tmp_path / 'c.db').as_posix()}",
        "vector_db_path": str(tmp_path / "chroma"),
        "ai_provider": "mock",
        "vector_store": "simple",
        "openai_api_key": "",
        "openrouter_api_key": "",
        "consent_required": True,
    }
    app_ = create_app(overrides)
    client = TestClient(app_)
    try:
        response = client.post(
            "/import/txt",
            files={"file": ("chat.txt", TXT_LOG.encode("utf-8"), "text/plain")},
            data={"person": "Zoe", "consent_confirmed": "false"},
        )
        assert response.status_code == 403
    finally:
        client.close()
        app_.state.context.db.engine.dispose()


def test_import_zip_endpoint_end_to_end(app, db, client, zipped_txt):
    response = client.post(
        "/import/zip",
        files={"file": ("export.zip", zipped_txt, "application/zip")},
        data={"person": "Zoe", "consent_confirmed": "true"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["messages_created"] == 4
    assert report["person_name"] == "Zoe"


def test_preview_endpoint_is_read_only(app, db, client):
    before = client.get("/people").json()
    response = client.post(
        "/import/preview",
        files={"file": ("chat.txt", TXT_LOG.encode("utf-8"), "text/plain")},
        data={"person": "Zoe"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid_messages"] == 4
    assert client.get("/people").json() == before