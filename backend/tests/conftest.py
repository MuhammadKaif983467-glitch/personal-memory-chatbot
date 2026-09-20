"""Shared pytest fixtures.

Every test runs against an isolated temporary SQLite database with the
deterministic MockProvider and the local SimpleVectorStore - no network, no
API keys.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.schemas.import_export import ImportPayload

SAMPLE_JSON = Path(__file__).parent.parent / "app" / "sample_data" / "sample_chat.json"

# Provider secrets that must never be consumed by a test. Autouse so any test
# that constructs Settings(...) directly stays hermetic even though
# pydantic-settings would otherwise read a developer's real .env (env vars win
# over the dotenv file, and empty values are normalized to unset by validators).
# Voice/TTS model vars are pinned too (not secrets, but they make health/settings
# output deterministic regardless of the developer's .env).
_SECRET_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_KEY_1",
    "OPENROUTER_API_KEY_2",
    "VOICE_STT_API_KEY",
    "VOICE_TTS_API_KEY",
    "OPENROUTER_TTS_MODEL",
    "VOICE_STT_PROVIDER",
    "VOICE_TTS_PROVIDER",
)


@pytest.fixture(autouse=True)
def _hermetic_provider_env(monkeypatch):
    for var in _SECRET_ENV_VARS:
        monkeypatch.setenv(var, "")

TEST_OVERRIDES_TEMPLATE = {
    "ai_provider": "mock",
    "vector_store": "simple",
    # Tests must never read a developer's real .env: pin empty keys so the
    # suite stays hermetic even when real API keys are configured (including
    # the split-role OPENROUTER_API_KEY_1 / _2 variables).
    "openai_api_key": "",
    "openrouter_api_key": "",
    "openrouter_api_key_1": "",
    "openrouter_api_key_2": "",
    "analyze_on_import": False,
    "consent_required": True,
    "show_memory_sources": True,
}


def _overrides(tmp_path: Path) -> dict:
    return {
        **TEST_OVERRIDES_TEMPLATE,
        "database_url": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "vector_db_path": str(tmp_path / "chroma"),
        "imports_dir": str(tmp_path / "imports"),
        "processed_dir": str(tmp_path / "processed"),
        "exports_dir": str(tmp_path / "exports"),
        "context_budget_chars": 4000,
    }


@pytest.fixture()
def app(tmp_path):
    return create_app(_overrides(tmp_path))


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def db(app):
    context = app.state.context
    session = context.db.session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def imported_alias(client, db):
    """Import the built-in sample chat so tests start with a known person."""
    payload = json.loads(SAMPLE_JSON.read_text(encoding="utf-8"))
    payload["consent_confirmed"] = True
    response = client.post("/import/json", json=payload)
    assert response.status_code == 200, response.text
    report = response.json()
    person = next(
        (p for p in client.get("/people").json() if p["name"] == "Ali"),
        None,
    )
    assert person is not None
    # analyze on import is disabled in tests, run it explicitly
    assert client.post(f"/people/{person['id']}/analyze").status_code == 200
    return {"person_id": person["id"], "conversation_id": report["conversation_id"]}


def sample_payload(**overrides) -> ImportPayload:
    payload = json.loads(SAMPLE_JSON.read_text(encoding="utf-8"))
    payload.update(overrides)
    return ImportPayload.model_validate(payload)