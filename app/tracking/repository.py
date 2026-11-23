"""Read/write access to a project's JSON metadata (project.json, days, index)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.paths import safe_join
from app.tracking.json_store import read_json, write_json

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_day_string(value: str) -> str:
    if not _DATE_RE.match(value):
        raise ValidationFailedError("Date must be formatted YYYY-MM-DD.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValidationFailedError("Not a valid calendar date.") from exc
    return value


class ProjectRepository:
    """JSON metadata for one project directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    # -- project.json --------------------------------------------------------

    @property
    def project_file(self) -> Path:
        return self.root / "project.json"

    def exists(self) -> bool:
        return self.project_file.is_file()

    def read_project(self) -> dict[str, Any]:
        if not self.exists():
            raise NotFoundError(f"No project.json in {self.root}")
        data: dict[str, Any] = read_json(self.project_file, "project")
        return data

    def write_project(self, data: dict[str, Any]) -> None:
        write_json(self.project_file, data, "project")

    # -- days ----------------------------------------------------------------

    @property
    def days_dir(self) -> Path:
        return self.root / "data" / "days"

    def list_days(self) -> list[dict[str, Any]]:
        if not self.days_dir.is_dir():
            return []
        out = []
        for f in sorted(self.days_dir.glob("*.json")):
            if not _DATE_RE.match(f.stem):
                continue
            try:
                doc = read_json(f)
            except ValidationFailedError:
                continue
            out.append({"date": f.stem, "clip_count": len(doc.get("clips", []))})
        return out

    def read_day(self, day: str) -> dict[str, Any]:
        validate_day_string(day)
        path = safe_join(self.days_dir, f"{day}.json")
        if not path.is_file():
            raise NotFoundError(f"No metadata for day {day}")
        data: dict[str, Any] = read_json(path, "day")
        return data

    def write_day(self, day: str, doc: dict[str, Any]) -> None:
        validate_day_string(day)
        write_json(safe_join(self.days_dir, f"{day}.json"), doc, "day")

    def touch_index(self, **extra: Any) -> None:
        index = self.root / "data" / "index.json"
        data: dict[str, Any] = read_json(index) if index.is_file() else {}
        data.update(extra)
        data["updated_at"] = datetime.now(UTC).isoformat()
        write_json(index, data)
