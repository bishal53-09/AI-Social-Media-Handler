"""Instagram adapter.

Status: contract, configuration and media validation only. ``publish()``,
``authenticate()`` and the other network operations raise
``UnsupportedOperationError`` — see README.md for the API requirements.
"""

from __future__ import annotations

from typing import ClassVar

from platforms.base import MediaLimits, PlatformAdapter


class InstagramAdapter(PlatformAdapter):
    name = "instagram"
    display_name = "Instagram"
    docs_url = "https://developers.facebook.com/docs/instagram-platform/content-publishing/"
    env_vars: ClassVar[tuple[str, ...]] = (
        "META_APP_ID",
        "META_APP_SECRET",
    )
    default_limits: ClassVar[dict[str, MediaLimits]] = {
        "reels": MediaLimits(
            max_duration_seconds=900,
            min_duration_seconds=3,
            aspect_ratios=("9:16",),
            max_file_size_mb=1024,
            containers=("mp4", "mov"),
        ),
    }
