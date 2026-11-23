"""YouTube adapter.

Status: contract, configuration and media validation only. ``publish()``,
``authenticate()`` and the other network operations raise
``UnsupportedOperationError`` — see README.md for the API requirements.
"""

from __future__ import annotations

from typing import ClassVar

from platforms.base import Capability, MediaLimits, PlatformAdapter


class YouTubeAdapter(PlatformAdapter):
    name = "youtube"
    display_name = "YouTube"
    docs_url = "https://developers.google.com/youtube/v3/guides/uploading_a_video"
    env_vars: ClassVar[tuple[str, ...]] = (
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
    )
    api_capabilities: ClassVar[frozenset[Capability]] = frozenset(
        {
            Capability.PUBLISH,
            Capability.ANALYTICS,
            Capability.LIST_COMMENTS,
            Capability.REPLY_COMMENT,
            Capability.HIDE_COMMENT,
            Capability.DELETE_COMMENT,
            Capability.LIKE_POST,
        }
    )
    engagement_notes: ClassVar[str] = (
        "YouTube Data API: commentThreads/comments cover listing, replying, moderation and deletion; "
        "videos.rate covers liking a video. Liking individual comments is not offered. Verify against "
        "current docs and quota costs before implementing."
    )
    default_limits: ClassVar[dict[str, MediaLimits]] = {
        "video": MediaLimits(
            max_duration_seconds=43200,
            min_duration_seconds=1,
            aspect_ratios=("16:9", "9:16", "1:1", "4:3"),
            max_file_size_mb=262144,
            containers=("mp4", "mov", "mkv", "webm"),
        ),
        # Shorts use this same adapter with Shorts-specific limits/metadata.
        "shorts": MediaLimits(
            max_duration_seconds=180,
            min_duration_seconds=1,
            aspect_ratios=("9:16", "1:1"),
            max_file_size_mb=262144,
            containers=("mp4", "mov"),
        ),
    }
