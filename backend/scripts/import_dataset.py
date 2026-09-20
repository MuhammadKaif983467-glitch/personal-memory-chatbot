"""Import a full conversation dataset through the end-to-end pipeline.

Usage (from the ``backend`` folder):

    .venv\\Scripts\\python.exe scripts\\import_dataset.py
    .venv\\Scripts\\python.exe scripts\\import_dataset.py --dry-run
    .venv\\Scripts\\python.exe scripts\\import_dataset.py --no-analyze
    .venv\\Scripts\\python.exe scripts\\import_dataset.py --queries "What sport does Kaif follow?"

The import is idempotent: run it as many times as you like, existing records
and embeddings are skipped. Nothing in the source dataset is modified.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import PROJECT_ROOT  # noqa: E402
from app.database.repositories import PersonRepository, StatsRepository  # noqa: E402
from app.factory import create_app  # noqa: E402
from app.schemas.chat import ChatRequest  # noqa: E402
from app.services.dataset_import_service import DatasetImportService  # noqa: E402

DEFAULT_PATH = PROJECT_ROOT / "data" / "imports" / "kaif_zain_10000_messages.json"

# The questions the correction test-suite cares about, per person.
PROBES = {
    "Kaif": [
        "What sport does Kaif follow?",
        "What programming language does Kaif prefer for quick scripting?",
        "What drink does Kaif currently prefer after the correction?",
        "What is Kaif's current exam date?",
    ],
    "Zain": [
        "What sport does Zain follow?",
        "What programming language does Zain prefer?",
        "What is the current deadline for Zain's database project?",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the Kaif/Zain dataset.")
    parser.add_argument("--path", default=str(DEFAULT_PATH), help="Path to the dataset JSON file.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count without writing.")
    parser.add_argument("--no-analyze", action="store_true", help="Skip profile/style/memory/embeddings.")
    parser.add_argument("--queries", nargs="*", default=None, help="Override the probe questions.")
    parser.add_argument("--no-retrieval", action="store_true", help="Skip the retrieval/answer probe.")
    parser.add_argument("--no-answer", action="store_true", help="Retrieve only, skip the chatbot answer.")
    parser.add_argument("--out", default="", help="Optional path to write the JSON report.")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"Dataset not found: {path}", file=sys.stderr)
        return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    app = create_app()
    context = app.state.context

    started = time.time()
    with context.db.session() as session:
        service = DatasetImportService(session, context.settings, context.embeddings)
        report = service.import_dataset(
            data,
            consent_confirmed=True,
            dry_run=args.dry_run,
            analyze=not args.no_analyze,
        )
        elapsed = time.time() - started
        report_json = report.model_dump()

        if not args.dry_run and not args.no_retrieval:
            before = _mutation_snapshot(session, context)
            report_json["probes"] = _probe(
                session, context, args.queries, answer=not args.no_answer
            )
            after = _mutation_snapshot(session, context)
            report_json["probe_mutations"] = {
                key: after[key] - before[key] for key in before
            }
            report_json["probe_read_only"] = all(
                delta == 0 for delta in report_json["probe_mutations"].values()
            )

    print(json.dumps(report_json, indent=2, ensure_ascii=False, default=str))
    print(f"\nelapsed_seconds={elapsed:.1f}")
    mutations = report_json.get("probe_mutations")
    if mutations is not None:
        print(f"probe_mutations={mutations}")
        print(f"probe_read_only={report_json['probe_read_only']}")

    if args.out:
        Path(args.out).write_text(json.dumps(report_json, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"report_written={args.out}")
    return 0


def _mutation_snapshot(session, context) -> dict:
    """Counts used to prove the probe path performs zero writes."""
    snapshot = dict(StatsRepository(session).snapshot())
    snapshot["vectors"] = context.embeddings.memory_count()
    return snapshot


def _probe(session, context, queries, *, answer: bool) -> list[dict]:
    results: list[dict] = []
    people = {p.name: p for p in PersonRepository(session).list_all()}
    for person_name, person in people.items():
        person_queries = queries if queries else PROBES.get(person_name, [])
        if not person_queries:
            print(
                f"warning: no probe questions configured for person '{person_name}'; "
                "add lines to the PROBES map to probe this person.",
                file=sys.stderr,
            )
        for query in person_queries:
            entry: dict = {
                "person": person_name,
                "query": query,
                "answer": None,
                "answer_confidence": None,
                "context_chars": 0,
            }
            if answer:
                # Read-only turn: retrieve -> rank -> context -> answer, no writes.
                preview = context.chat_service.answer_preview(
                    session, ChatRequest(person_id=person.id, message=query)
                )
                entry["answer"] = preview.reply
                entry["answer_confidence"] = preview.confidence.level
                entry["context_chars"] = preview.context_chars
                entry["retrieved"] = [
                    {
                        "content": item.content,
                        "memory_type": item.memory_type,
                        "confidence": item.confidence,
                        "similarity": round(item.similarity, 4),
                    }
                    for item in preview.retrieved[:3]
                ]
            else:
                hits = context.chat_service.retrieval.retrieve(
                    session, query, person_id=person.id, limit=3
                )
                entry["retrieved"] = [
                    {
                        "content": hit.memory.content,
                        "memory_type": hit.memory.memory_type,
                        "confidence": hit.memory.confidence,
                        "similarity": round(hit.similarity, 4),
                    }
                    for hit in hits
                ]
            results.append(entry)
    return results


if __name__ == "__main__":
    raise SystemExit(main())
