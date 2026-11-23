"""Instagram authentication settings.

Meta (Facebook) Login OAuth; Instagram Graph API for Instagram professional accounts.

TODO(phase 6): implement the authorization flow and token refresh, storing
tokens through ``app.core.security.CredentialVault``. Endpoints and scopes
below are a starting point; verify them against the current platform docs.
"""

from __future__ import annotations

from dataclasses import dataclass

from platforms.base import Credentials  # noqa: F401  (re-exported for adapters)


@dataclass(frozen=True)
class OAuthConfig:
    authorize_url: str = "https://www.facebook.com/dialog/oauth"
    token_url: str = "https://graph.facebook.com/oauth/access_token"  # noqa: S105 - public endpoint, not a secret
    scopes: tuple[str, ...] = (
        "instagram_basic",
        "instagram_content_publish",
        "pages_show_list",
        "pages_read_engagement",
    )
    env_vars: tuple[str, ...] = (
        "META_APP_ID",
        "META_APP_SECRET",
    )
