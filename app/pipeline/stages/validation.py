"""Final stage — validation: sources untouched, outputs present and readable."""

from __future__ import annotations

from app.core.exceptions import ValidationFailedError
from app.core.paths import safe_join
from app.pipeline.base import Stage, StageContext, StageResult
from app.pipeline.ffmpeg import probe_file


class ValidationStage(Stage):
    name = "validation"
    kinds = ("video", "image")

    def run(self, ctx: StageContext) -> StageResult:
        problems: list[str] = []
        checks: list[str] = []

        # 1. The original must be unchanged since ingestion.
        ingest = ctx.previous.get("ingest", {})
        src = ctx.source_path
        if not src.is_file():
            problems.append("source file is missing")
        elif ingest:
            st = src.stat()
            if st.st_size != ingest.get("size_bytes") or st.st_mtime != ingest.get("mtime"):
                problems.append("source file changed after ingestion (size or mtime differs)")
            else:
                checks.append("source unchanged")

        # 2. Every recorded output exists and is readable.
        ff = ctx.config.pipeline.ffmpeg
        thumb = ctx.previous.get("thumbnails", {}).get("thumbnail")
        if thumb:
            p = safe_join(ctx.project_root, thumb)
            if p.is_file() and p.stat().st_size > 0:
                checks.append("thumbnail present")
            else:
                problems.append("thumbnail missing or empty")
        proxy = ctx.previous.get("proxies", {}).get("proxy")
        if proxy:
            p = safe_join(ctx.project_root, proxy)
            try:
                if probe_file(p, ff).video_stream_count:
                    checks.append("proxy readable")
                else:
                    problems.append("proxy has no video stream")
            except Exception as exc:
                problems.append(f"proxy unreadable: {exc}")

        if problems:
            raise ValidationFailedError("; ".join(problems), details={"problems": problems})
        return StageResult(outputs={"checks": checks}, message=", ".join(checks) or None)
