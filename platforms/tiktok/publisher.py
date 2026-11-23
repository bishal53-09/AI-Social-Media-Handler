"""TikTok publishing — not implemented.

Initialise an upload, send the file (chunked), then poll publish status. Unaudited apps can only
post privately; public posting needs TikTok's app review/audit.

TODO(phase 6): implement against the official API only. Persist the upload
reference *before* the transfer finishes so a lost response can be reconciled
(``get_post_status``) instead of re-uploaded.
"""

from __future__ import annotations

from app.core.exceptions import UnsupportedOperationError


class TikTokPublisher:
    def publish(self, *_args: object, **_kwargs: object) -> None:
        raise UnsupportedOperationError(
            "TikTok publishing is not implemented yet.",
            details={"platform": "tiktok"},
        )
