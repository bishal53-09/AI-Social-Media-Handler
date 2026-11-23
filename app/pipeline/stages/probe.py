"""Stage 2 — metadata extraction with ffprobe."""

from __future__ import annotations

from app.pipeline.base import Stage, StageContext, StageResult
from app.pipeline.ffmpeg import ProbeResult, probe_file

ORIGINAL_360_EXTENSIONS = {".osv", ".insv"}


def classify_media(source_rel: str, probe: ProbeResult) -> str:
    """Return ``360`` (camera original), ``360-stitched`` or ``flat``.

    * ``.osv`` / ``.insv`` are camera-original containers that still need
      stitching in the vendor's software.
    * Anything equirectangular (spherical metadata, or a 2:1 frame as a
      heuristic) is treated as stitched 360 footage.
    """
    ext = "." + source_rel.rsplit(".", 1)[-1].lower() if "." in source_rel else ""
    if ext in ORIGINAL_360_EXTENSIONS:
        return "360"
    if probe.is_equirectangular:
        return "360-stitched"
    return "flat"


class ProbeStage(Stage):
    name = "probe"

    def run(self, ctx: StageContext) -> StageResult:
        cfg = ctx.config.pipeline.ffmpeg
        probe = probe_file(ctx.source_path, cfg)
        ctx.check_cancelled()
        return StageResult(
            outputs={
                "probe": probe.to_dict(),
                "media_type": classify_media(ctx.source_rel, probe),
                "camera": " ".join(p for p in (probe.make, probe.model) if p) or None,
            },
            config_used={"ffprobe": cfg.ffprobe_binary},
        )
