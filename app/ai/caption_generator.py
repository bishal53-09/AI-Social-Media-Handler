"""Caption, title and hashtag generation (text only)."""

from __future__ import annotations

from app.ai.base import AIProvider, TextPart
from app.ai.prompts import load_prompt
from app.ai.schemas import CaptionSet, EditPlan

PLATFORM_CAPTION_LIMITS = {"instagram": 2200, "tiktok": 2200, "youtube": 5000}


class CaptionGenerator:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def generate(
        self,
        platform: str,
        summary: str,
        plan: EditPlan | None = None,
        tone: str = "friendly",
        max_hashtags: int = 8,
    ) -> CaptionSet:
        limit = PLATFORM_CAPTION_LIMITS.get(platform, 2200)
        text = (
            f"Platform: {platform} (caption limit {limit} characters)\n"
            f"Tone: {tone}\nMax hashtags: {max_hashtags}\n"
            f"Video summary: {summary}\n"
        )
        if plan:
            text += f"Format: {plan.format}, about {plan.duration_target:.0f}s.\n"
        result = self.provider.generate(
            system=load_prompt("captions"), parts=[TextPart(text)], response_model=CaptionSet
        )
        result.caption = result.caption[:limit]
        del result.hashtags[max_hashtags:]
        return result
