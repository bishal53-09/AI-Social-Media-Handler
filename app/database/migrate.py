"""Programmatic Alembic helpers (no alembic.ini required)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade_database(url: str, revision: str = "head") -> None:
    """Create or upgrade the schema to ``revision``."""
    command.upgrade(alembic_config(url), revision)
