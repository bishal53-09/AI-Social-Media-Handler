"""Instagram analytics — not implemented.

Instagram insights via the Graph API (reach, plays, likes, comments, shares, saves).

TODO(phase 6): implement with the official API and store results on the post.
"""

from __future__ import annotations

from app.core.exceptions import UnsupportedOperationError


class InstagramAnalytics:
    def fetch(self, *_args: object, **_kwargs: object) -> None:
        raise UnsupportedOperationError(
            "Instagram analytics are not implemented yet.",
            details={"platform": "instagram"},
        )
