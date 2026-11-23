"""Strict schemas for everything the model may return.

``extra="forbid"`` means any unexpected field (for example an attempted
``command`` or ``ffmpeg_args``) invalidates the whole response.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReframeView(Strict):
    """A virtual camera inside an equirectangular frame (degrees)."""

    yaw: float = Field(ge=-180, le=180, description="Horizontal angle; 0 = frame centre.")
    pitch: float = Field(ge=-90, le=90, description="Vertical angle; 0 = horizon.")
    fov: float = Field(ge=30, le=120, description="Horizontal field of view.")


class Scene(Strict):
    start: float = Field(ge=0, description="Seconds from clip start.")
    end: float = Field(ge=0)
    description: str = Field(max_length=500)
    interest: int = Field(ge=1, le=5, description="1 = filler, 5 = standout moment.")
    tags: list[str] = Field(default_factory=list, max_length=12)
    suggested_view: ReframeView | None = None


class FootageAnalysis(Strict):
    summary: str = Field(max_length=1500)
    scenes: list[Scene] = Field(max_length=100)
    notes: str | None = Field(default=None, max_length=1000)


class Highlight(Strict):
    clip_id: str = Field(max_length=64)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    score: float = Field(ge=0, le=1)
    title: str = Field(max_length=120)
    reason: str = Field(max_length=400)
    suggested_view: ReframeView | None = None


class HighlightList(Strict):
    highlights: list[Highlight] = Field(max_length=50)


class PlanSegment(Strict):
    source: str = Field(max_length=64, description="A clip id from the provided list.")
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    reframe: ReframeView | None = None


class EditPlan(Strict):
    format: Literal["9:16", "16:9", "1:1"]
    duration_target: float = Field(gt=0)
    segments: list[PlanSegment] = Field(min_length=1, max_length=100)
    rationale: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _finite(self) -> EditPlan:
        for seg in self.segments:
            for v in (seg.start, seg.end):
                if not math.isfinite(v):
                    raise ValueError("segment times must be finite")
        return self


class CaptionSet(Strict):
    title: str | None = Field(default=None, max_length=100)
    caption: str = Field(max_length=5000)
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    alt_text: str | None = Field(default=None, max_length=400)

    @field_validator("hashtags")
    @classmethod
    def _clean_tags(cls, tags: list[str]) -> list[str]:
        cleaned: list[str] = []
        for t in tags:
            t = "".join(ch for ch in t.lstrip("#") if ch.isalnum() or ch == "_")
            if t and t.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(t)
        return cleaned
