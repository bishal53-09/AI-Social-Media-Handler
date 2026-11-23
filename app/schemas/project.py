from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectSettings(BaseModel):
    default_camera: str | None = None
    color_profile: str | None = None
    platforms: list[str] = Field(default_factory=list)


class ProjectMetadata(BaseModel):
    """Shape of ``<project>/project.json`` (see ``config/schemas/project.schema.json``)."""

    schema_version: int = 1
    id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    timezone: str = "UTC"
    settings: ProjectSettings = Field(default_factory=ProjectSettings)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    path: str | None = Field(
        default=None,
        description="Absolute project directory. Defaults to <MEDIA_ROOT>/<slug>.",
    )
    description: str | None = Field(default=None, max_length=5000)
    default_camera: str | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    path: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectRead):
    exists_on_disk: bool
    settings: ProjectSettings | None = None
    day_count: int = 0
    media_count: int = 0


class ProjectList(BaseModel):
    items: list[ProjectRead]
    total: int


class DaySummary(BaseModel):
    date: date
    clip_count: int


class DayList(BaseModel):
    items: list[DaySummary]


class DayRead(BaseModel):
    date: date
    project_id: str
    notes: str | None = None
    clips: list[dict[str, Any]]
