"""Backup management endpoints.

Provides create, list, validate, and restore operations for database
backups. All paths are controlled by application configuration — no
arbitrary filesystem access.

V3.3 Phase 3 — Backup, Recovery, Summarization & Memory Relationships.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import AppContext, get_context, get_db
from app.services.backup_service import BackupService

router = APIRouter(prefix="/backup", tags=["backup"])


class BackupCreateRequest(BaseModel):
    label: str = ""


class BackupCreateResponse(BaseModel):
    valid: bool
    path: str
    size: int
    schema_version: str = ""
    message_count: int = 0
    memory_count: int = 0
    conversation_count: int = 0
    person_count: int = 0
    created_at: str = ""
    errors: list[str] = []
    warnings: list[str] = []


class BackupListItem(BaseModel):
    valid: bool
    path: str
    size: int
    schema_version: str = ""
    message_count: int = 0
    memory_count: int = 0
    created_at: str = ""
    errors: list[str] = []
    warnings: list[str] = []


class BackupValidateRequest(BaseModel):
    backup_path: str


class BackupRestoreRequest(BaseModel):
    backup_path: str


def _get_backup_service(context: AppContext) -> BackupService:
    return BackupService(context.settings.database_url)


@router.post("/create", response_model=BackupCreateResponse)
def create_backup(
    req: BackupCreateRequest = BackupCreateRequest(),
    context: AppContext = Depends(get_context),
):
    svc = _get_backup_service(context)
    meta = svc.create(label=req.label)
    return BackupCreateResponse(
        valid=meta.valid,
        path=meta.path,
        size=meta.size,
        schema_version=meta.schema_version,
        message_count=meta.message_count,
        memory_count=meta.memory_count,
        conversation_count=meta.conversation_count,
        person_count=meta.person_count,
        created_at=meta.created_at,
        errors=meta.errors,
        warnings=meta.warnings,
    )


@router.get("", response_model=list[BackupListItem])
def list_backups(context: AppContext = Depends(get_context)):
    svc = _get_backup_service(context)
    backups = svc.list_backups()
    return [
        BackupListItem(
            valid=b.valid,
            path=b.path,
            size=b.size,
            schema_version=b.schema_version,
            message_count=b.message_count,
            memory_count=b.memory_count,
            created_at=b.created_at,
            errors=b.errors,
            warnings=b.warnings,
        )
        for b in backups
    ]


@router.post("/validate", response_model=BackupCreateResponse)
def validate_backup(
    req: BackupValidateRequest,
    context: AppContext = Depends(get_context),
):
    svc = _get_backup_service(context)
    backup_path = Path(req.backup_path)
    # Security: validate path is within backup directory
    try:
        backup_path.resolve().relative_to(svc.backup_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Path must be within the backup directory")

    meta = svc.validate(backup_path)
    return BackupCreateResponse(
        valid=meta.valid,
        path=meta.path,
        size=meta.size,
        schema_version=meta.schema_version,
        message_count=meta.message_count,
        memory_count=meta.memory_count,
        conversation_count=meta.conversation_count,
        person_count=meta.person_count,
        created_at=meta.created_at,
        errors=meta.errors,
        warnings=meta.warnings,
    )


@router.post("/restore", response_model=BackupCreateResponse)
def restore_backup(
    req: BackupRestoreRequest,
    context: AppContext = Depends(get_context),
):
    svc = _get_backup_service(context)
    backup_path = Path(req.backup_path)
    # Security: validate path is within backup directory
    try:
        backup_path.resolve().relative_to(svc.backup_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Path must be within the backup directory")

    meta = svc.restore(backup_path)
    if not meta.valid:
        raise HTTPException(status_code=422, detail={"errors": meta.errors})
    return BackupCreateResponse(
        valid=meta.valid,
        path=meta.path,
        size=meta.size,
        schema_version=meta.schema_version,
        message_count=meta.message_count,
        memory_count=meta.memory_count,
        conversation_count=meta.conversation_count,
        person_count=meta.person_count,
        created_at=meta.created_at,
        errors=meta.errors,
        warnings=meta.warnings,
    )
