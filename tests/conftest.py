"""Shared fixtures. Everything is synthetic: no real footage or API keys needed."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import AppConfig, Settings, clear_config_caches, load_app_config
from app.database.migrate import upgrade_database
from app.database.session import Database
from app.main import create_app

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")


def _block_real_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may open a real browser; tests that exercise adapters inject a fake page."""
    from app.core.exceptions import DependencyMissingError
    from platforms.browser import BrowserAdapter

    def blocked(self: BrowserAdapter, *, headless: bool):  # type: ignore[no-untyped-def]
        raise DependencyMissingError("Real browser disabled in tests.")

    monkeypatch.setattr(BrowserAdapter, "_launch", blocked)


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Never read the developer's real .env or write into the repo."""
    for var in (
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "DATA_DIR",
        "MEDIA_ROOT",
        "APP_HOST",
        "APP_PORT",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'env.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "env-data"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "env-projects"))
    monkeypatch.setenv("BROWSER_PROFILE_DIR", str(tmp_path / "env-browser-profiles"))
    _block_real_browser(monkeypatch)
    clear_config_caches()
    yield
    clear_config_caches()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        data_dir=str(tmp_path / "data"),
        media_root=str(tmp_path / "projects"),
    )


@pytest.fixture
def config() -> AppConfig:
    cfg = load_app_config()
    cfg.projects.allowed_roots = []  # only MEDIA_ROOT is allowed by default in tests
    return cfg


@pytest.fixture
def db(settings: Settings) -> Iterator[Database]:
    upgrade_database(settings.resolved_database_url)  # exercises the real migration
    database = Database(settings.resolved_database_url)
    yield database
    database.dispose()


@pytest.fixture
def session(db: Database) -> Iterator[Session]:
    s = db.session()
    yield s
    s.close()


@pytest.fixture
def client(settings: Settings, config: AppConfig) -> Iterator[TestClient]:
    with TestClient(create_app(settings, config)) as c:
        yield c


def make_video(path: Path, *, size: str = "320x160", seconds: float = 2, fps: int = 25, audio: bool = True) -> Path:
    """Generate a small synthetic H.264 video with ffmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={fps}:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(str(path))
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.fixture
def video_factory():  # type: ignore[no-untyped-def]
    return make_video
