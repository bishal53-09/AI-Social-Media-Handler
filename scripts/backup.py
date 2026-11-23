#!/usr/bin/env python3
"""Back up application state: the SQLite database and each project's metadata.

Media files (footage, proxies, renders) are NOT copied — they can be huge and
raw footage is immutable; back those up with your normal tools. Project
metadata (project.json, data/, logs/) is small and is included.

Usage: python scripts/backup.py [--output DIR] [project_dir ...]

Writes ``asmh-backup-<UTC timestamp>.tar.gz`` (mode 0600) and refuses to
overwrite an existing archive.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.paths import expand

METADATA_DIRS = ("data", "logs")


def backup_database(url: str, dest: Path) -> bool:
    db_path = make_url(url).database
    if not db_path or db_path == ":memory:" or not Path(db_path).exists():
        return False
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)  # consistent snapshot even while the app is running
        finally:
            dst.close()
    finally:
        src.close()
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("projects", nargs="*", help="Project directories to include.")
    parser.add_argument("--output", default=str(get_settings().data_path / "backups"))
    args = parser.parse_args(argv)

    out_dir = expand(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = out_dir / f"asmh-backup-{stamp}.tar.gz"
    if archive.exists():
        print(f"Refusing to overwrite {archive}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp, tarfile.open(archive, "w:gz") as tar:
        snapshot = Path(tmp) / "app.db"
        if backup_database(get_settings().resolved_database_url, snapshot):
            tar.add(snapshot, arcname="app.db")
        for project in args.projects:
            root = expand(project)
            if not (root / "project.json").is_file():
                print(f"Skipping {root}: no project.json", file=sys.stderr)
                continue
            tar.add(root / "project.json", arcname=f"projects/{root.name}/project.json")
            for sub in METADATA_DIRS:
                if (root / sub).is_dir():
                    tar.add(root / sub, arcname=f"projects/{root.name}/{sub}")
    os.chmod(archive, 0o600)
    print(f"Backup written: {archive} ({archive.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
