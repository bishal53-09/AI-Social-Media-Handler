#!/usr/bin/env python3
"""Create or upgrade the SQLite schema using Alembic.

Usage: python scripts/migrate_data.py [revision]      (default: head)

This only touches the application database. It never modifies project folders.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.database.migrate import upgrade_database


def main(argv: list[str]) -> int:
    url = get_settings().resolved_database_url
    upgrade_database(url, argv[0] if argv else "head")
    print(f"Database is up to date: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
