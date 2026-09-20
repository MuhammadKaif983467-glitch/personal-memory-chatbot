"""Live acceptance verifier (run against the real local .env / database).

Deliberately prints NO credential material: only booleans, model names, lengths
and masked snippets. Verifies in order:

  1. Configuration booleans (chat/embedding/TTS configured, split keys in use).
  2. /health and /settings are secret-free and report the new split-role fields.
  3. Live chat auth (uses OPENROUTER_API_KEY_2 chain) and live embedding auth
     (uses OPENROUTER_API_KEY_1 chain).
  4. Two-person project E2E on a temporary project: create -> two participants
     with ME/OTHER roles -> chat (real AI reply) -> current-conversation
     learning NEW -> learning CORRECTION (old superseded, new active) ->
     retrieval finds the learned memory -> cross-project isolation check ->
     delete ONLY the temporary project and prove the regression baseline is
     restored exactly.

Run from backend:  .venv\\Scripts\\python.exe scripts\\live_acceptance.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.database.models import Memory  # noqa: E402
from app.database.repositories import (  # noqa: E402
    MemoryRepository,
    MemoryVersionRepository,
    PersonRepository,
    ProjectRepository,
    StatsRepository,
)
from app.factory import create_app  # noqa: E402
from app.schemas.chat import ChatRequest  # noqa: E402
from app.schemas.project import ME_ROLE, OTHER_ROLE  # noqa: E402
from app.services.memory_service import LEARNED_CORRECTION, LEARNED_NEW  # noqa: E402
from app.services.project_service import ProjectService  # noqa: E402

KEY_PATTERN = re.compile(r"sk-(or|proj|sk)-[A-Za-z0-9]{6,}")
RESULTS: dict[str, str] = {}


def _ok(name: str) -> None:
    RESULTS[name] = "PASS"
    print(f"[PASS] {name}")


def _fail(name: str, detail: str) -> None:
    RESULTS[name] = f"FAIL: {detail}"
    print(f"[FAIL] {name}: {detail}")


def snapshot(context) -> dict:
    with context.db.session() as session:
        stats = StatsRepository(session).snapshot()
        projects = len(ProjectRepository(session).list_all())
        memories_total = session.scalar(select(func.count(Memory.id))) or 0
        memories_corrected = (
            session.scalar(
                select(func.count(Memory.id)).where(Memory.status == "corrected")
            )
            or 0
        )
    return {
        "projects": projects,
        "persons": stats["persons"],
        "conversations": stats["conversations"],
        "messages": stats["messages"],
        "memories_total": memories_total,
        "memories_active": stats["memories"],
        "memories_corrected": memories_corrected,
        "embeddings": context.embeddings.memory_count(),
    }


def _snippet(text: str, limit: int = 90) -> str:
    return text.strip()[:limit].replace("\n", " ")


def _safe_repr(exc: Exception, settings) -> str:
    """Exception text with any configured key masked (never printed raw)."""
    message = f"{type(exc).__name__}: {exc}"
    for secret in (
        settings.openrouter_api_key,
        settings.openrouter_api_key_1,
        settings.openrouter_api_key_2,
        settings.openai_api_key,
    ):
        if secret and len(secret) >= 4:
            message = message.replace(secret, "***")
    return message


def main() -> int:
    settings = Settings()
    app = create_app()
    context = app.state.context
    client = TestClient(app)

    # ---- 1. Configuration (booleans only, never key material) ----
    print("== CONFIGURATION ==")
    chat_cfg = settings.chat_key_configured
    embed_cfg = settings.embedding_key_configured
    split = settings.split_keys_in_use
    tts_cfg = bool(settings.openrouter_tts_model.strip())
    print(f"provider={settings.ai_provider}  vector_store={context.vector_store.name}")
    print(
        f"chat_key_configured={chat_cfg}  embedding_key_configured={embed_cfg}  "
        f"split_keys_in_use={split}  tts_configured={tts_cfg}"
    )
    print("base_url=" + (settings.openrouter_base_url or "n/a"))
    print(f"chat_model_chain={list(settings.chat_model_chain)}")
    print(f"embedding_model_chain={list(settings.embedding_model_chain)}")
    if tts_cfg:
        print(f"openrouter_tts_model={settings.openrouter_tts_model.strip()}")
    if chat_cfg and embed_cfg and split:
        _ok("configuration_key_separation")
    else:
        _fail("configuration_key_separation", f"chat={chat_cfg} embed={embed_cfg} split={split}")
    if settings.openrouter_chat_api_key and settings.openrouter_chat_api_key != settings.openrouter_embedding_api_key:
        _ok("keys_are_distinct_roles")
    else:
        _fail("keys_are_distinct_roles", "chat and embedding keys resolve to the same value")

    # ---- 2. /health + /settings secret-free ----
    print("\n== HEALTH / SETTINGS ==")
    health = client.get("/health").json()
    settings_body = client.get("/settings").json()
    settings_text = client.get("/settings").text
    health_text = client.get("/health").text
    assert (
        "sk-or" not in settings_text and "sk-or" not in health_text
    ), "key material leaked in /settings or /health"
    assert KEY_PATTERN.search(settings_text) is None and KEY_PATTERN.search(health_text) is None
    print(f"health.provider={health.get('provider')}  provider_auth_configured={health.get('provider_auth_configured')}")
    print(f"settings.provider={settings_body.get('provider')}  auth_status={settings_body.get('auth_status')}")
    for key in ("chat_key_configured", "embedding_key_configured", "split_keys_in_use", "tts_configured"):
        print(f"settings.{key}={settings_body.get(key)}")
    assert settings_body["chat_key_configured"] is chat_cfg
    assert settings_body["embedding_key_configured"] is embed_cfg
    _ok("health_settings_secret_free")

    # ---- 3. Live provider auth (dedicated key chains; fallback intact) ----
    print("\n== LIVE PROVIDER AUTH ==")
    try:
        reply = context.provider.generate(
            "You are a connectivity check.",
            [{"role": "user", "content": "Reply with exactly: OK"}],
        )
        if not reply or not reply.strip():
            raise RuntimeError("empty reply")
        print(f"live_chat_auth_reply_len={len(reply)}  reply_snippet={_snippet(reply, 40)!r}")
        _ok("live_chat_auth")
    except Exception as exc:  # noqa: BLE001 - reason only, never key material
        _fail("live_chat_auth", _safe_repr(exc, settings))

    try:
        vectors = context.provider.embed(["Live acceptance embedding diagnostic."])
        dims = {len(v) for v in vectors}
        print(
            f"live_embedding_auth_count={len(vectors)}  dims={sorted(dims)}  "
            f"active_embedding_model={context.provider.embedding_model}"
        )
        assert vectors and dims == {settings.openrouter_embedding_dimensions}
        _ok("live_embedding_auth")
    except Exception as exc:  # noqa: BLE001
        _fail("live_embedding_auth", _safe_repr(exc, settings))

    # ---- 4. Two-person E2E on a temporary project + learning + cleanup ----
    print("\n== TWO-PERSON LIVE E2E (temporary project) ==")
    baseline = snapshot(context)
    print("baseline=" + json.dumps(baseline))

    with context.db.session() as session:
        svc = ProjectService(session)
        project = svc.create(
            "Live Acceptance Test",
            participants=[
                {"role": "me", "name": "Test User"},
                {"role": "other", "name": "Test Person"},
            ],
        )
        people = svc.participants(project)
        me = next(p for p in people if p.participant_role == ME_ROLE)
        other = next(p for p in people if p.participant_role == OTHER_ROLE)
        print(
            f"temp_project_id={project.id}  me={me.id}  other={other.id}  "
            f"me_role={me.participant_role}  other_role={other.participant_role}"
        )
        assert me.project_id == project.id and other.project_id == project.id
        _ok("two_person_project_created")

        # Real chat turn -> assistant reply persisted into temp project + NEW memory.
        turn1 = context.chat_service.handle(
            session,
            ChatRequest(
                person_id=other.id,
                sender_name="me",
                message="I now prefer Java over other languages.",
            ),
        )
        assert turn1.reply.strip()
        learned1 = [l for l in turn1.learned if l.outcome == LEARNED_NEW]
        print(f"chat_turn1_reply_len={len(turn1.reply)}  learned_outcomes={[l.outcome for l in turn1.learned]}")
        if not learned1:
            raise AssertionError("expected LEARNED_NEW for the ME participant")
        mem1 = MemoryRepository(session).get(learned1[0].memory_id)
        person1 = PersonRepository(session).get(mem1.person_id)
        assert mem1.status == "active"
        assert person1.project_id == project.id
        assert "Java" in mem1.content
        ver1 = MemoryVersionRepository(session).list_for_memory(mem1.id)
        assert ver1[0].revision == 1 and ver1[0].status == "ACTIVE"
        _ok("current_conversation_learning_NEW")
        print(
            f"learned_NEW memory_id={mem1.id} status={mem1.status} type={mem1.memory_type} "
            f"content={_snippet(mem1.content)}"
        )

        # Correction turn -> old superseded, replacement ACTIVE + linked.
        turn2 = context.chat_service.handle(
            session,
            ChatRequest(
                person_id=other.id,
                sender_name="me",
                message="I changed my favorite language from Java to Python.",
            ),
        )
        learned2 = [l for l in turn2.learned if l.outcome == LEARNED_CORRECTION]
        if not learned2:
            raise AssertionError("expected LEARNED_CORRECTION")
        mem2 = MemoryRepository(session).get(learned2[0].memory_id)
        assert mem2.correction_of_id == mem1.id
        assert "Python" in mem2.content and mem2.status == "active"
        retired = MemoryRepository(session).get(mem1.id)
        assert retired.status == "corrected"
        old_versions = MemoryVersionRepository(session).list_for_memory(mem1.id)
        assert [v.status for v in old_versions] == ["ACTIVE", "SUPERSEDED"]
        _ok("current_conversation_learning_CORRECTION")
        print(
            f"learned_CORRECTION memory_id={mem2.id} correction_of={mem2.correction_of_id} "
            f"content={_snippet(mem2.content)}"
        )

        # Retrieval finds the active learned memory for the ME participant.
        hits = context.chat_service.retrieval.retrieve(
            session, "prefers Python programming language", person_id=me.id, limit=3
        )
        top = hits[0].memory if hits else None
        assert top is not None and "Python" in top.content, f"retrieval top={top and top.content!r}"
        print(f"retrieval_top_similarity={round(hits[0].similarity, 4)} content={_snippet(top.content)}")
        _ok("retrieval_finds_learned_memory")

        # Cross-project isolation: default-project retrieval must not leak the temp memory.
        default = ProjectRepository(session).find_default()
        default_people = PersonRepository(session).list_all(project_id=default.id)
        default_person = next(
            (p for p in default_people if p.name == "Kaif"), default_people[0] if default_people else None
        )
        if default_person is None:
            _fail("cross_project_isolation", "no people exist in the default project to probe")
        else:
            leaks = context.chat_service.retrieval.retrieve(
                session,
                "I changed my favorite language from Java to Python",
                person_id=default_person.id,
                limit=3,
            )
            assert all(h.memory.person_id != me.id for h in leaks), "cross-project leak detected"
            _ok("cross_project_isolation")
            print(
                f"default_project_probe_person={default_person.name} "
                f"retrieval={len(leaks)} hits, none from temp project"
            )

        # Cleanup: delete ONLY the temporary project; baseline must be restored.
        delete_result = ProjectService(session).delete(project.id, context.embeddings)
        print(
            f"temp_project_delete memories={delete_result.deleted_memories} "
            f"messages={delete_result.deleted_messages} embeddings={delete_result.deleted_embeddings} "
            f"vectors={delete_result.deleted_vectors}"
        )
        assert ProjectRepository(session).get(project.id) is None
        session.commit()

    after = snapshot(context)
    print("after_delete=" + json.dumps(after))
    assert after == baseline, f"baseline changed: {baseline} -> {after}"
    _ok("temp_project_deleted_baseline_restored")

    print("\n== RESULT ==")
    for name, status in RESULTS.items():
        print(f"{name}: {status}")
    failures = [s for s in RESULTS.values() if not s.startswith("PASS")]
    print(f"\nOVERALL: {'PARTIAL (' + str(len(failures)) + ' failed)' if failures else 'PASS'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())