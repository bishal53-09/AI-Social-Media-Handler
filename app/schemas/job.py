from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JobType = Literal["media.scan", "pipeline.process"]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class JobCreate(BaseModel):
    type: JobType
    project_id: str
    params: dict[str, Any] = Field(
        default_factory=dict,
        description=("media.scan: {probe: bool}. pipeline.process: {stages: [str], asset_ids: [str], force: bool}."),
    )


class JobEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    stage: str | None = None
    event: str
    message: str | None = None
    data: dict[str, Any] | None = None
    created_at: datetime


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str | None = None
    type: str
    status: JobStatus
    progress: float
    current_stage: str | None = None
    params: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobDetail(JobRead):
    events: list[JobEventRead] = Field(default_factory=list)


class JobList(BaseModel):
    items: list[JobRead]
    total: int
