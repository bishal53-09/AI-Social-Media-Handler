"""Ordinary (non-360) video from any source goes through every implemented stage."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import AppConfig, Settings
from app.models import Job, MediaAsset, Project
from app.pipeline.base import StageContext
from app.pipeline.ffmpeg import probe_file
from app.pipeline.orchestrator import PipelineRunner
from app.pipeline.stages.probe import ProbeStage
from app.pipeline.stages.proxies import ProxyStage
from app.pipeline.stages.thumbnails import ThumbnailStage
from app.services.media_service import MediaService
from app.services.project_service import ProjectService
from app.tracking.repository import ProjectRepository
from tests.conftest import make_video, needs_ffmpeg

pytestmark = needs_ffmpeg


def make_webm(path: Path, size: str = "480x270") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=25:duration=1"]
    cmd += ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-b:v", "200k", str(path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.fixture
def project(session: Session, settings: Settings, config: AppConfig) -> Project:
    """A project with no 360 footage at all: phone, camera and screen-recording style files."""
    p = ProjectService(session, settings, config).init_project("Everyday Clips", default_camera="iPhone 16")
    root = Path(p.path)
    make_video(root / "media/raw/phone-vertical.mov", size="720x1280", seconds=1)
    make_video(root / "media/raw/2026-11-23/camera.mkv", size="1280x720", seconds=1, audio=False)
    make_video(root / "media/raw/wide-21x9.mp4", size="640x320", seconds=1)  # 2:1, but not 360
    make_webm(root / "media/raw/screen-recording.webm")
    return p


def ctx(root: Path, rel: str, config: AppConfig) -> StageContext:
    c = StageContext(project_root=root, source_rel=rel, kind="video", config=config)
    c.previous["probe"] = ProbeStage().run(c).outputs
    return c


def test_vertical_phone_video_is_flat_and_gets_a_full_quality_vertical_proxy(
    project: Project, config: AppConfig
) -> None:
    root = Path(project.path)
    c = ctx(root, "media/raw/phone-vertical.mov", config)
    assert c.previous["probe"]["media_type"] == "flat"
    thumb = ThumbnailStage().run(c)
    assert (root / thumb.outputs["thumbnail"]).is_file()
    proxy = probe_file(root / ProxyStage().run(c).outputs["proxy"])
    # The shorter side is capped at 540, so 9:16 keeps the same quality as landscape.
    assert (proxy.width, proxy.height) == (540, 960)


def test_landscape_proxy_caps_height(project: Project, config: AppConfig) -> None:
    root = Path(project.path)
    proxy = probe_file(root / ProxyStage().run(ctx(root, "media/raw/2026-11-23/camera.mkv", config)).outputs["proxy"])
    assert (proxy.width, proxy.height) == (960, 540)


def test_two_to_one_video_outside_stitched_folder_is_ordinary(project: Project, config: AppConfig) -> None:
    root = Path(project.path)
    c = ctx(root, "media/raw/wide-21x9.mp4", config)
    assert c.previous["probe"]["media_type"] == "flat"
    assert c.previous["probe"]["probe"]["is_equirectangular"] is False
    assert c.previous["probe"]["probe"]["possible_360"] is True
    res = ProxyStage().run(c)
    assert not res.skipped and res.outputs["proxy_height"] == 320  # never upscaled


def test_scan_and_pipeline_handle_a_project_with_no_360_footage(
    session: Session, project: Project, config: AppConfig
) -> None:
    root = Path(project.path)
    result = MediaService(session, config).scan(project)
    assert (result.new, result.probed, result.probe_failed) == (4, 4, 0)
    assets = {a.relative_path: a for a in session.scalars(select(MediaAsset))}
    assert {a.media_type for a in assets.values()} == {"flat"}
    assert {a.stage for a in assets.values()} == {"raw"}

    job = Job(type="pipeline.process", project_id=project.id, params={})
    session.add(job)
    session.commit()
    PipelineRunner(session, config).run(job.id)
    session.refresh(job)
    assert job.status == "completed" and job.result["succeeded"] == 4 and job.result["failed"] == 0
    for a in session.scalars(select(MediaAsset)):
        session.refresh(a)
        assert a.thumbnail_path and a.proxy_path, a.relative_path
        assert (root / a.proxy_path).is_file()

    repo = ProjectRepository(root)
    clips = [c for d in repo.list_days() for c in repo.read_day(d["date"])["clips"]]
    assert len(clips) == 4
    for clip in clips:
        assert clip["source"]["type"] == "flat"
        # The project's default camera applies to ordinary video, not only to 360 footage.
        assert clip["source"]["camera"] == "iPhone 16"
        assert clip["source"]["metadata"]["is_equirectangular"] is False
