from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UTCDateTime, new_id, utcnow


class Post(Base):
    """Persistent record of one *platform post* (one platform's copy of a ContentPost). See ``app.publishing.state``."""

    __tablename__ = "posts"
    __table_args__ = (Index("ix_posts_project_status", "project_id", "status"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("post"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    #: The user-facing post this platform post belongs to (null for legacy/standalone rows).
    content_post_id: Mapped[str | None] = mapped_column(
        ForeignKey("content_posts.id", ondelete="CASCADE"), default=None, index=True
    )
    platform: Mapped[str] = mapped_column(String(32))
    variant: Mapped[str | None] = mapped_column(String(32), default=None)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), default=None)
    output_file: Mapped[str] = mapped_column(String(1024))
    caption: Mapped[str | None] = mapped_column(Text, default=None)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(200), default=None)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    external_post_id: Mapped[str | None] = mapped_column(String(200), default=None)
    external_url: Mapped[str | None] = mapped_column(String(1024), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    analytics: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class PostAttempt(Base):
    """One upload attempt. The idempotency key and any platform-side reference
    are recorded *before* the upload starts so a lost response can be reconciled
    instead of blindly retried."""

    __tablename__ = "post_attempts"
    __table_args__ = (UniqueConstraint("post_id", "attempt"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("att"))
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    attempt: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    # in_progress | success | failed | unknown
    outcome: Mapped[str] = mapped_column(String(16), default="in_progress")
    idempotency_key: Mapped[str | None] = mapped_column(String(64), default=None)
    upload_reference: Mapped[str | None] = mapped_column(String(512), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
