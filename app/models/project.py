from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UTCDateTime, utcnow


class Project(Base):
    """Registry entry for a project directory.

    The authoritative, portable metadata lives in ``<path>/project.json``; this
    row is an index so the API can list projects without scanning the disk.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
