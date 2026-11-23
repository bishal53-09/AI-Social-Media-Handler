"""Stage 4 — editing proxies (small H.264 files for smooth scrubbing).

Proxies are for preview and analysis only; they are never used for final
renders. Colour is *not* corrected: log/HDR sources will look flat.
"""

from __future__ import annotations

from app.core.paths import safe_join, to_project_relative
from app.core.security import run_command_streaming
from app.pipeline.base import Stage, StageContext, StageResult
from app.pipeline.ffmpeg import parse_progress_line, probe_file
from app.pipeline.sidecar import derived_name, write_sidecar
from app.pipeline.stages.thumbnails import needs_stitching

PROXY_DIR = "media/proxies"


class ProxyStage(Stage):
    name = "proxies"

    def run(self, ctx: StageContext) -> StageResult:
        cfg = ctx.config.pipeline.proxies
        ff = ctx.config.pipeline.ffmpeg
        cfg_used = cfg.model_dump()
        if needs_stitching(ctx):
            return StageResult(
                skipped=True,
                message="Multi-lens camera original: stitch it first; proxies are generated from stitched exports.",
            )
        probe = ctx.previous.get("probe", {}).get("probe", {})
        media_type = ctx.previous.get("probe", {}).get("media_type", ctx.media_type)
        duration = probe.get("duration")

        out_dir = safe_join(ctx.project_root, PROXY_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = safe_join(out_dir, derived_name(ctx.source_rel, ".mp4"))
        rel = to_project_relative(out, ctx.project_root)
        if out.exists() and not ctx.force:
            return StageResult(
                outputs={"proxy": rel}, config_used=cfg_used, skipped=True, message="Proxy already exists."
            )

        height = cfg.equirect_height if media_type in ("360", "360-stitched") else cfg.height
        cfg_used = {**cfg_used, "target_height": height}
        tmp = out.with_name(f".{out.stem}.partial.mp4")
        tmp.unlink(missing_ok=True)
        cmd = [
            ff.binary,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(ctx.source_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            # never upscale; keep even dimensions for H.264
            "-vf",
            f"scale=-2:'min({height},ih)'",
            "-c:v",
            cfg.video_codec,
            "-preset",
            cfg.preset,
            "-crf",
            str(cfg.crf),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            cfg.audio_codec,
            "-b:a",
            cfg.audio_bitrate,
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(tmp),
        ]

        def on_line(line: str) -> None:
            frac = parse_progress_line(line, duration)
            if frac is not None:
                ctx.progress(frac, "encoding proxy")

        try:
            run_command_streaming(
                cmd,
                on_line=on_line,
                should_cancel=ctx.is_cancelled,
                timeout=cfg.timeout_seconds or None,
            )
            result = probe_file(tmp, ff)  # prove the proxy is a readable video
            if not result.video_stream_count:
                from app.core.exceptions import MediaProcessingError

                raise MediaProcessingError("Generated proxy has no video stream.")
            tmp.replace(out)
        finally:
            tmp.unlink(missing_ok=True)
        write_sidecar(
            out,
            source_rel=ctx.source_rel,
            stage=self.name,
            config=cfg_used,
            extra={"width": result.width, "height": result.height, "duration": result.duration},
        )
        return StageResult(
            outputs={
                "proxy": rel,
                "proxy_width": result.width,
                "proxy_height": result.height,
                "proxy_duration": result.duration,
            },
            config_used=cfg_used,
        )
