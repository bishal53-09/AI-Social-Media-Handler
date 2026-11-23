from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MediaAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    relative_path: str
    kind: str
    stage: str
    day: str | None = None
    size_bytes: int
    sha256: str | None = None
    media_type: str
    camera: str | None = None
    probe: dict[str, Any] | None = None
    probe_error: str | None = None
    thumbnail_path: str | None = None
    proxy_path: str | None = None
    source_asset_id: str | None = None
    missing: bool
    created_at: datetime
    updated_at: datetime


class MediaList(BaseModel):
    items: list[MediaAssetRead]
    total: int
    limit: int
    offset: int


class ScanRequest(BaseModel):
    probe: bool = Field(default=True, description="Run ffprobe on new or changed files.")


class ScanResult(BaseModel):
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    missing: int = 0
    skipped: int = 0
    probed: int = 0
    probe_failed: int = 0
    days_written: int = 0
    warnings: list[str] = Field(default_factory=list)
