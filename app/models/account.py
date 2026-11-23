from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UTCDateTime, new_id, utcnow


class Account(Base):
    """A connected social account.

    Tokens are *not* stored here. ``credential_key`` points at an entry in the
    :class:`app.core.security.CredentialVault`, which can be encrypted at rest.
    """

    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("acct"))
    platform: Mapped[str] = mapped_column(String(32), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    external_account_id: Mapped[str | None] = mapped_column(String(200), default=None)
    credential_key: Mapped[str | None] = mapped_column(String(128), default=None)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
