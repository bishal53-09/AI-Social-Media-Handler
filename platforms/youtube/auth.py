"""YouTube authentication settings.

Google OAuth 2.0 (installed-app / loopback flow) with the YouTube Data API v3.

TODO(phase 6): implement the authorization flow and token refresh, storing
tokens through ``app.core.security.CredentialVault``. Endpoints and scopes
below are a starting point; verify them against the current platform docs.
"""

from __future__ import annotations

from dataclasses import dataclass

from platforms.base import Credentials  # noqa: F401  (re-exported for adapters)


@dataclass(frozen=True)
class OAuthConfig:
    authorize_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url: str = "https://oauth2.googleapis.com/token"  # noqa: S105 - public endpoint, not a secret
    scopes: tuple[str, ...] = (
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    )
    env_vars: tuple[str, ...] = (
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
    )
