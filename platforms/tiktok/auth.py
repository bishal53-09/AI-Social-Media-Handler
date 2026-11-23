"""TikTok authentication settings.

TikTok Login Kit OAuth 2.0 with the Content Posting API.

TODO(phase 6): implement the authorization flow and token refresh, storing
tokens through ``app.core.security.CredentialVault``. Endpoints and scopes
below are a starting point; verify them against the current platform docs.
"""

from __future__ import annotations

from dataclasses import dataclass

from platforms.base import Credentials  # noqa: F401  (re-exported for adapters)


@dataclass(frozen=True)
class OAuthConfig:
    authorize_url: str = "https://www.tiktok.com/v2/auth/authorize/"
    token_url: str = "https://open.tiktokapis.com/v2/oauth/token/"  # noqa: S105 - public endpoint, not a secret
    scopes: tuple[str, ...] = (
        "user.info.basic",
        "video.upload",
        "video.publish",
    )
    env_vars: tuple[str, ...] = (
        "TIKTOK_CLIENT_KEY",
        "TIKTOK_CLIENT_SECRET",
    )
