"""Basic footage-analysis workflow (Phase 4 foundation).

media file → sampled frames → AI scene analysis → validated JSON saved in the
project (``data/analysis/<clip_id>.json``). Frames are sent only with consent
(``config/ai.yaml``), and only from the proxy when one exists.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider, ImagePart, enforce_media_consent
from app.ai.footage_analyzer import FootageAnalyzer
from app.ai.frames import sample_frames
from app.core.config import AppConfig
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.paths import safe_join
from app.models import MediaAsset, Project
from app.pipeline.sidecar import clip_id_for
from app.tracking.events import append_event
from app.tracking.json_store import write_json


def analyze_asset(
    session: Session, project: Project, ref: str, provider: AIProvider, config: AppConfig
) -> dict[str, Any]:
    asset = session.scalar(
        select(MediaAsset).where(
            MediaAsset.project_id == project.id,
            or_(MediaAsset.id == ref, MediaAsset.relative_path == ref),
        )
    )
    if asset is None:
        raise NotFoundError(f"No media '{ref}' in this project. Run a scan first.")
    if asset.kind != "video":
        raise ValidationFailedError("Only video can be analysed.")
    if not asset.probe:
        raise ValidationFailedError("This file has no metadata yet. Run a scan (with ffprobe) first.")
    probe = asset.probe
    if asset.media_type == "360" and (probe.get("video_stream_count") or 1) > 1:
        raise ValidationFailedError(
            "This is a multi-lens camera original. Stitch it first and analyse the stitched export."
        )

    policy = config.ai.media_transmission
    # Fail on missing consent *before* spending time extracting frames.
    enforce_media_consent([ImagePart(b"")] * policy.max_frames_per_clip, policy)

    root = Path(project.path)
    source = asset.proxy_path or asset.relative_path
    frames = sample_frames(safe_join(root, source), probe.get("duration") or 0.0, policy, config.pipeline.ffmpeg)
    cid = clip_id_for(asset.relative_path)
    analysis = FootageAnalyzer(provider).analyze(cid, probe, asset.media_type, frames)

    record = {
        "clip_id": cid,
        "source": asset.relative_path,
        "analysed_at": datetime.now(UTC).isoformat(),
        "provider": provider.name,
        "model": config.ai.anthropic.model if provider.name == "anthropic" else None,
        "frames_sent": [f.timestamp for f in frames],
        "analysis": analysis.model_dump(mode="json"),
    }
    write_json(safe_join(root, f"data/analysis/{cid}.json"), record)
    append_event(root, "ai.footage_analysed", {"clip_id": cid, "frames": len(frames)})
    return record
