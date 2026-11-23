from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UTCDateTime, new_id, utcnow


class Job(Base):
    """A unit of background work. SQLite — not JSON files — is the job store."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("job"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), default=None)
    # e.g. media.scan, pipeline.process
    type: Mapped[str] = mapped_column(String(64))
    # queued | running | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_stage: Mapped[str | None] = mapped_column(String(64), default=None)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class JobEvent(Base):
    """Per-stage trace: configuration used, outputs produced, failures."""

    __tablename__ = "job_events"
    __table_args__ = (Index("ix_job_events_job", "job_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("evt"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    stage: Mapped[str | None] = mapped_column(String(64), default=None)
    # started | progress | completed | failed | skipped | cancelled | info
    event: Mapped[str] = mapped_column(String(16))
    message: Mapped[str | None] = mapped_column(Text, default=None)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
