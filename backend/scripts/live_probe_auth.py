"""Stage-by-stage live auth prober (NO database writes).

Writes progress to data/live_auth_log.txt (flushed per line) and also prints.
Each live stage has a hard deadline so a rate-limited provider cannot hang the
probe forever. Never prints credential material.

Run: .venv\\Scripts\\python.exe -u scripts\\live_probe_auth.py
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.factory import create_app  # noqa: E402

LOG = BACKEND_DIR / ".." / "data" / "live_auth_log.txt"


def log(line: str) -> None:
    ts = time.strftime("%H:%M:%S")
    text = f"[{ts}] {line}"
    print(text, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(text + "\n")
        fh.flush()


def run_with_deadline(name: str, fn, seconds: int, settings=None):
    out: dict = {"done": False, "error": None, "value": None}

    def worker():
        try:
            out["value"] = fn()
            out["done"] = True
        except Exception as exc:  # noqa: BLE001
            out["error"] = exc

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        log(f"{name}: NOT COMPLETED within {seconds}s (rate-limited or blocked)")
        return None
    if out["error"] is not None:
        # Never leak credential material into the log: mask any configured key
        # that happens to appear inside the exception message.
        message = _sanitize(str(out["error"]), settings)
        log(f"{name}: FAILED {type(out['error']).__name__}: {message}")
        return None
    return out["value"]


def _sanitize(message: str, settings) -> str:
    if not settings:
        return message
    secrets = [
        settings.openrouter_api_key,
        settings.openrouter_api_key_1,
        settings.openrouter_api_key_2,
        settings.openai_api_key,
    ]
    for secret in secrets:
        if secret and len(secret) >= 4:
            message = message.replace(secret, "***")
    return message


def main() -> int:
    settings = Settings()
    app = create_app()
    context = app.state.context
    client = TestClient(app)
    LOG.unlink(missing_ok=True)

    log("== CONFIGURATION ==")
    log(f"provider={settings.ai_provider} vector_store={context.vector_store.name}")
    log(f"chat_key_configured={settings.chat_key_configured}")
    log(f"embedding_key_configured={settings.embedding_key_configured}")
    log(f"split_keys_in_use={settings.split_keys_in_use}")
    log(f"tts_configured={bool(settings.openrouter_tts_model.strip())}")
    log(f"keys_distinct={settings.openrouter_chat_api_key != settings.openrouter_embedding_api_key}")

    log("== HEALTH / SETTINGS (secret-free) ==")
    health = client.get("/health").json()
    body = client.get("/settings").json()
    log(f"health.provider={health.get('provider')} auth={health.get('provider_auth_configured')}")
    log(f"settings.provider={body.get('provider')} auth_status={body.get('auth_status')} "
        f"chat_key={body.get('chat_key_configured')} embed_key={body.get('embedding_key_configured')} "
        f"split={body.get('split_keys_in_use')} tts={body.get('tts_configured')}")
    text = client.get("/settings").text + client.get("/health").text
    log(f"settings_health_leak_check={'CLEAN' if ('sk-or' not in text) else 'LEAK_DETECTED'}")

    log("== LIVE CHAT AUTH (KEY_2 chain) ==")
    started = time.time()

    def chat_call():
        return context.provider.generate(
            "You are a connectivity check.", [{"role": "user", "content": "Reply with exactly: OK"}]
        )

    reply = run_with_deadline("live_chat_auth", chat_call, 120, settings)
    if reply is not None:
        log(f"live_chat_AUTH=PASS reply_len={len(reply)} el_s={round(time.time() - started, 1)} "
            f"reply_snippet={reply.strip()[:40]!r}")

    log("== LIVE EMBEDDING AUTH (KEY_1 chain) ==")
    started = time.time()

    def embed_call():
        vectors = context.provider.embed(["Live acceptance embedding diagnostic."])
        return (len(vectors), {len(v) for v in vectors}, context.provider.embedding_model)

    result = run_with_deadline("live_embedding_auth", embed_call, 150, settings)
    if result is not None:
        count, dims, model = result
        log(f"live_embedding_AUTH=PASS count={count} dims={sorted(dims)} model={model} "
            f"el_s={round(time.time() - started, 1)}")

    log("== DONE ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())