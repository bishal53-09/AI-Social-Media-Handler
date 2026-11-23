"""Storage interface. Keys are relative POSIX paths ("exports/drafts/a.mp4")."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path


class Storage(ABC):
    @abstractmethod
    def put_file(self, key: str, source: Path, *, overwrite: bool = False) -> None:
        """Copy ``source`` into storage under ``key``. Must not overwrite by default."""

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def open(self, key: str) -> Path:
        """Return a local path for reading (downloading first if remote)."""

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def list(self, prefix: str = "") -> Iterator[str]: ...
