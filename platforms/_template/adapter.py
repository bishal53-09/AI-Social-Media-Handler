"""Template for a new platform adapter. Copy, rename, implement what you can."""

from __future__ import annotations

from typing import ClassVar

from platforms.base import MediaLimits, PlatformAdapter


class ExampleAdapter(PlatformAdapter):
    name = "example"
    display_name = "Example"
    docs_url = "https://example.com/api-docs"
    env_vars: ClassVar[tuple[str, ...]] = ("EXAMPLE_CLIENT_ID", "EXAMPLE_CLIENT_SECRET")
    default_limits: ClassVar[dict[str, MediaLimits]] = {
        "video": MediaLimits(
            max_duration_seconds=60,
            aspect_ratios=("9:16",),
            max_file_size_mb=500,
            containers=("mp4",),
        ),
    }

    # TODO: override authenticate / refresh_credentials / publish / get_post_status /
    # get_analytics once they are implemented against the official API, and then
    # set ``publishing_implemented = True``.
