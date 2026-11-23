from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.base import Base
from app.database.migrate import upgrade_database
from app.database.models import Base as ModelsBase
from app.database.session import Database
from app.models import Job, JobEvent, MediaAsset, Post, Project
from app.services.job_service import JobRunner


def test_migration_creates_every_model_table(settings: Settings) -> None:
    upgrade_database(settings.resolved_database_url)
    db = Database(settings.resolved_database_url)
    try:
        tables = set(inspect(db.engine).get_table_names())
    finally:
        db.dispose()
    assert set(ModelsBase.metadata.tables) <= tables
    assert "alembic_version" in tables


def test_migration_is_repeatable(settings: Settings) -> None:
    upgrade_database(settings.resolved_database_url)
    upgrade_database(settings.resolved_database_url)  # no error when already at head


def test_models_and_migration_agree(db: Database) -> None:
    """Fails when a model changes without a new Alembic revision."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_data_survives_a_new_connection(settings: Settings, session: Session, db: Database) -> None:
    session.add(Project(id="p1", name="One", path="/x/one"))
    session.commit()
    db2 = Database(settings.resolved_database_url)
    try:
        s2 = db2.session()
        assert s2.get(Project, "p1").name == "One"  # type: ignore[union-attr]
        s2.close()
    finally:
        db2.dispose()


def test_datetimes_are_timezone_aware_utc(session: Session) -> None:
    session.add(Project(id="p", name="P", path="/p"))
    session.commit()
    local = timezone(timedelta(hours=5, minutes=30))
    when = datetime(2026, 11, 23, 12, 0, tzinfo=local)
    session.add(Post(project_id="p", platform="youtube", output_file="a.mp4", scheduled_at=when))
    session.commit()
    session.expire_all()
    got = session.query(Post).one().scheduled_at
    assert got is not None and got.tzinfo is not None
    assert got == when and got.utcoffset() == timedelta(0)
    assert got.hour == 6 and got.minute == 30


def test_naive_datetimes_are_rejected(session: Session) -> None:
    session.add(Project(id="p", name="P", path="/p"))
    session.add(Post(project_id="p", platform="x", output_file="a", scheduled_at=datetime(2026, 1, 1)))
    with pytest.raises(Exception, match="Naive datetime"):
        session.commit()
    session.rollback()


def test_foreign_keys_are_enforced_and_cascade(session: Session) -> None:
    session.add(MediaAsset(project_id="nope", relative_path="a.mp4", kind="video"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    session.add(Project(id="p", name="P", path="/p"))
    session.commit()
    job = Job(type="media.scan", project_id="p")
    session.add(job)
    session.commit()
    session.add(JobEvent(job_id=job.id, event="info"))
    session.add(MediaAsset(project_id="p", relative_path="a.mp4", kind="video"))
    session.commit()
    session.delete(session.get(Project, "p"))
    session.commit()
    assert session.query(MediaAsset).count() == 0
    assert session.query(Job).count() == 0 and session.query(JobEvent).count() == 0


def test_unique_media_path_per_project(session: Session) -> None:
    session.add(Project(id="p", name="P", path="/p"))
    session.commit()
    session.add(MediaAsset(project_id="p", relative_path="a.mp4", kind="video"))
    session.commit()
    session.add(MediaAsset(project_id="p", relative_path="a.mp4", kind="video"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_sqlite_uses_wal_and_foreign_keys(db: Database) -> None:
    with db.engine.connect() as c:
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert str(c.execute(text("PRAGMA journal_mode")).scalar()).lower() == "wal"


def test_interrupted_jobs_are_marked_failed_on_startup(db: Database, session: Session, config) -> None:  # type: ignore[no-untyped-def]
    session.add_all(
        [Job(type="a", status="running"), Job(type="b", status="queued"), Job(type="c", status="completed")]
    )
    session.commit()
    assert JobRunner(db, config).recover_interrupted() == 2
    session.expire_all()
    statuses = sorted(j.status for j in session.query(Job))
    assert statuses == ["completed", "failed", "failed"]
    assert all("Interrupted" in (j.error or "") for j in session.query(Job) if j.status == "failed")


def test_utc_helper_matches_utc_zone() -> None:
    from app.database.base import utcnow

    assert utcnow().tzinfo is UTC


def test_alembic_files_exist_on_disk() -> None:
    assert list((Path(__file__).parents[2] / "app/database/migrations/versions").glob("0001_*.py"))
