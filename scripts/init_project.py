#!/usr/bin/env python3
"""Create a project (same as ``python -m app.cli init-project``).

Usage: python scripts/init_project.py --name "My Project" --path ~/Content/MyProject
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cli import app

if __name__ == "__main__":
    app(["init-project", *sys.argv[1:]])
