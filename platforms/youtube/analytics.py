"""YouTube analytics — not implemented.

YouTube Analytics / Data API statistics (views, likes, comments).

TODO(phase 6): implement with the official API and store results on the post.
"""

from __future__ import annotations

from app.core.exceptions import UnsupportedOperationError


class YouTubeAnalytics:
    def fetch(self, *_args: object, **_kwargs: object) -> None:
        raise UnsupportedOperationError(
            "YouTube analytics are not implemented yet.",
            details={"platform": "youtube"},
        )
