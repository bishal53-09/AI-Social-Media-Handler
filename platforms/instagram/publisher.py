"""Instagram publishing — not implemented.

Create a media container from a *publicly reachable* video URL, poll its status until FINISHED, then
call media_publish. Because the media must be hosted at a public URL, the S3_* settings (or another
host) are required; footage is never made public automatically.

TODO(phase 6): implement against the official API only. Persist the upload
reference *before* the transfer finishes so a lost response can be reconciled
(``get_post_status``) instead of re-uploaded.
"""

from __future__ import annotations

from app.core.exceptions import UnsupportedOperationError


class InstagramPublisher:
    def publish(self, *_args: object, **_kwargs: object) -> None:
        raise UnsupportedOperationError(
            "Instagram publishing is not implemented yet.",
            details={"platform": "instagram"},
        )
