"""Database engine and session management.

The engine/session factory is created per application (dependency injection),
so tests can spin up isolated databases without touching a module-level engine.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, select, text, update
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Database:
    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.url = url
        connect_args = (
            {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
        )
        self.engine = create_engine(url, connect_args=connect_args, echo=echo, future=True)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False, future=True
        )

    def init(self) -> None:
        """Create tables and apply additive migrations (idempotent).

        Import models first so they register on Base.
        """
        # noqa: F401 - importing registers the models on Base.metadata
        from app.database import models  # noqa: F401
        Base.metadata.create_all(self.engine)
        self.migrate()

    def migrate(self) -> None:
        """Additive, non-destructive schema/data migration for existing SQLite
        databases created before the multi-project model existed.

        * adds a ``project_id`` column to persons / conversations / memories,
        * adds the ``participant_role`` column to persons (ME / OTHER setup),
        * ensures a default ("Demo / Regression") project exists,
        * backfills every untagged row into that project so no data is ever
          stranded outside an isolation boundary.
        """
        if not self.url.startswith("sqlite"):
            return
        from app.database import models  # noqa: F401
        from app.database.models import DEFAULT_PROJECT_NAME, Conversation, Memory, Person, Project

        def _ensure_column(table: str, column_sql: str, name: str) -> None:
            with self.engine.connect() as conn:
                columns = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_sql}"))
                    conn.commit()

        _ensure_column("persons", "project_id INTEGER REFERENCES projects(id)", "project_id")
        _ensure_column("conversations", "project_id INTEGER REFERENCES projects(id)", "project_id")
        _ensure_column("memories", "project_id INTEGER REFERENCES projects(id)", "project_id")
        _ensure_column("persons", "participant_role VARCHAR(20) DEFAULT ''", "participant_role")

        with self.session_ctx() as session:
            if session.scalar(select(Project.id).limit(1)) is None:
                session.add(Project(name=DEFAULT_PROJECT_NAME, user_id="local"))
                session.flush()
            default_id = session.scalar(select(Project.id).order_by(Project.id.asc()).limit(1))

            session.execute(update(Person).where(Person.project_id.is_(None)).values(project_id=default_id))
            session.execute(
                update(Conversation).where(Conversation.project_id.is_(None)).values(project_id=default_id)
            )
            memory_project = (
                select(Person.project_id).where(Person.id == Memory.person_id).correlate(Memory).scalar_subquery()
            )
            session.execute(
                update(Memory).where(Memory.project_id.is_(None)).values(project_id=memory_project)
            )

    def session(self) -> Session:
        return self.session_factory()

    @contextmanager
    def session_ctx(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()