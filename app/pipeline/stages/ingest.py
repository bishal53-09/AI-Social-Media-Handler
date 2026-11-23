"""Stage 1 — ingestion: verify the source and record an immutable fingerprint.

The source file is opened read-only. The SHA-256 recorded here lets later runs
(and the validation stage) prove the original footage was never modified.
"""

from __future__ import annotations

import hashlib

from app.core.security import validate_file
from app.pipeline.base import Stage, StageContext, StageResult

CHUNK = 8 * 1024 * 1024


class IngestStage(Stage):
    name = "ingest"
    kinds = ("video", "image")

    def run(self, ctx: StageContext) -> StageResult:
        path = ctx.source_path  # raises if the path escapes the project
        media = ctx.config.media
        size = validate_file(
            path,
            allowed_extensions=[*media.video_extensions, *media.image_extensions],
            max_size_bytes=media.max_file_size_bytes,
        )
        st = path.stat()
        known = ctx.previous.get("ingest")
        if (
            known
            and not ctx.force
            and known.get("sha256")
            and known.get("size_bytes") == size
            and known.get("mtime") == st.st_mtime
        ):
            return StageResult(outputs=known, skipped=True, message="Unchanged since last ingest.")

        digest = hashlib.sha256()
        done = 0
        with path.open("rb") as fh:  # read-only
            while chunk := fh.read(CHUNK):
                digest.update(chunk)
                done += len(chunk)
                ctx.check_cancelled()
                ctx.progress(done / size if size else 1.0, "hashing")
        return StageResult(
            outputs={"sha256": digest.hexdigest(), "size_bytes": size, "mtime": st.st_mtime},
            config_used={"max_file_size_bytes": media.max_file_size_bytes},
        )
