"""ffprobe / ffmpeg integration (subprocess, never a shell)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.core.config import FfmpegConfig
from app.core.exceptions import MediaProcessingError
from app.core.security import run_command, which

#: Aspect-ratio tolerance when flagging a 2:1 frame as possibly 360.
EQUIRECT_TOLERANCE = 0.02


@dataclass
class ProbeResult:
    format_name: str | None = None
    duration: float | None = None
    size_bytes: int | None = None
    bit_rate: int | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    pixel_format: str | None = None
    color_space: str | None = None
    color_transfer: str | None = None
    color_primaries: str | None = None
    color_range: str | None = None
    rotation: int = 0
    video_stream_count: int = 0
    audio_stream_count: int = 0
    has_audio: bool = False
    # equirectangular | None — set only from explicit spherical metadata
    projection: str | None = None
    # metadata | None
    projection_source: str | None = None
    #: 2:1 frame without spherical metadata. Could be a stitched 360 export that
    #: lost its metadata, or an ordinary wide video; it is *not* treated as 360
    #: unless it sits in ``media/stitched/`` (see ``classify_media``).
    possible_360: bool = False
    make: str | None = None
    model: str | None = None
    creation_time: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def is_equirectangular(self) -> bool:
        return self.projection == "equirectangular"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_equirectangular"] = self.is_equirectangular
        return d


def _fraction(value: str | None) -> float | None:
    if not value or value in ("0/0", "N/A"):
        return None
    try:
        f = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return round(float(f), 3) if f > 0 else None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f >= 0 else None


def parse_probe(data: dict[str, Any]) -> ProbeResult:
    """Convert ffprobe's JSON into a :class:`ProbeResult`."""
    fmt = data.get("format", {}) or {}
    streams = data.get("streams", []) or []
    videos = [
        s
        for s in streams
        if s.get("codec_type") == "video" and (s.get("disposition") or {}).get("attached_pic", 0) != 1
    ]
    audios = [s for s in streams if s.get("codec_type") == "audio"]

    res = ProbeResult(
        format_name=fmt.get("format_name"),
        duration=_float(fmt.get("duration")),
        size_bytes=_int(fmt.get("size")),
        bit_rate=_int(fmt.get("bit_rate")),
        video_stream_count=len(videos),
        audio_stream_count=len(audios),
        has_audio=bool(audios),
    )
    tags = {str(k).lower(): v for k, v in (fmt.get("tags") or {}).items()}
    res.make = tags.get("make") or tags.get("com.apple.quicktime.make")
    res.model = tags.get("model") or tags.get("com.apple.quicktime.model")
    res.creation_time = tags.get("creation_time")

    if audios:
        res.audio_codec = audios[0].get("codec_name")

    if not videos:
        res.warnings.append("No video stream found.")
        return res

    # With several video streams (e.g. dual-fisheye originals) describe the largest.
    main = max(videos, key=lambda s: (s.get("width") or 0) * (s.get("height") or 0))
    res.width = _int(main.get("width"))
    res.height = _int(main.get("height"))
    res.fps = _fraction(main.get("avg_frame_rate")) or _fraction(main.get("r_frame_rate"))
    res.video_codec = main.get("codec_name")
    res.pixel_format = main.get("pix_fmt")
    res.color_space = main.get("color_space")
    res.color_transfer = main.get("color_transfer")
    res.color_primaries = main.get("color_primaries")
    res.color_range = main.get("color_range")
    if res.duration is None:
        res.duration = _float(main.get("duration"))

    # Rotation: display-matrix side data or legacy "rotate" tag.
    for side in main.get("side_data_list") or []:
        if "rotation" in side:
            rot = _int(round(float(side["rotation"])))
            res.rotation = (-rot) % 360 if rot is not None else 0
    rotate_tag = (main.get("tags") or {}).get("rotate")
    if rotate_tag and not res.rotation:
        res.rotation = (_int(rotate_tag) or 0) % 360
    if res.rotation in (90, 270) and res.width and res.height:
        res.width, res.height = res.height, res.width

    # Projection: explicit spherical metadata wins over the aspect-ratio guess.
    for side in main.get("side_data_list") or []:
        if str(side.get("side_data_type", "")).lower().startswith("spherical"):
            projection = str(side.get("projection", "")).lower()
            if "equirect" in projection:
                res.projection, res.projection_source = "equirectangular", "metadata"
    if res.projection is None and res.width and res.height:
        ratio = res.width / res.height
        if abs(ratio - 2.0) <= 2.0 * EQUIRECT_TOLERANCE:
            res.possible_360 = True
            res.warnings.append(
                "2:1 aspect ratio without spherical metadata. Treated as an ordinary video; "
                "if it is a stitched 360 export, put it in media/stitched/."
            )
    return res


def check_binary(name: str) -> str | None:
    return which(name)


def probe_file(path: Path, cfg: FfmpegConfig | None = None) -> ProbeResult:
    """Run ffprobe on ``path`` and parse the result."""
    cfg = cfg or FfmpegConfig()
    result = run_command(
        [
            cfg.ffprobe_binary,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "--",
            str(path),
        ],
        timeout=cfg.probe_timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        raise MediaProcessingError(
            "ffprobe could not read this file.",
            details={"stderr": result.stderr.strip()[-500:]},
        )
    try:
        return parse_probe(json.loads(result.stdout))
    except json.JSONDecodeError as exc:
        raise MediaProcessingError("ffprobe returned invalid JSON.") from exc


def parse_progress_line(line: str, duration: float | None) -> float | None:
    """Return fraction complete from an ffmpeg ``-progress`` line, if it carries one."""
    if not duration or duration <= 0:
        return None
    key, _, value = line.partition("=")
    if key in ("out_time_us", "out_time_ms"):  # both are microseconds in practice
        try:
            seconds = int(value) / 1_000_000
        except ValueError:
            return None
        return max(0.0, min(1.0, seconds / duration))
    return None
