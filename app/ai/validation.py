"""Safety checks applied to AI output *after* schema validation.

The schema guarantees shape; these checks guarantee the plan is sane against
real data (known clips, real durations, configured limits).
"""

from __future__ import annotations

from collections.abc import Mapping

from app.ai.schemas import EditPlan, FootageAnalysis, HighlightList
from app.core.config import EditPlanConfig
from app.core.exceptions import AIResponseError

EPS = 0.05


def validate_analysis(analysis: FootageAnalysis, duration: float | None) -> list[str]:
    problems: list[str] = []
    for i, s in enumerate(analysis.scenes):
        if s.end <= s.start:
            problems.append(f"scene {i}: end must be after start")
        if duration is not None and s.end > duration + EPS:
            problems.append(f"scene {i}: ends at {s.end}s after the clip ({duration}s)")
    if problems:
        raise AIResponseError("AI analysis failed validation.", details={"problems": problems})
    return problems


def validate_highlights(result: HighlightList, durations: Mapping[str, float | None]) -> HighlightList:
    problems: list[str] = []
    for i, h in enumerate(result.highlights):
        if h.clip_id not in durations:
            problems.append(f"highlight {i}: unknown clip '{h.clip_id}'")
            continue
        d = durations[h.clip_id]
        if h.end <= h.start:
            problems.append(f"highlight {i}: end must be after start")
        elif d is not None and h.end > d + EPS:
            problems.append(f"highlight {i}: ends after the clip ({d}s)")
    if problems:
        raise AIResponseError("AI highlights failed validation.", details={"problems": problems})
    return result


def validate_edit_plan(plan: EditPlan, durations: Mapping[str, float | None], limits: EditPlanConfig) -> list[str]:
    """Reject unsafe plans; return non-fatal warnings.

    ``durations`` maps allowed source clip ids to their duration. A ``source``
    that is not a key is rejected, so a plan cannot reference arbitrary files.
    """
    problems: list[str] = []
    warnings: list[str] = []
    if plan.format not in limits.allowed_formats:
        problems.append(f"format '{plan.format}' is not allowed")
    if len(plan.segments) > limits.max_segments:
        problems.append(f"{len(plan.segments)} segments exceeds the limit of {limits.max_segments}")
    total = 0.0
    lo, hi = limits.fov_range
    for i, seg in enumerate(plan.segments):
        if seg.source not in durations:
            problems.append(f"segment {i}: unknown source '{seg.source}'")
            continue
        if seg.end <= seg.start:
            problems.append(f"segment {i}: end must be after start")
            continue
        d = durations[seg.source]
        if d is not None and seg.end > d + EPS:
            problems.append(f"segment {i}: ends at {seg.end}s but '{seg.source}' is {d}s long")
        if seg.reframe and not lo <= seg.reframe.fov <= hi:
            problems.append(f"segment {i}: fov {seg.reframe.fov} outside {lo}-{hi}")
        total += seg.end - seg.start
    if total > limits.max_duration_seconds:
        problems.append(f"total duration {total:.0f}s exceeds {limits.max_duration_seconds:.0f}s")
    if plan.duration_target and abs(total - plan.duration_target) / plan.duration_target > 0.25:
        warnings.append(f"segments total {total:.1f}s, more than 25% away from the target {plan.duration_target}s")
    if problems:
        raise AIResponseError("AI edit plan failed validation.", details={"problems": problems})
    return warnings
