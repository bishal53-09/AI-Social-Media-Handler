from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.post import PostAttemptRead


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    post_id: str
    external_id: str
    parent_external_id: str | None = None
    author_name: str | None = None
    author_external_id: str | None = None
    text: str
    like_count: int
    reply_count: int
    posted_at: datetime | None = None
    fetched_at: datetime
    is_own: bool
    hidden: bool
    liked_by_me: bool
    removed_remotely: bool


class CommentList(BaseModel):
    items: list[CommentRead]
    total: int


class ReplyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class LikeRequest(BaseModel):
    like: bool = True


class HideRequest(BaseModel):
    hidden: bool = True


class EngagementActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    comment_external_id: str | None = None
    action: str
    outcome: str
    detail: str | None = None
    error: str | None = None
    created_at: datetime


class MetricSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    collected_at: datetime
    metrics: dict[str, Any]


class PartReportRead(BaseModel):
    status: str
    count: int = 0
    message: str | None = None


class SyncReportRead(BaseModel):
    post_id: str
    comments: PartReportRead
    analytics: PartReportRead
    synced_at: datetime


class PlatformPostSummary(BaseModel):
    id: str
    platform: str
    platform_name: str
    variant: str | None = None
    status: str
    external_post_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    scheduled_at: datetime | None = None
    error: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    metrics_collected_at: datetime | None = None
    comment_count: int = 0


class PlatformPostDetail(PlatformPostSummary):
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    approved_by: str | None = None
    approved_at: datetime | None = None
    attempts: list[PostAttemptRead] = Field(default_factory=list)
    #: capability name → implemented | planned | unavailable
    capabilities: dict[str, str] = Field(default_factory=dict)
    engagement_notes: str = ""
    snapshots: list[MetricSnapshotRead] = Field(default_factory=list)
    actions: list[EngagementActionRead] = Field(default_factory=list)


class PlatformTarget(BaseModel):
    platform: str = Field(min_length=1, max_length=32)
    variant: str | None = Field(default=None, max_length=32)


class ContentPostCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=200)
    output_file: str = Field(min_length=1, max_length=1024)
    caption: str | None = Field(default=None, max_length=5000)
    hashtags: list[str] = Field(default_factory=list, max_length=60)
    platforms: list[PlatformTarget] = Field(min_length=1, max_length=20)
    scheduled_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be blank")
        return v

    @field_validator("scheduled_at")
    @classmethod
    def _aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone offset (ISO 8601).")
        return v


class ContentPostSummary(BaseModel):
    id: str
    project_id: str
    title: str
    output_file: str | None = None
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    created_at: datetime
    platform_posts: list[PlatformPostSummary]
    #: Sum of additive metrics (views, likes, comments, shares, saves, ...) over platforms with data.
    totals: dict[str, float | int] = Field(default_factory=dict)
    comment_total: int = 0


class ContentPostDetail(ContentPostSummary):
    platform_posts: list[PlatformPostDetail]  # type: ignore[assignment]


class ContentPostList(BaseModel):
    items: list[ContentPostSummary]
    total: int


class PlatformBreakdown(BaseModel):
    platform: str
    platform_name: str
    published_posts: int
    posts_with_data: int
    totals: dict[str, float | int]


class TopPost(BaseModel):
    content_post_id: str | None
    title: str
    platform: str
    platform_post_id: str
    external_url: str | None = None
    metrics: dict[str, Any]


class AnalyticsOverview(BaseModel):
    published_posts: int
    posts_with_data: int
    totals: dict[str, float | int]
    by_platform: list[PlatformBreakdown]
    top_posts: list[TopPost]
    last_collected_at: datetime | None = None
