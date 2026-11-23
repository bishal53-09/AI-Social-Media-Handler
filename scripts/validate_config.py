#!/usr/bin/env python3
"""Validate configuration, JSON schemas and (optionally) a project's JSON metadata.

Usage:
    python scripts/validate_config.py                 # config/*.yaml + schemas
    python scripts/validate_config.py ~/Content/Trip  # also validate that project's JSON

Exit code 0 when everything is valid, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jsonschema import Draft202012Validator

from app.core.config import get_settings, load_app_config
from app.core.exceptions import AppError
from app.core.paths import SCHEMA_DIR
from app.pipeline.orchestrator import STAGES
from app.tracking.json_store import read_json


def main(argv: list[str]) -> int:
    problems: list[str] = []

    try:
        cfg = load_app_config(get_settings().config_path)
        print(f"ok   config/*.yaml ({len(cfg.pipeline.stages)} stages, {len(cfg.export_presets)} presets)")
        for stage in cfg.pipeline.stages:
            known = STAGES.get(stage.name)
            if known is None:
                problems.append(f"pipeline.yaml names unknown stage '{stage.name}'")
            elif known.implemented != stage.implemented:
                problems.append(f"pipeline.yaml says {stage.name}.implemented={stage.implemented}, code disagrees")
    except AppError as exc:
        problems.append(exc.message)

    for schema in sorted(SCHEMA_DIR.glob("*.schema.json")):
        try:
            Draft202012Validator.check_schema(json.loads(schema.read_text()))
            print(f"ok   schema {schema.name}")
        except Exception as exc:
            problems.append(f"{schema.name}: {exc}")

    if argv:
        root = Path(argv[0]).expanduser().resolve()
        try:
            read_json(root / "project.json", "project")
            print("ok   project.json")
        except AppError as exc:
            problems.append(f"project.json: {exc.message}")
        for day in sorted((root / "data" / "days").glob("*.json")):
            try:
                read_json(day, "day")
                print(f"ok   data/days/{day.name}")
            except AppError as exc:
                problems.append(f"data/days/{day.name}: {exc.message}")

    for p in problems:
        print(f"FAIL {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
