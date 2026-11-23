"""Atomic, schema-validated JSON files.

Project-level metadata is stored as JSON so a project folder stays portable and
inspectable. Writes are atomic (temp file + rename) so a crash never leaves a
half-written file. JSON is *not* used for concurrent job state — that is SQLite.
"""

from __future__ import annotations

import json
import os
import tempfile
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from app.core.exceptions import ValidationFailedError
from app.core.paths import SCHEMA_DIR

SCHEMA_NAMES = ("project", "day", "clip", "post")


@lru_cache(maxsize=1)
def _registry() -> Registry:
    registry: Registry = Registry()
    for name in SCHEMA_NAMES:
        doc = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
        registry = registry.with_resource(doc["$id"], Resource.from_contents(doc, default_specification=DRAFT202012))
    return registry


@cache
def _validator(name: str) -> Draft202012Validator:
    if name not in SCHEMA_NAMES:
        raise ValueError(f"Unknown schema '{name}'")
    doc = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(doc, registry=_registry(), format_checker=Draft202012Validator.FORMAT_CHECKER)


def validate_document(name: str, data: Any) -> None:
    """Validate ``data`` against ``config/schemas/<name>.schema.json``."""
    errors = sorted(_validator(name).iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.absolute_path) or "(root)"
        raise ValidationFailedError(
            f"Invalid {name} document at {where}: {first.message}",
            details={
                "errors": [
                    {"path": "/".join(str(p) for p in e.absolute_path), "message": e.message} for e in errors[:20]
                ]
            },
        )


def read_json(path: Path, schema: str | None = None) -> Any:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationFailedError(f"{path.name} is not valid JSON: {exc}") from exc
    if schema:
        validate_document(schema, data)
    return data


def write_json(path: Path, data: Any, schema: str | None = None) -> None:
    """Validate (optionally) then write ``data`` atomically."""
    if schema:
        validate_document(schema, data)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
