"""Frame sampling for AI analysis.

Frames are extracted with ffmpeg, downscaled and re-encoded with Pillow, which
also drops all metadata (EXIF/GPS) before anything could be transmitted.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.core.config import FfmpegConfig, MediaTransmissionConfig
from app.core.exceptions import MediaProcessingError
from app.core.security import run_command


@dataclass(frozen=True)
class SampledFrame:
    timestamp: float
    jpeg: bytes


def sample_timestamps(duration: float, count: int) -> list[float]:
    """Evenly spaced timestamps centred in ``count`` equal slices of the clip."""
    if duration <= 0 or count < 1:
        return [0.0]
    return [round(duration * (i + 0.5) / count, 3) for i in range(count)]


def sample_frames(
    video: Path,
    duration: float,
    policy: MediaTransmissionConfig,
    ffmpeg: FfmpegConfig | None = None,
    count: int | None = None,
) -> list[SampledFrame]:
    """Extract up to ``count`` (default ``policy.max_frames_per_clip``) JPEG frames."""
    ffmpeg = ffmpeg or FfmpegConfig()
    n = min(count or policy.max_frames_per_clip, policy.max_frames_per_clip)
    frames: list[SampledFrame] = []
    with tempfile.TemporaryDirectory(prefix="asmh-frames-") as tmp:
        for i, ts in enumerate(sample_timestamps(duration, n)):
            out = Path(tmp) / f"f{i}.png"
            run_command(
                [
                    ffmpeg.binary,
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{ts:.3f}",
                    "-i",
                    str(video),
                    "-frames:v",
                    "1",
                    "-an",
                    "-sn",
                    "-c:v",
                    "png",
                    str(out),
                ],
                timeout=ffmpeg.probe_timeout_seconds * 4,
            )
            if not out.exists():
                continue
            with Image.open(out) as im:
                rgb = im.convert("RGB")
                if rgb.width > policy.frame_width:
                    rgb.thumbnail((policy.frame_width, 10_000), Image.Resampling.LANCZOS)
                buf = BytesIO()
                rgb.save(buf, "JPEG", quality=policy.jpeg_quality)  # no exif passed => stripped
            frames.append(SampledFrame(ts, buf.getvalue()))
    if not frames:
        raise MediaProcessingError("Could not extract any frames from this video.")
    return frames
