"""Stage contract shared by every pipeline stage.

A stage:

* receives a :class:`StageContext` (project root, one source file, accumulated
  results of earlier stages, configuration, progress + cancellation hooks);
* returns a :class:`StageResult` with its outputs and the configuration it
  actually used (recorded in the job trace);
* never modifies the source file and writes only inside the project;
* is testable on its own — it touches neither the database nor the API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import AppConfig
from app.core.exceptions import CancelledError
from app.core.paths import safe_join


def _no_progress(_fraction: float, _message: str | None = None) -> None:
    return None


def _never_cancelled() -> bool:
    return False


@dataclass
class StageContext:
    project_root: Path
    source_rel: str  # path relative to project root, POSIX style
    kind: str  # "video" | "image"
    config: AppConfig
    media_type: str = "unknown"
    # Outputs of earlier stages for this source, keyed by stage name.
    previous: dict[str, dict[str, Any]] = field(default_factory=dict)
    force: bool = False
    progress: Callable[[float, str | None], None] = _no_progress
    is_cancelled: Callable[[], bool] = _never_cancelled

    @property
    def source_path(self) -> Path:
        return safe_join(self.project_root, self.source_rel)

    def check_cancelled(self) -> None:
        if self.is_cancelled():
            raise CancelledError("Cancelled by user.")


@dataclass
class StageResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    config_used: dict[str, Any] = field(default_factory=dict)
    message: str | None = None
    skipped: bool = False


class Stage(ABC):
    name: str = ""
    #: ``False`` for documented extension points that are not built yet; the
    #: orchestrator refuses to run them rather than pretend success.
    implemented: bool = True
    #: Which source kinds the stage applies to.
    kinds: tuple[str, ...] = ("video",)

    @abstractmethod
    def run(self, ctx: StageContext) -> StageResult: ...
