"""Import / export endpoints."""

from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import AppContext, get_context, get_db
from app.core.exceptions import ImportValidationError
from app.schemas.import_export import (
    DatasetImportResult,
    ImportPayload,
    ImportPreviewResult,
    ImportResult,
    ImportedConversationInfo,
)
from app.services.dataset_import_service import DatasetImportService
from app.services.export_service import ExportService
from app.services.import_preview_service import ImportPreviewService
from app.services.import_service import ImportService
from app.services.memory_service import MemoryService

router = APIRouter()


async def _read_upload(file: UploadFile, context: AppContext) -> bytes:
    """Read an upload with a hard size cap so a huge file cannot exhaust memory."""
    max_bytes = context.settings.import_max_bytes
    raw = await file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ImportValidationError(
            f"Upload is too large (over {max_bytes // (1024 * 1024)} MB). Import in smaller chunks."
        )
    return raw


@router.post("/import/preview", response_model=ImportPreviewResult)
async def import_preview(
    file: UploadFile = File(...),
    person: str = Form(""),
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    """Read-only preview of an upload: counts and samples, no writes.

    Supports .txt (chat/TXT lines), .csv, .json, and .zip (containing one of
    the former). Never stores anything; use /import/txt or /import/zip to apply.
    """
    raw = await _read_upload(file, context)
    # Never silently discard malformed records: preview reports them.
    return ImportPreviewService().preview_file(file.filename or "upload", raw, person)


@router.post("/import/txt", response_model=ImportResult)
async def import_txt(
    file: UploadFile = File(...),
    person: str = Form(...),
    consent_confirmed: bool = Form(False),
    title: str = Form("Imported Chat"),
    project_id: int | None = Form(None),
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    """Import a plain-text chat log (or TXT export) as conversation history."""
    raw = await _read_upload(file, context)
    preview = ImportPreviewService()
    messages = preview.txt_to_messages(raw, person=person)
    payload = ImportPayload(
        consent_confirmed=consent_confirmed,
        conversation=ImportedConversationInfo(title=title or "Imported Chat", person=person, source="txt"),
        messages=messages,
        project_id=project_id,
    )
    report = ImportService(db, context.settings).import_payload(payload)
    _analyze_if_enabled(context, db, report)
    context.metrics.inc("imports")
    return report


@router.post("/import/zip", response_model=ImportResult)
async def import_zip(
    file: UploadFile = File(...),
    person: str = Form(""),
    consent_confirmed: bool = Form(False),
    title: str = Form("Imported Chat"),
    project_id: int | None = Form(None),
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    """Import the largest text/log file inside a ZIP archive."""
    raw = await _read_upload(file, context)
    preview = ImportPreviewService()
    messages = preview.zip_to_messages(raw, person=person)
    person_name = person or ImportPreviewService.name_without_zip(file.filename or "")
    payload = ImportPayload(
        consent_confirmed=consent_confirmed,
        conversation=ImportedConversationInfo(title=title or "Imported Chat", person=person_name, source="zip"),
        messages=messages,
        project_id=project_id,
    )
    report = ImportService(db, context.settings).import_payload(payload)
    _analyze_if_enabled(context, db, report)
    context.metrics.inc("imports")
    return report


@router.post("/import/json", response_model=ImportResult)
def import_json(payload: ImportPayload, db: Session = Depends(get_db), context: AppContext = Depends(get_context)):
    """Import conversation history from JSON.

    Consent (consent_confirmed) is mandatory: you must have permission to
    process another person's data before we store or analyse it.
    """
    report = ImportService(db, context.settings).import_payload(payload)
    _analyze_if_enabled(context, db, report)
    context.metrics.inc("imports")
    return report


@router.post("/import/csv", response_model=ImportResult)
async def import_csv(
    file: UploadFile = File(...),
    person: str = Form(...),
    consent_confirmed: bool = Form(False),
    title: str = Form("Imported Chat"),
    project_id: int | None = Form(None),
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    raw = await _read_upload(file, context)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    report = ImportService(db, context.settings).import_csv(
        text,
        person_name=person,
        title=title,
        source="csv",
        consent_confirmed=consent_confirmed,
        project_id=project_id,
    )
    _analyze_if_enabled(context, db, report)
    context.metrics.inc("imports")
    return report


@router.post("/import/jsonl", response_model=ImportResult)
async def import_jsonl(
    file: UploadFile = File(...),
    person: str = Form(...),
    consent_confirmed: bool = Form(False),
    title: str = Form("Imported Chat"),
    project_id: int | None = Form(None),
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    """Import conversation history from JSONL/NDJSON (one JSON object per line)."""
    raw = await _read_upload(file, context)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    report = ImportService(db, context.settings).import_jsonl(
        text,
        person_name=person,
        title=title,
        source="jsonl",
        consent_confirmed=consent_confirmed,
        project_id=project_id,
    )
    _analyze_if_enabled(context, db, report)
    context.metrics.inc("imports")
    return report


@router.post("/import/dataset", response_model=DatasetImportResult)
def import_dataset(
    payload: dict,
    dry_run: bool = False,
    analyze: bool = True,
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    """Import a full multi-participant dataset (Kaif/Zain format).

    The body must include ``consent_confirmed: true``. ``dry_run=true``
    validates and counts without writing; the default safe mode is idempotent
    so the same dataset can be imported repeatedly without duplicate rows.
    """
    service = DatasetImportService(db, context.settings, context.embeddings)
    report = service.import_dataset(
        payload,
        consent_confirmed=bool(payload.get("consent_confirmed")),
        dry_run=dry_run,
        analyze=analyze,
    )
    context.metrics.inc("imports")
    return report


def _analyze_if_enabled(context: AppContext, db: Session, report: ImportResult) -> None:
    if not context.settings.analyze_on_import or not report.person_id:
        return
    if not getattr(context.provider, "chat_key_configured", False):
        return
    person_id = report.person_id
    embeddings = context.embeddings

    def _run():
        session = context.db.session()
        try:
            MemoryService(session).analyze_person(person_id, embeddings)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


@router.post("/import/universal/inspect")
async def inspect_upload(
    file: UploadFile = File(...),
    context: AppContext = Depends(get_context),
):
    """Inspect an uploaded file and detect platform/format without importing."""
    from app.services.import_engine.orchestrator import ImportOrchestrator
    raw = await _read_upload(file, context)
    orch = ImportOrchestrator()
    return orch.inspect(file.filename or "upload", raw)


@router.post("/import/universal/preview")
async def universal_preview(
    file: UploadFile = File(...),
    person: str = Form(""),
    context: AppContext = Depends(get_context),
):
    """Preview an upload with platform detection and participant info."""
    from app.services.import_engine.orchestrator import ImportOrchestrator
    raw = await _read_upload(file, context)
    orch = ImportOrchestrator()
    return orch.preview_file(file.filename or "upload", raw, person)


@router.post("/import/universal", response_model=ImportResult)
async def universal_import(
    file: UploadFile = File(...),
    person: str = Form(""),
    consent_confirmed: bool = Form(False),
    project_id: int | None = Form(None),
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
):
    """Universal import: auto-detect platform, parse, and import."""
    from app.services.import_engine.orchestrator import ImportOrchestrator
    raw = await _read_upload(file, context)
    orch = ImportOrchestrator()
    payload = orch.import_file(
        file.filename or "upload", raw,
        person=person, consent_confirmed=consent_confirmed,
        project_id=project_id,
    )
    report = ImportService(db, context.settings).import_payload(payload)
    _analyze_if_enabled(context, db, report)
    context.metrics.inc("imports")
    return report


@router.get("/export/conversations")
def export_conversations(project_id: int | None = Query(None), db: Session = Depends(get_db)):
    return ExportService(db).conversations(project_id=project_id)


@router.get("/export/messages")
def export_messages(project_id: int | None = Query(None), db: Session = Depends(get_db)):
    return ExportService(db).messages(project_id=project_id)


@router.get("/export/memories")
def export_memories(project_id: int | None = Query(None), db: Session = Depends(get_db)):
    return ExportService(db).memories(project_id=project_id)


@router.get("/export/people")
def export_people(project_id: int | None = Query(None), db: Session = Depends(get_db)):
    return ExportService(db).people(project_id=project_id)