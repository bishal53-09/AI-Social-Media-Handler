"""Edit planning: highlights → validated, executable-by-software edit plan."""

from __future__ import annotations

import json
from collections.abc import Mapping

from app.ai.base import AIProvider, TextPart
from app.ai.prompts import load_prompt
from app.ai.schemas import EditPlan, HighlightList
from app.ai.validation import validate_edit_plan
from app.core.config import EditPlanConfig


class EditPlanner:
    def __init__(self, provider: AIProvider, limits: EditPlanConfig) -> None:
        self.provider = provider
        self.limits = limits

    def plan(
        self,
        highlights: HighlightList,
        durations: Mapping[str, float | None],
        *,
        fmt: str = "9:16",
        duration_target: float = 35.0,
    ) -> tuple[EditPlan, list[str]]:
        text = (
            f"Allowed formats: {', '.join(self.limits.allowed_formats)}; requested: {fmt}.\n"
            f"duration_target: {duration_target}\n"
            f"Clip durations (seconds): {json.dumps(dict(durations))}\n"
            f"Highlights:\n{json.dumps(highlights.model_dump(mode='json'), indent=1)}"
        )
        plan = self.provider.generate(system=load_prompt("edit_plan"), parts=[TextPart(text)], response_model=EditPlan)
        warnings = validate_edit_plan(plan, durations, self.limits)
        return plan, warnings
