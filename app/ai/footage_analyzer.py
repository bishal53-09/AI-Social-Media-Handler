"""Footage analysis: sampled frames + metadata → validated scene analysis."""

from __future__ import annotations

from typing import Any

from app.ai.base import AIProvider, ImagePart, Part, TextPart
from app.ai.frames import SampledFrame
from app.ai.prompts import load_prompt
from app.ai.schemas import FootageAnalysis
from app.ai.validation import validate_analysis


def describe_clip(clip_id: str, probe: dict[str, Any], media_type: str) -> str:
    """Technical metadata only — never the file path or any user-identifying text."""
    fields = {
        "clip_id": clip_id,
        "type": media_type,
        "duration_seconds": probe.get("duration"),
        "resolution": f"{probe.get('width')}x{probe.get('height')}",
        "fps": probe.get("fps"),
        "equirectangular_360": bool(probe.get("is_equirectangular")),
        "has_audio": probe.get("has_audio"),
    }
    return "\n".join(f"{k}: {v}" for k, v in fields.items())


class FootageAnalyzer:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def analyze(
        self, clip_id: str, probe: dict[str, Any], media_type: str, frames: list[SampledFrame]
    ) -> FootageAnalysis:
        parts: list[Part] = [TextPart(describe_clip(clip_id, probe, media_type))]
        for f in frames:
            parts.append(TextPart(f"Frame at {f.timestamp:.1f}s:"))
            parts.append(ImagePart(f.jpeg))
        result = self.provider.generate(
            system=load_prompt("footage_analysis"), parts=parts, response_model=FootageAnalysis
        )
        validate_analysis(result, probe.get("duration"))
        return result
