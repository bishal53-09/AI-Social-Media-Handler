"""Append-only event log stored inside the project (``logs/events.jsonl``).

Gives every project a portable, human-readable audit trail of what happened to
its media (scans, probes, thumbnails, approvals, ...). Operational state such as
job progress stays in SQLite.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.security import redact


def append_event(project_root: Path, event_type: str, payload: dict[str, Any] | None = None) -> None:
    path = project_root / "logs" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "type": event_type,
        "payload": payload or {},
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(redact(json.dumps(record, ensure_ascii=False, default=str)) + "\n")
