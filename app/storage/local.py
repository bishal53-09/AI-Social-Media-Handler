"""Local-filesystem storage rooted at a directory (path-traversal safe)."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

from app.core.exceptions import ConflictError, NotFoundError
from app.core.paths import safe_join
from app.storage.base import Storage


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return safe_join(self.root, key)

    def put_file(self, key: str, source: Path, *, overwrite: bool = False) -> None:
        dest = self._path(key)
        if dest.exists() and not overwrite:
            raise ConflictError(f"'{key}' already exists; refusing to overwrite.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.partial")
        try:
            shutil.copyfile(source, tmp)
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def open(self, key: str) -> Path:
        path = self._path(key)
        if not path.is_file():
            raise NotFoundError(f"'{key}' not found.")
        return path

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def list(self, prefix: str = "") -> Iterator[str]:
        base = self._path(prefix) if prefix else self.root
        if not base.exists():
            return
        for p in sorted(base.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                yield p.relative_to(self.root).as_posix()
