#!/usr/bin/env python3
"""Check required and optional tools (Python, FFmpeg, ffprobe, Node.js, ...).

Same checks as ``python -m app.cli doctor`` but dependency-focused: it does not
create the database. Exit code 1 if a required tool is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cli import run_checks

TOOLS = {"Python", "Git", "FFmpeg", "ffprobe", "Node.js", "npm"}


def main() -> int:
    failed = False
    for check in run_checks():
        if check.name not in TOOLS:
            continue
        print(f"{check.status.upper():<5} {check.name:<10} {check.detail}")
        if check.fix:
            print(f"      -> {check.fix}")
        failed |= check.status == "fail"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
