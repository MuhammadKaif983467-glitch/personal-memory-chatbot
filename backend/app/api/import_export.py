"""Import / export endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
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
    if context.settings.analyze_on_import and report.person_id:
        try:
            MemoryService(db).analyze_person(report.person_id, context.embeddings)
        except Exception:
            # Import itself succeeded; analysis failure is non-fatal but visible.
            report.errors.append("Automated analysis failed - run /people/{id}/analyze manually.")


@router.get("/export/conversations")
def export_conversations(db: Session = Depends(get_db)):
    return ExportService(db).conversations()


@router.get("/export/messages")
def export_messages(db: Session = Depends(get_db)):
    return ExportService(db).messages()


@router.get("/export/memories")
def export_memories(db: Session = Depends(get_db)):
    return ExportService(db).memories()


@router.get("/export/people")
def export_people(db: Session = Depends(get_db)):
    return ExportService(db).people()