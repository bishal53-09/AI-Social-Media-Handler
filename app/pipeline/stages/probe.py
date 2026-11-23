"""Stage 2 — metadata extraction with ffprobe."""

from __future__ import annotations

from app.pipeline.base import Stage, StageContext, StageResult
from app.pipeline.ffmpeg import ProbeResult, probe_file

ORIGINAL_360_EXTENSIONS = {".osv", ".insv"}
#: Folder for stitched 360 exports (optional workflow).
STITCHED_FOLDER = "media/stitched/"


def classify_media(source_rel: str, probe: ProbeResult) -> str:
    """Return ``flat`` (any ordinary video), ``360-stitched`` or ``360``.

    Ordinary video from any source (phone, camera, drone, screen recording,
    finished edit) is ``flat``. 360 handling is opt-in:

    * ``.osv`` / ``.insv`` are 360 camera-original containers (``360``).
    * Spherical metadata marks a stitched 360 export (``360-stitched``).
    * A 2:1 frame without that metadata counts as 360 only inside
      ``media/stitched/``; elsewhere it is an ordinary wide video.
    """
    ext = "." + source_rel.rsplit(".", 1)[-1].lower() if "." in source_rel else ""
    if ext in ORIGINAL_360_EXTENSIONS:
        return "360"
    if probe.is_equirectangular:
        return "360-stitched"
    if probe.possible_360 and source_rel.startswith(STITCHED_FOLDER):
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
