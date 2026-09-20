"""Re-embed every active memory with the active AI provider.

When the embedding provider/model changes (OpenAI -> OpenRouter, or a different
embedding model), existing vectors become semantically incompatible with new
query embeddings. This script migrates the vector store in place:

* every active memory is embedded with the active provider's embedding model,
* any vector belonging to a superseded/deleted memory is removed,
* memory ids and correction/supersession history are untouched,
* re-running is idempotent (only changed model/checksum vectors are refreshed).

It NEVER creates, edits or deletes memories - only vectors + embedding records.

Usage (from the ``backend`` folder):

    .venv\\Scripts\\python.exe scripts\\reembed_vectors.py
    .venv\\Scripts\\python.exe scripts\\reembed_vectors.py --check
    .venv\\Scripts\\python.exe scripts\\reembed_vectors.py --force
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.repositories import EmbeddingRecordRepository, MemoryRepository  # noqa: E402
from app.factory import create_app  # noqa: E402
from app.services.embedding_service import content_checksum  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-embed active memories with the active provider.")
    parser.add_argument("--check", action="store_true", help="Report compatibility without changing anything.")
    parser.add_argument("--force", action="store_true", help="Re-embed every active memory, ignoring checksums.")
    args = parser.parse_args()

    app = create_app()
    context = app.state.context
    provider = context.provider

    print(f"provider={provider.name}")
    print(f"embedding_model={provider.embedding_model}")
    print(f"embedding_dim={provider.embedding_dim}")
    if provider.name in ("mock", "local"):
        print("active provider is offline; nothing to migrate.")
        return 0

    started = time.time()
    with context.db.session() as session:
        problems = context.embeddings.verify_compatible(session)
        print(f"pre_migration_problems={problems}")

        memory_repo = MemoryRepository(session)
        record_repo = EmbeddingRecordRepository(session)
        active = memory_repo.list_active()
        all_active_ids = {m.id for m in active}
        records = record_repo.list_all()

        if args.check:
            print("active_memories=", len(all_active_ids))
            print("vectors=", len(records))
            print("inactive_memories_with_vectors=", sorted(r.memory_id for r in records if r.memory_id not in all_active_ids))
            print(f"compatible={not problems}")
            return 0

        # 1) Remove vectors for memories that are no longer active.
        removed_orphan_vectors = 0
        for record in list(records):
            if record.memory_id not in all_active_ids:
                context.embeddings.remove_memory_embedding(session, record.memory_id)
                removed_orphan_vectors += 1

        # 2) Embed (or refresh) every active memory in efficient batches.
        pending: list = []
        skipped_unchanged = 0
        for memory in active:
            existing = record_repo.get_by_memory(memory.id)
            if args.force or existing is None or existing.model != provider.embedding_model:
                pending.append(memory)
                continue
            if existing.checksum != content_checksum(memory.content):
                pending.append(memory)
                continue
            skipped_unchanged += 1
        regenerated = context.embeddings.ensure_memory_embeddings(session, pending)

        remaining_problems = context.embeddings.verify_compatible(session)
        active_count = len(all_active_ids)
        vector_count = context.embeddings.memory_count()
        records_after = record_repo.list_all()
        models = sorted({r.model for r in records_after})

    elapsed = time.time() - started
    print(f"active_memories={active_count}")
    print(f"active_memories_with_vectors={len(records_after)}")
    print(f"vectors={vector_count}")
    print(f"regenerated_embeddings={regenerated}")
    print(f"skipped_unchanged={skipped_unchanged}")
    print(f"removed_orphan_vectors={removed_orphan_vectors}")
    print(f"embedding_models={models}")
    print(f"embedding_compatible={not remaining_problems}")
    print(f"remaining_problems={remaining_problems}")
    print(f"elapsed_seconds={elapsed:.1f}")

    if remaining_problems:
        print("ERROR: migration did not fully converge.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())