from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UTCDateTime, new_id, utcnow


class ContentPost(Base):
    """The user-facing *post*: one piece of content that may go to several platforms.

    Each platform it targets is a :class:`app.models.post.Post` (a "platform post")
    pointing back here through ``content_post_id``.
    """

    __tablename__ = "content_posts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("cpost"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    output_file: Mapped[str | None] = mapped_column(String(1024), default=None)
    caption: Mapped[str | None] = mapped_column(Text, default=None)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Comment(Base):
    """A comment on a platform post, as last seen on the platform (or written by us)."""

    __tablename__ = "comments"
    __table_args__ = (
        UniqueConstraint("post_id", "external_id"),
        Index("ix_comments_post_posted", "post_id", "posted_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("cmt"))
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(200))
    parent_external_id: Mapped[str | None] = mapped_column(String(200), default=None)
    author_name: Mapped[str | None] = mapped_column(String(300), default=None)
    author_external_id: Mapped[str | None] = mapped_column(String(200), default=None)
    text: Mapped[str] = mapped_column(Text)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    is_own: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    liked_by_me: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Set when a later sync no longer returns it (deleted on the platform).
    removed_remotely: Mapped[bool] = mapped_column(Boolean, default=False)


class MetricSnapshot(Base):
    """Analytics for one platform post at one point in time (history is kept)."""

    __tablename__ = "metric_snapshots"
    __table_args__ = (Index("ix_metric_snapshots_post_time", "post_id", "collected_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("snap"))
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class EngagementAction(Base):
    """Audit trail of every outward interaction (reply, like, hide, delete)."""

    __tablename__ = "engagement_actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("act"))
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    comment_external_id: Mapped[str | None] = mapped_column(String(200), default=None)
    action: Mapped[str] = mapped_column(String(32))
    # succeeded | failed
    outcome: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
