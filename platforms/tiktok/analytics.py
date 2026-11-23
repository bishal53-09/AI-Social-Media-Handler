"""TikTok analytics — not implemented.

Video metrics via the TikTok API (requires additional scopes and approval).

TODO(phase 6): implement with the official API and store results on the post.
"""

from __future__ import annotations

from app.core.exceptions import UnsupportedOperationError


class TikTokAnalytics:
    def fetch(self, *_args: object, **_kwargs: object) -> None:
        raise UnsupportedOperationError(
            "TikTok analytics are not implemented yet.",
            details={"platform": "tiktok"},
        )
