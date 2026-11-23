from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PostCreate(BaseModel):
    project_id: str
    platform: str
    variant: str | None = None
    account_id: str | None = None
    output_file: str = Field(min_length=1, max_length=1024)
    caption: str | None = Field(default=None, max_length=5000)
    hashtags: list[str] = Field(default_factory=list, max_length=60)
    scheduled_at: datetime | None = None

    @field_validator("scheduled_at")
    @classmethod
    def _aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone offset (ISO 8601).")
        return v


class PostAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attempt: int
    started_at: datetime
    finished_at: datetime | None = None
    outcome: str
    idempotency_key: str | None = None
    upload_reference: str | None = None
    error: str | None = None


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    platform: str
    variant: str | None = None
    account_id: str | None = None
    output_file: str
    caption: str | None = None
    hashtags: list[str]
    scheduled_at: datetime | None = None
    status: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    external_post_id: str | None = None
    external_url: str | None = None
    error: str | None = None
    published_at: datetime | None = None
    analytics: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class PostList(BaseModel):
    items: list[PostRead]
    total: int
