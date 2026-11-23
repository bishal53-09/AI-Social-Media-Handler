"""TikTok adapter.

Status: contract, configuration and media validation only. ``publish()``,
``authenticate()`` and the other network operations raise
``UnsupportedOperationError`` — see README.md for the API requirements.
"""

from __future__ import annotations

from typing import ClassVar

from platforms.base import Capability, MediaLimits, PlatformAdapter


class TikTokAdapter(PlatformAdapter):
    name = "tiktok"
    display_name = "TikTok"
    docs_url = "https://developers.tiktok.com/doc/content-posting-api-get-started"
    env_vars: ClassVar[tuple[str, ...]] = (
        "TIKTOK_CLIENT_KEY",
        "TIKTOK_CLIENT_SECRET",
    )
    api_capabilities: ClassVar[frozenset[Capability]] = frozenset({Capability.PUBLISH, Capability.ANALYTICS})
    engagement_notes: ClassVar[str] = (
        "TikTok's public Content Posting/Display APIs expose basic video statistics. Comment management and "
        "liking are not available there; they depend on restricted business/partner programs. Verify current docs."
    )
    default_limits: ClassVar[dict[str, MediaLimits]] = {
        "video": MediaLimits(
            max_duration_seconds=600,
            min_duration_seconds=3,
            aspect_ratios=("9:16", "1:1", "16:9"),
            max_file_size_mb=4096,
            containers=("mp4", "mov", "webm"),
        ),
    }
