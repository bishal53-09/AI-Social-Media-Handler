"""YouTube publishing — not implemented.

videos.insert with a resumable upload session; the session URI is the upload_reference to persist
for resuming/reconciling. Shorts are regular uploads whose vertical, <=3 min video is classified as
a Short; use the 'shorts' variant for metadata and presets, not a second implementation. API
projects that are unverified may be forced private.

TODO(phase 6): implement against the official API only. Persist the upload
reference *before* the transfer finishes so a lost response can be reconciled
(``get_post_status``) instead of re-uploaded.
"""

from __future__ import annotations

from app.core.exceptions import UnsupportedOperationError


class YouTubePublisher:
    def publish(self, *_args: object, **_kwargs: object) -> None:
        raise UnsupportedOperationError(
            "YouTube publishing is not implemented yet.",
            details={"platform": "youtube"},
        )
