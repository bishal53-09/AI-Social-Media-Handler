"""Filesystem locations and path-safety helpers.

All code that turns user- or API-supplied strings into filesystem paths must go
through :func:`safe_join` or :func:`ensure_within` so that requests cannot read
or write outside the directory they are scoped to.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.core.exceptions import PathSecurityError

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
SCHEMA_DIR = CONFIG_DIR / "schemas"


def expand(path: str | os.PathLike[str], base: Path | None = None) -> Path:
    """Expand ``~`` and make ``path`` absolute (relative to ``base`` or the repo root)."""
    p = Path(os.path.expanduser(os.fspath(path)))
    if not p.is_absolute():
        p = (base or REPO_ROOT) / p
    return p.resolve()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def ensure_within(path: Path, root: Path) -> Path:
    """Return ``path`` resolved, or raise if it is not inside ``root``.

    Symlinks are resolved before the check, so a link pointing outside the root
    is rejected too.
    """
    resolved = path.resolve()
    if not is_within(resolved, root):
        raise PathSecurityError(
            "Path is outside the allowed directory.",
            details={"path": str(path), "root": str(root)},
        )
    return resolved


def safe_join(root: Path, *parts: str) -> Path:
    """Join untrusted relative ``parts`` onto ``root`` and refuse escapes.

    Absolute parts, ``..`` segments that leave the root, NUL bytes and
    symlinks that resolve outside the root are all rejected.
    """
    for part in parts:
        if "\x00" in part:
            raise PathSecurityError("Path contains a NUL byte.")
        if os.path.isabs(part) or part.startswith("~"):
            raise PathSecurityError("Absolute paths are not allowed here.", details={"path": part})
    candidate = root.joinpath(*parts)
    return ensure_within(candidate, root)


def to_project_relative(path: Path, project_root: Path) -> str:
    """Return a POSIX-style path relative to the project root (for portable JSON)."""
    return ensure_within(path, project_root).relative_to(project_root.resolve()).as_posix()
