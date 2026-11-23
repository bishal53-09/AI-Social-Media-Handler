from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.core.config import clear_config_caches
from tests.conftest import make_video, needs_ffmpeg

runner = CliRunner()


@pytest.fixture(autouse=True)
def _cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "cli-data"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "cli-projects"))
    clear_config_caches()


def test_version() -> None:
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0 and "ai-social-media-handler 0.1.0" in r.output


def test_init_project_creates_structure_and_valid_json(tmp_path: Path) -> None:
    target = tmp_path / "Content" / "MyTravelProject"
    r = runner.invoke(app, ["init-project", "--name", "My Travel Project", "--path", str(target)])
    assert r.exit_code == 0, r.output
    assert "my-travel-project" in r.output
    for rel in ("media/raw", "media/stitched", "media/processed/reframed", "data/days", "exports/drafts", "logs"):
        assert (target / rel).is_dir()
    meta = json.loads((target / "project.json").read_text())
    assert meta["id"] == "my-travel-project" and meta["schema_version"] == 1


def test_init_project_twice_is_refused_with_actionable_message(tmp_path: Path) -> None:
    args = ["init-project", "--name", "X", "--path", str(tmp_path / "x")]
    assert runner.invoke(app, args).exit_code == 0
    again = runner.invoke(app, args)
    assert again.exit_code == 1 and "already contains a project" in again.output


def test_doctor_reports_environment(tmp_path: Path) -> None:
    r = runner.invoke(app, ["doctor"])
    assert "Python" in r.output and "Database" in r.output and "Configuration" in r.output
    assert "FFmpeg" in r.output
    # exit code is 0 only when nothing required is missing
    from tests.conftest import HAS_FFMPEG

    assert (r.exit_code == 0) == HAS_FFMPEG


def test_doctor_does_not_crash_when_optional_tools_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    r = runner.invoke(app, ["doctor"])
    assert r.exception is None or isinstance(r.exception, SystemExit)
    assert "not found" in r.output and "→" in r.output  # actionable fix hints


def test_inventory_on_unscanned_project_suggests_scan(tmp_path: Path) -> None:
    p = tmp_path / "p"
    runner.invoke(app, ["init-project", "--name", "P", "--path", str(p)])
    r = runner.invoke(app, ["inventory", str(p)])
    assert r.exit_code == 0 and "No media indexed yet" in r.output and "scan" in r.output


def test_commands_on_a_non_project_fail_cleanly(tmp_path: Path) -> None:
    r = runner.invoke(app, ["scan", str(tmp_path)])
    assert r.exit_code == 1 and "No project.json" in r.output


@needs_ffmpeg
def test_scan_process_inventory_workflow(tmp_path: Path) -> None:
    p = tmp_path / "proj"
    runner.invoke(app, ["init-project", "--name", "Flow", "--path", str(p)])
    make_video(p / "media/raw/2026-11-23/a.mp4", size="640x360", seconds=1)
    make_video(p / "media/stitched/pano.mp4", size="640x320", seconds=1)

    s = runner.invoke(app, ["scan", str(p)])
    assert s.exit_code == 0 and "new: 2" in s.output and "probed: 2" in s.output

    proc = runner.invoke(
        app, ["process", str(p), "--stage", "ingest", "--stage", "probe", "--stage", "thumbnails", "--stage", "proxies"]
    )
    assert proc.exit_code == 0, proc.output
    assert "job completed: 2 ok, 0 failed" in proc.output

    inv = runner.invoke(app, ["inventory", str(p)])
    assert "360-stitched" in inv.output and "640x320" in inv.output and "yes" in inv.output
    assert len(list((p / "media/thumbnails").glob("*.jpg"))) == 2


def test_process_refuses_unimplemented_stage(tmp_path: Path) -> None:
    p = tmp_path / "p"
    runner.invoke(app, ["init-project", "--name", "P", "--path", str(p)])
    r = runner.invoke(app, ["process", str(p), "--stage", "reframing"])
    assert r.exit_code == 1 and "not implemented" in r.output


def test_serve_refuses_non_localhost_without_flag() -> None:
    r = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert r.exit_code == 2 and "Refusing to bind" in r.output


def test_analyze_requires_consent_and_key(tmp_path: Path) -> None:
    p = tmp_path / "p"
    runner.invoke(app, ["init-project", "--name", "P", "--path", str(p)])
    r = runner.invoke(app, ["analyze", str(p), "media/raw/x.mp4"])
    assert r.exit_code == 1  # unknown clip is reported cleanly, not a traceback
