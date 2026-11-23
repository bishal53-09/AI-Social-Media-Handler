"""Stage 3 — thumbnails (ffmpeg frame grab for video, Pillow for images)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.core.exceptions import MediaProcessingError
from app.core.paths import safe_join, to_project_relative
from app.core.security import run_command
from app.pipeline.base import Stage, StageContext, StageResult
from app.pipeline.sidecar import derived_name, write_sidecar

THUMB_DIR = "media/thumbnails"


def needs_stitching(ctx: StageContext) -> bool:
    """True for multi-lens camera originals that must be stitched first."""
    probe = ctx.previous.get("probe", {}).get("probe", {})
    media_type = ctx.previous.get("probe", {}).get("media_type", ctx.media_type)
    return media_type == "360" and (probe.get("video_stream_count") or 1) > 1


def _save_jpeg(src: Path, dest: Path, width: int, quality: int) -> tuple[int, int]:
    with Image.open(src) as im:
        rgb = im.convert("RGB")
        if rgb.width > width:
            rgb.thumbnail((width, 10_000), Image.Resampling.LANCZOS)
        rgb.save(dest, "JPEG", quality=quality, optimize=True)
        return rgb.width, rgb.height


class ThumbnailStage(Stage):
    name = "thumbnails"
    kinds = ("video", "image")

    def run(self, ctx: StageContext) -> StageResult:
        cfg = ctx.config.pipeline.thumbnails
        cfg_used = cfg.model_dump()
        if needs_stitching(ctx):
            return StageResult(
                skipped=True,
                message="Multi-lens camera original: stitch it in the camera vendor's software "
                "first, then import the stitched file into media/stitched/.",
            )
        out_dir = safe_join(ctx.project_root, THUMB_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = safe_join(out_dir, derived_name(ctx.source_rel, ".jpg"))
        rel = to_project_relative(out, ctx.project_root)
        if out.exists() and not ctx.force:
            return StageResult(
                outputs={"thumbnail": rel}, config_used=cfg_used, skipped=True, message="Thumbnail already exists."
            )

        tmp_jpg = out.with_name(f".{out.name}.partial.jpg")
        try:
            if ctx.kind == "image":
                size = _save_jpeg(ctx.source_path, tmp_jpg, cfg.width, cfg.quality)
            else:
                size = self._video_frame(ctx, out, tmp_jpg, cfg.width, cfg.quality, cfg.position)
            tmp_jpg.replace(out)
        finally:
            tmp_jpg.unlink(missing_ok=True)
        write_sidecar(out, source_rel=ctx.source_rel, stage=self.name, config=cfg_used)
        return StageResult(outputs={"thumbnail": rel, "thumbnail_size": list(size)}, config_used=cfg_used)

    def _video_frame(
        self, ctx: StageContext, out: Path, tmp_jpg: Path, width: int, quality: int, position: float
    ) -> tuple[int, int]:
        ff = ctx.config.pipeline.ffmpeg
        duration = ctx.previous.get("probe", {}).get("probe", {}).get("duration") or 0.0
        tmp_png = out.with_name(f".{out.name}.partial.png")
        try:
            for ts in (max(0.0, duration * position), 0.0):
                ctx.check_cancelled()
                tmp_png.unlink(missing_ok=True)
                run_command(
                    [
                        ff.binary,
                        "-nostdin",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-ss",
                        f"{ts:.3f}",
                        "-i",
                        str(ctx.source_path),
                        "-frames:v",
                        "1",
                        "-an",
                        "-sn",
                        "-f",
                        "image2",
                        "-c:v",
                        "png",
                        str(tmp_png),
                    ],
                    timeout=ff.probe_timeout_seconds * 4,
                )
                if tmp_png.exists() and tmp_png.stat().st_size > 0:
                    return _save_jpeg(tmp_png, tmp_jpg, width, quality)
            raise MediaProcessingError("ffmpeg produced no frame for the thumbnail.")
        finally:
            tmp_png.unlink(missing_ok=True)
