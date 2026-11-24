"""Real ffmpeg/ffprobe on synthetic media."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import AppConfig, Settings
from app.core.exceptions import CancelledError, MediaProcessingError, UnsupportedOperationError
from app.models import Job, JobEvent, MediaAsset, Project
from app.pipeline.base import StageContext
from app.pipeline.ffmpeg import probe_file
from app.pipeline.orchestrator import PipelineRunner, resolve_stages
from app.pipeline.stages.ingest import IngestStage
from app.pipeline.stages.probe import ProbeStage
from app.pipeline.stages.proxies import ProxyStage
from app.pipeline.stages.thumbnails import ThumbnailStage
from app.services.media_service import MediaService
from app.services.project_service import ProjectService
from app.tracking.repository import ProjectRepository
from tests.conftest import make_video, needs_ffmpeg

pytestmark = needs_ffmpeg


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def project(session: Session, settings: Settings, config: AppConfig) -> Project:
    p = ProjectService(session, settings, config).init_project("Media Test", default_camera="DJI Osmo 360 II")
    root = Path(p.path)
    make_video(root / "media/stitched/pano.mp4", size="640x320", seconds=2)
    make_video(root / "media/raw/2026-11-23/flat.mp4", size="640x360", seconds=2, audio=False)
    # A file outside a dated folder takes its day from its modification time. Pin that time to the
    # same day as the dated folder so the tests do not depend on the date they are run.
    pinned = datetime(2026, 11, 23, 12, 0).timestamp()
    os.utime(root / "media/stitched/pano.mp4", (pinned, pinned))
    return p


def ctx(root: Path, rel: str, config: AppConfig, **kw) -> StageContext:  # type: ignore[no-untyped-def]
    return StageContext(project_root=root, source_rel=rel, kind="video", config=config, **kw)


# --- individual stages ------------------------------------------------------------


def test_probe_stage_extracts_real_metadata(project: Project, config: AppConfig) -> None:
    res = ProbeStage().run(ctx(Path(project.path), "media/stitched/pano.mp4", config))
    probe = res.outputs["probe"]
    assert (probe["width"], probe["height"]) == (640, 320)
    assert probe["fps"] == 25.0 and probe["video_codec"] == "h264" and probe["audio_codec"] == "aac"
    assert probe["duration"] == pytest.approx(2.0, abs=0.2)
    assert res.outputs["media_type"] == "360-stitched"


def test_probe_rejects_non_media(tmp_path: Path, config: AppConfig) -> None:
    (tmp_path / "x.mp4").write_text("garbage")
    with pytest.raises(MediaProcessingError, match="could not read"):
        ProbeStage().run(ctx(tmp_path, "x.mp4", config))


def test_thumbnail_stage_creates_valid_jpeg_with_sidecar(project: Project, config: AppConfig) -> None:
    root = Path(project.path)
    rel = "media/stitched/pano.mp4"
    c = ctx(root, rel, config)
    c.previous["probe"] = ProbeStage().run(c).outputs
    res = ThumbnailStage().run(c)
    thumb = root / res.outputs["thumbnail"]
    assert thumb.parent == root / "media" / "thumbnails"
    with Image.open(thumb) as im:
        assert im.format == "JPEG" and im.width <= config.pipeline.thumbnails.width
        assert im.width / im.height == pytest.approx(2.0, abs=0.05)
    import json

    side = json.loads(thumb.with_name(thumb.name + ".json").read_text())
    assert side["source"] == rel and side["stage"] == "thumbnails"


def test_thumbnail_is_skipped_when_present_unless_forced(project: Project, config: AppConfig) -> None:
    root, rel = Path(project.path), "media/raw/2026-11-23/flat.mp4"
    c = ctx(root, rel, config)
    c.previous["probe"] = ProbeStage().run(c).outputs
    assert not ThumbnailStage().run(c).skipped
    assert ThumbnailStage().run(c).skipped
    c.force = True
    assert not ThumbnailStage().run(c).skipped


def test_image_thumbnail_uses_pillow(tmp_path: Path, config: AppConfig) -> None:
    (tmp_path / "media" / "raw").mkdir(parents=True)
    Image.new("RGB", (2000, 1000), "red").save(tmp_path / "media/raw/pic.jpg")
    c = StageContext(project_root=tmp_path, source_rel="media/raw/pic.jpg", kind="image", config=config)
    res = ThumbnailStage().run(c)
    with Image.open(tmp_path / res.outputs["thumbnail"]) as im:
        assert im.width == config.pipeline.thumbnails.width


def test_proxy_stage_makes_playable_smaller_file_and_reports_progress(project: Project, config: AppConfig) -> None:
    root, rel = Path(project.path), "media/raw/2026-11-23/flat.mp4"
    c = ctx(root, rel, config)
    seen: list[float] = []
    c.progress = lambda f, _m=None: seen.append(f)
    c.previous["probe"] = ProbeStage().run(c).outputs
    res = ProxyStage().run(c)
    out = root / res.outputs["proxy"]
    p = probe_file(out)
    assert p.video_codec == "h264" and p.pixel_format == "yuv420p"
    assert p.height <= 360  # never upscaled (source is 360p, target 540)
    assert p.duration == pytest.approx(2.0, abs=0.3)
    assert seen and max(seen) <= 1.0
    assert not list(out.parent.glob(".*partial*"))


def test_proxy_for_stitched_360_uses_equirect_height_without_upscaling(project: Project, config: AppConfig) -> None:
    root = Path(project.path)
    c = ctx(root, "media/stitched/pano.mp4", config)
    c.previous["probe"] = ProbeStage().run(c).outputs
    out = root / ProxyStage().run(c).outputs["proxy"]
    p = probe_file(out)
    assert (p.width, p.height) == (640, 320)  # 2:1 preserved, source smaller than 960


def test_cancelling_a_proxy_stops_ffmpeg_and_leaves_no_partial_file(project: Project, config: AppConfig) -> None:
    root = Path(project.path)
    make_video(root / "media/raw/long.mp4", size="1280x720", seconds=20)
    c = ctx(root, "media/raw/long.mp4", config)
    c.previous["probe"] = ProbeStage().run(c).outputs
    c.is_cancelled = lambda: True
    with pytest.raises(CancelledError):
        ProxyStage().run(c)
    assert not list((root / "media" / "proxies").glob("*"))


def test_multi_lens_originals_are_not_processed_as_if_stitched(project: Project, config: AppConfig) -> None:
    c = ctx(Path(project.path), "media/raw/x.osv", config)
    c.previous["probe"] = {"media_type": "360", "probe": {"video_stream_count": 2}}
    for stage in (ThumbnailStage(), ProxyStage()):
        res = stage.run(c)
        assert res.skipped and "stitch" in (res.message or "").lower()


def test_ingest_fingerprints_without_modifying_source(project: Project, config: AppConfig) -> None:
    root, rel = Path(project.path), "media/stitched/pano.mp4"
    src = root / rel
    before, mtime = sha(src), src.stat().st_mtime
    res = IngestStage().run(ctx(root, rel, config))
    assert res.outputs["sha256"] == before
    assert sha(src) == before and src.stat().st_mtime == mtime


def test_ingest_rejects_disallowed_extension_and_traversal(tmp_path: Path, config: AppConfig) -> None:
    (tmp_path / "notes.txt").write_text("x")
    from app.core.exceptions import PathSecurityError, ValidationFailedError

    with pytest.raises(ValidationFailedError):
        IngestStage().run(ctx(tmp_path, "notes.txt", config))
    with pytest.raises(PathSecurityError):
        IngestStage().run(ctx(tmp_path, "../notes.txt", config))


# --- scanning ------------------------------------------------------------------------


def test_scan_indexes_probes_and_writes_day_files(session: Session, project: Project, config: AppConfig) -> None:
    result = MediaService(session, config).scan(project)
    assert (result.new, result.probed, result.probe_failed, result.days_written) == (2, 2, 0, 1)
    assets = {a.relative_path: a for a in session.scalars(select(MediaAsset))}
    pano = assets["media/stitched/pano.mp4"]
    assert pano.media_type == "360-stitched" and pano.stage == "stitched"
    assert assets["media/raw/2026-11-23/flat.mp4"].day == "2026-11-23"
    day = ProjectRepository(Path(project.path)).read_day("2026-11-23")  # schema-validated
    assert "media/raw/2026-11-23/flat.mp4" in {c["source"]["file"] for c in day["clips"]}
    # Files outside a dated folder fall back to their modification date.
    from datetime import datetime

    mdate = datetime.fromtimestamp(Path(project.path, "media/stitched/pano.mp4").stat().st_mtime)
    assert pano.day == mdate.strftime("%Y-%m-%d")


def test_scan_is_idempotent_and_detects_changes_and_removals(
    session: Session, project: Project, config: AppConfig
) -> None:
    svc, root = MediaService(session, config), Path(project.path)
    svc.scan(project)
    again = svc.scan(project)
    assert (again.new, again.unchanged, again.changed) == (0, 2, 0)

    make_video(root / "media/raw/2026-11-23/flat.mp4", size="320x180", seconds=1)  # replaced on disk
    (root / "media/stitched/pano.mp4").unlink()
    third = svc.scan(project)
    assert third.changed == 1 and third.missing == 1
    assert any("changed on disk" in w for w in third.warnings)
    missing = session.scalar(select(MediaAsset).where(MediaAsset.relative_path == "media/stitched/pano.mp4"))
    assert missing is not None and missing.missing is True


def test_scan_ignores_hidden_partial_and_unknown_files_and_escaping_symlinks(
    session: Session, project: Project, config: AppConfig, tmp_path: Path
) -> None:
    root = Path(project.path)
    (root / "media/raw/.hidden.mp4").write_bytes(b"x")
    (root / "media/raw/notes.txt").write_text("x")
    outside = make_video(tmp_path / "outside" / "secret.mp4")
    os.symlink(outside, root / "media/raw/link.mp4")
    result = MediaService(session, config).scan(project)
    paths = {a.relative_path for a in session.scalars(select(MediaAsset))}
    assert "media/raw/link.mp4" not in paths and ".hidden" not in " ".join(paths)
    assert result.skipped == 1 and any("outside the project" in w for w in result.warnings)


def test_scan_records_probe_failures_without_crashing(session: Session, project: Project, config: AppConfig) -> None:
    (Path(project.path) / "media/raw/corrupt.mp4").write_text("not a video")
    result = MediaService(session, config).scan(project)
    assert result.probe_failed == 1
    bad = session.scalar(select(MediaAsset).where(MediaAsset.relative_path == "media/raw/corrupt.mp4"))
    assert bad is not None and bad.probe_error


def test_day_sync_preserves_user_edits_and_never_deletes_clips(
    session: Session, project: Project, config: AppConfig
) -> None:
    repo, svc = ProjectRepository(Path(project.path)), MediaService(session, config)
    svc.scan(project)
    day = repo.read_day("2026-11-23")
    day["clips"][0]["title"] = "My custom title"
    day["clips"][0]["processing"]["color_profile"] = "d-log"
    day["clips"][0]["outputs"].append(
        {"file": "exports/drafts/a.mp4", "kind": "draft", "created_at": "2026-11-23T10:00:00+00:00"}
    )
    day["clips"].append(
        {  # a clip whose media file no longer exists
            "id": "clip_gone",
            "title": "Gone",
            "source": {"file": "media/raw/2026-11-23/gone.mp4", "type": "flat"},
            "processing": {"status": "pending"},
            "outputs": [],
            "posts": [],
        }
    )
    repo.write_day("2026-11-23", day)
    svc.scan(project)
    after = {c["id"]: c for c in repo.read_day("2026-11-23")["clips"]}
    kept = next(c for c in after.values() if c["source"]["file"].endswith("flat.mp4"))
    assert kept["title"] == "My custom title"
    assert kept["processing"]["color_profile"] == "d-log" and len(kept["outputs"]) == 1
    assert "clip_gone" in after


# --- orchestrator -----------------------------------------------------------------------


def run_job(session: Session, project: Project, config: AppConfig, **params) -> Job:  # type: ignore[no-untyped-def]
    job = Job(type="pipeline.process", project_id=project.id, params=params)
    session.add(job)
    session.commit()
    PipelineRunner(session, config).run(job.id)
    session.refresh(job)
    return job


def test_pipeline_job_processes_everything_and_traces_each_stage(
    session: Session, project: Project, config: AppConfig
) -> None:
    root = Path(project.path)
    originals = {p: sha(p) for p in (root / "media/stitched/pano.mp4", root / "media/raw/2026-11-23/flat.mp4")}
    MediaService(session, config).scan(project, probe=False)
    job = run_job(session, project, config)
    assert job.status == "completed" and job.progress == 1.0
    assert job.result["succeeded"] == 2 and job.result["failed"] == 0

    for a in session.scalars(select(MediaAsset)):
        assert a.sha256 and a.probe and a.thumbnail_path and a.proxy_path
        assert (root / a.thumbnail_path).is_file() and (root / a.proxy_path).is_file()
    events = list(session.scalars(select(JobEvent).where(JobEvent.job_id == job.id)))
    completed = [e for e in events if e.event == "completed"]
    assert {e.stage for e in completed} == {"ingest", "probe", "thumbnails", "proxies", "validation"}
    proxy_ev = next(e for e in completed if e.stage == "proxies")
    assert proxy_ev.data["config"]["crf"] == 28 and proxy_ev.data["outputs"]["proxy"]
    # originals untouched
    assert {p: sha(p) for p in originals} == originals
    # day JSON reflects completed processing
    day = ProjectRepository(root).read_day("2026-11-23")
    assert all(c["processing"]["status"] == "completed" for c in day["clips"])


def test_second_run_skips_existing_work(session: Session, project: Project, config: AppConfig) -> None:
    MediaService(session, config).scan(project, probe=False)
    run_job(session, project, config)
    second = run_job(session, project, config)
    states = {s for a in second.result["assets"].values() for s in a["stages"].values()}
    assert "skipped" in states
    assert all(a["stages"]["thumbnails"] == "skipped" for a in second.result["assets"].values())


def test_failure_on_one_file_does_not_stop_the_others(session: Session, project: Project, config: AppConfig) -> None:
    (Path(project.path) / "media/raw/corrupt.mp4").write_text("nope")
    MediaService(session, config).scan(project, probe=False)
    job = run_job(session, project, config)
    assert job.status == "failed" and job.result["succeeded"] == 2 and job.result["failed"] == 1
    assert "1 of 3" in job.error
    failed = [e for e in session.scalars(select(JobEvent).where(JobEvent.job_id == job.id)) if e.event == "failed"]
    assert failed and failed[0].stage == "probe"


def test_cancelled_job_stops(session: Session, project: Project, config: AppConfig) -> None:
    MediaService(session, config).scan(project, probe=False)
    job = Job(type="pipeline.process", project_id=project.id, params={}, cancel_requested=True)
    session.add(job)
    session.commit()
    PipelineRunner(session, config).run(job.id)
    session.refresh(job)
    assert job.status == "cancelled"
    assert not list((Path(project.path) / "media/proxies").glob("*.mp4"))


def test_unimplemented_and_unknown_stages_are_refused(config: AppConfig) -> None:
    from app.core.exceptions import ValidationFailedError

    for name in ("reframing", "color_grading", "rendering", "editing", "subtitles", "audio", "analysis"):
        with pytest.raises(UnsupportedOperationError):
            resolve_stages([name])
    with pytest.raises(ValidationFailedError):
        resolve_stages(["teleport"])


def test_stage_subset_only_runs_requested_stages(session: Session, project: Project, config: AppConfig) -> None:
    MediaService(session, config).scan(project, probe=False)
    job = run_job(session, project, config, stages=["ingest", "probe"])
    assert job.status == "completed"
    assert all(set(a["stages"]) == {"ingest", "probe"} for a in job.result["assets"].values())
    assert not list((Path(project.path) / "media/thumbnails").glob("*.jpg"))
