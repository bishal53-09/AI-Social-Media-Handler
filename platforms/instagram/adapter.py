"""Instagram adapter.

Status: contract, configuration and media validation only. ``publish()``,
``authenticate()`` and the other network operations raise
``UnsupportedOperationError`` — see README.md for the API requirements.
"""

from __future__ import annotations

from typing import ClassVar

from platforms.base import Capability, MediaLimits, PlatformAdapter


class InstagramAdapter(PlatformAdapter):
    name = "instagram"
    display_name = "Instagram"
    docs_url = "https://developers.facebook.com/docs/instagram-platform/content-publishing/"
    env_vars: ClassVar[tuple[str, ...]] = (
        "META_APP_ID",
        "META_APP_SECRET",
    )
    api_capabilities: ClassVar[frozenset[Capability]] = frozenset(
        {
            Capability.PUBLISH,
            Capability.ANALYTICS,
            Capability.LIST_COMMENTS,
            Capability.REPLY_COMMENT,
            Capability.HIDE_COMMENT,
            Capability.DELETE_COMMENT,
        }
    )
    engagement_notes: ClassVar[str] = (
        "Instagram Graph API (professional accounts): comments can be listed, replied to, hidden and deleted. "
        "Liking comments or media is not offered. Requires app review and permissions; verify current docs."
    )
    default_limits: ClassVar[dict[str, MediaLimits]] = {
        "reels": MediaLimits(
            max_duration_seconds=900,
            min_duration_seconds=3,
            aspect_ratios=("9:16",),
            max_file_size_mb=1024,
            containers=("mp4", "mov"),
        ),
        "carousel": MediaLimits(
            max_file_size_mb=1024,
            containers=("mp4", "mov", "jpg", "jpeg", "png"),
            max_files=10,
        ),
    }
