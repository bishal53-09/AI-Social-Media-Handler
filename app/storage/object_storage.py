"""S3-compatible object storage — extension point (not implemented).

Needed later because Instagram's publishing API requires media at a public URL.
When implemented it must: use the ``S3_*`` settings, never make objects public
without an explicit per-upload approval, and use short-lived pre-signed URLs.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from app.core.exceptions import UnsupportedOperationError
from app.storage.base import Storage


class ObjectStorage(Storage):
    """TODO(phase 6): implement with boto3 (or another S3 client)."""

    def _unsupported(self) -> UnsupportedOperationError:
        return UnsupportedOperationError("Object storage is not implemented yet (Phase 6).")

    def put_file(self, key: str, source: Path, *, overwrite: bool = False) -> None:
        raise self._unsupported()

    def exists(self, key: str) -> bool:
        raise self._unsupported()

    def open(self, key: str) -> Path:
        raise self._unsupported()

    def delete(self, key: str) -> None:
        raise self._unsupported()

    def list(self, prefix: str = "") -> Iterator[str]:
        raise self._unsupported()
