"""Database backup and restore service.

Provides atomic, integrity-checked backups using SQLite's online backup API.
Backups are timestamped, versioned, and validated before any destructive
operation like restore.

V3.3 Phase 3 — Backup, Recovery, Summarization & Memory Relationships.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger

logger = get_logger("backup")


@dataclass
class BackupMetadata:
    """Structured result from backup operations."""
    valid: bool
    path: str
    size: int = 0
    schema_version: str = ""
    message_count: int = 0
    memory_count: int = 0
    conversation_count: int = 0
    person_count: int = 0
    created_at: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _get_db_path(database_url: str) -> Path:
    """Extract the filesystem path from a SQLAlchemy sqlite URL."""
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///"):]).resolve()
    raise ValueError(f"Not a SQLite URL: {database_url}")


def _timestamp() -> str:
    """UTC timestamp safe for filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class BackupService:
    """Create, validate, list, and restore SQLite database backups.

    Uses SQLite's online backup API (``.backup()``) for atomic, consistent
    copies even while the database is in active use.
    """

    def __init__(self, database_url: str, backup_dir: Optional[Path] = None) -> None:
        self.db_path = _get_db_path(database_url)
        if backup_dir is None:
            backup_dir = self.db_path.parent / "backups"
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    # ── CREATE ──────────────────────────────────────────────────────────

    def create(self, label: str = "") -> BackupMetadata:
        """Create an atomic backup of the active database.

        Uses SQLite's backup API for consistency. The source database is
        never modified.
        """
        ts = _timestamp()
        suffix = f".{label}" if label else ""
        backup_name = f"chatbot.db.backup.{ts}{suffix}.bak"
        backup_path = self.backup_dir / backup_name

        logger.info("Creating backup: %s", backup_name)

        src_conn: Optional[sqlite3.Connection] = None
        dst_conn: Optional[sqlite3.Connection] = None
        try:
            src_conn = sqlite3.connect(str(self.db_path), timeout=30)
            dst_conn = sqlite3.connect(str(backup_path), timeout=30)

            # Online backup: pages are copied atomically
            src_conn.backup(dst_conn, pages=256, sleep=0.01)
            dst_conn.commit()

            # Verify the backup
            meta = self.validate(backup_path)
            if not meta.valid:
                logger.error("Backup created but failed validation: %s", meta.errors)
            else:
                logger.info(
                    "Backup OK: %s (%d bytes, %d msgs, %d memories)",
                    backup_name, meta.size, meta.message_count, meta.memory_count,
                )
            return meta
        except Exception as exc:
            # Clean up partial backup on failure
            if backup_path.exists():
                backup_path.unlink()
            logger.error("Backup failed: %s", exc)
            return BackupMetadata(
                valid=False,
                path=str(backup_path),
                errors=[f"Backup creation failed: {exc}"],
            )
        finally:
            if src_conn:
                src_conn.close()
            if dst_conn:
                dst_conn.close()

    # ── LIST ────────────────────────────────────────────────────────────

    def list_backups(self) -> list[BackupMetadata]:
        """List all valid backups in the backup directory, newest first."""
        backups: list[BackupMetadata] = []
        for p in sorted(self.backup_dir.glob("chatbot.db.backup.*.bak"), reverse=True):
            meta = self.validate(p)
            backups.append(meta)
        return backups

    # ── VALIDATE ────────────────────────────────────────────────────────

    def validate(self, backup_path: Path) -> BackupMetadata:
        """Comprehensive validation of a backup file.

        Checks: file exists, readable, opens as SQLite, integrity_check,
        foreign_key_check, required tables, row counts.
        """
        meta = BackupMetadata(valid=False, path=str(backup_path))
        errors: list[str] = []
        warnings: list[str] = []

        # 1. File exists
        if not backup_path.exists():
            errors.append("File does not exist")
            meta.errors = errors
            return meta

        # 2. File readable
        if not os.access(backup_path, os.R_OK):
            errors.append("File is not readable")
            meta.errors = errors
            return meta

        meta.size = backup_path.stat().st_size

        # 3. Opens as SQLite
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(str(backup_path), timeout=10)
            cursor = conn.cursor()

            # 4. Integrity check
            result = cursor.execute("PRAGMA integrity_check").fetchone()
            if result[0] != "ok":
                errors.append(f"integrity_check failed: {result[0]}")
                meta.errors = errors
                return meta

            # 5. Foreign key check
            fk_violations = cursor.execute("PRAGMA foreign_key_check").fetchall()
            if fk_violations:
                warnings.append(f"{len(fk_violations)} FK violations found")

            # 6. Schema version
            try:
                row = cursor.execute(
                    "SELECT version FROM schema_migrations ORDER BY applied_at DESC LIMIT 1"
                ).fetchone()
                meta.schema_version = row[0] if row else "pre-v3.3"
            except Exception:
                meta.schema_version = "pre-v3.3"

            # 7. Required tables
            tables = {
                row[0] for row in cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            required = {"projects", "persons", "conversations", "messages", "memories"}
            missing = required - tables
            if missing:
                errors.append(f"Missing required tables: {missing}")

            # 8. Row counts
            try:
                meta.message_count = cursor.execute("SELECT count(*) FROM messages").fetchone()[0]
                meta.memory_count = cursor.execute("SELECT count(*) FROM memories").fetchone()[0]
                meta.conversation_count = cursor.execute("SELECT count(*) FROM conversations").fetchone()[0]
                meta.person_count = cursor.execute("SELECT count(*) FROM persons").fetchone()[0]
            except Exception as e:
                warnings.append(f"Could not count rows: {e}")

            # 9. FTS5 check
            try:
                cursor.execute("SELECT count(*) FROM messages_fts").fetchone()
            except Exception:
                warnings.append("FTS5 table missing or empty")

            meta.created_at = datetime.fromtimestamp(
                backup_path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            meta.errors = errors
            meta.warnings = warnings
            meta.valid = len(errors) == 0

        except Exception as exc:
            errors.append(f"Failed to open as SQLite: {exc}")
            meta.errors = errors
        finally:
            if conn:
                conn.close()

        return meta

    # ── RESTORE ─────────────────────────────────────────────────────────

    def restore(self, backup_path: Path) -> BackupMetadata:
        """Restore the database from a validated backup.

        Uses SQLite's online backup API to overwrite the current database
        in-place. This works even when the database is in active use.

        Steps:
        1. Validate source backup
        2. Create emergency backup of current DB
        3. Use SQLite backup API to overwrite current DB from backup
        4. Verify restored database
        """
        logger.info("Restore requested from: %s", backup_path.name)

        # Step 1: Validate source backup
        source_meta = self.validate(backup_path)
        if not source_meta.valid:
            return BackupMetadata(
                valid=False,
                path=str(backup_path),
                errors=[f"Source backup invalid: {source_meta.errors}"],
            )

        # Step 2: Create emergency backup
        logger.info("Creating emergency backup before restore...")
        emergency = self.create(label="pre_restore")
        if not emergency.valid:
            return BackupMetadata(
                valid=False,
                path=str(backup_path),
                errors=[f"Emergency backup failed: {emergency.errors}"],
            )

        # Step 3: Use SQLite backup API to overwrite current DB
        src_conn: Optional[sqlite3.Connection] = None
        dst_conn: Optional[sqlite3.Connection] = None
        try:
            src_conn = sqlite3.connect(str(backup_path), timeout=30)
            dst_conn = sqlite3.connect(str(self.db_path), timeout=30)

            # This copies all pages from backup into the live database,
            # effectively replacing all data atomically
            src_conn.backup(dst_conn, pages=256, sleep=0.01)
            dst_conn.commit()

            # Step 4: Verify restored database
            restored_meta = self.validate(self.db_path)
            if not restored_meta.valid:
                logger.error("Restored DB failed validation: %s", restored_meta.errors)
                return BackupMetadata(
                    valid=False,
                    path=str(backup_path),
                    errors=[f"Restored DB invalid: {restored_meta.errors}"],
                )

            logger.info("Restore complete: %d messages, %d memories",
                        restored_meta.message_count, restored_meta.memory_count)
            return restored_meta

        except Exception as exc:
            logger.error("Restore failed: %s", exc)
            return BackupMetadata(
                valid=False,
                path=str(backup_path),
                errors=[f"Restore failed: {exc}"],
            )
        finally:
            if src_conn:
                src_conn.close()
            if dst_conn:
                dst_conn.close()
