"""Highlight selection from scene analyses (text only — no media is sent)."""

from __future__ import annotations

import json
from collections.abc import Mapping

from app.ai.base import AIProvider, TextPart
from app.ai.prompts import load_prompt
from app.ai.schemas import FootageAnalysis, HighlightList
from app.ai.validation import validate_highlights


class HighlightDetector:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def detect(
        self,
        analyses: Mapping[str, FootageAnalysis],
        durations: Mapping[str, float | None],
        max_highlights: int = 8,
    ) -> HighlightList:
        payload = {cid: a.model_dump(mode="json") for cid, a in analyses.items()}
        text = f"Return at most {max_highlights} highlights.\nAnalyses by clip_id:\n{json.dumps(payload, indent=1)}"
        result = self.provider.generate(
            system=load_prompt("highlights"), parts=[TextPart(text)], response_model=HighlightList
        )
        result = validate_highlights(result, durations)
        result.highlights.sort(key=lambda h: h.score, reverse=True)
        del result.highlights[max_highlights:]
        return result
