"""Sidecar metadata for generated files.

Every generated file (thumbnail, proxy, future renders) gets a ``<name>.json``
next to it recording its source, the stage and the configuration used. The
association survives losing the database and moving the project.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.tracking.json_store import write_json


def short_hash(text: str, n: int = 10) -> str:
    return hashlib.sha1(text.encode(), usedforsecurity=False).hexdigest()[:n]


def clip_id_for(source_rel: str) -> str:
    """Deterministic clip id for a project-relative source path."""
    return f"clip_{short_hash(source_rel, 8)}"


def derived_name(source_rel: str, suffix: str) -> str:
    """Deterministic, collision-resistant file name for a derived file."""
    stem = Path(source_rel).stem[:60]
    return f"{stem}.{short_hash(source_rel)}{suffix}"


def write_sidecar(
    output: Path,
    *,
    source_rel: str,
    stage: str,
    config: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> Path:
    sidecar = output.with_name(output.name + ".json")
    write_json(
        sidecar,
        {
            "source": source_rel,
            "stage": stage,
            "config": config,
            "created_at": datetime.now(UTC).isoformat(),
            **(extra or {}),
        },
    )
    return sidecar
