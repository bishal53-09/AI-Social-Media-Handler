from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UTCDateTime, new_id, utcnow


class MediaAsset(Base):
    """An indexed media file inside a project.

    ``relative_path`` is relative to the project root so the index stays valid
    when a project is moved between computers. ``source_asset_id`` links
    generated files (thumbnails, proxies, renders) back to their source.
    """

    __tablename__ = "media_assets"
    __table_args__ = (
        UniqueConstraint("project_id", "relative_path"),
        Index("ix_media_assets_project_kind", "project_id", "kind"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("media"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    relative_path: Mapped[str] = mapped_column(String(1024))
    # video | image
    kind: Mapped[str] = mapped_column(String(16))
    # raw | stitched | proxy | thumbnail | processed | ready | posted | other
    stage: Mapped[str] = mapped_column(String(32), default="other")
    day: Mapped[str | None] = mapped_column(String(10), default=None)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    mtime: Mapped[float] = mapped_column(default=0.0)
    sha256: Mapped[str | None] = mapped_column(String(64), default=None)
    # flat (any ordinary video) | 360 | 360-stitched | unknown (not probed yet)
    media_type: Mapped[str] = mapped_column(String(16), default="unknown")
    camera: Mapped[str | None] = mapped_column(String(100), default=None)
    probe: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    probe_error: Mapped[str | None] = mapped_column(String(2000), default=None)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), default=None)
    proxy_path: Mapped[str | None] = mapped_column(String(1024), default=None)
    source_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL"), default=None
    )
    missing: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
