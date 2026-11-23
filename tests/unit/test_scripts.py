from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def run(script: str, *args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    import os

    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-I", str(REPO / "scripts" / script), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO,
        check=False,
    )


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    return {
        "DATABASE_URL": f"sqlite:///{tmp_path / 's.db'}",
        "DATA_DIR": str(tmp_path / "d"),
        "MEDIA_ROOT": str(tmp_path / "m"),
        "PYTHONPATH": str(REPO),
    }


def test_validate_config_passes_on_repo_defaults(env: dict[str, str]) -> None:
    r = run("validate_config.py", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "schema project.schema.json" in r.stdout


def test_validate_config_detects_broken_project_json(tmp_path: Path, env: dict[str, str]) -> None:
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / "project.json").write_text('{"id": "NOT VALID"}')
    r = run("validate_config.py", str(tmp_path / "proj"), env_extra=env)
    assert r.returncode == 1 and "project.json" in r.stderr


def test_migrate_and_backup_roundtrip(tmp_path: Path, env: dict[str, str]) -> None:
    assert run("migrate_data.py", env_extra=env).returncode == 0
    proj = tmp_path / "proj"
    r = run("init_project.py", "--name", "Backup Me", "--path", str(proj), env_extra=env)
    assert r.returncode == 0, r.stderr + r.stdout
    out = tmp_path / "bk"
    r = run("backup.py", "--output", str(out), str(proj), env_extra=env)
    assert r.returncode == 0, r.stderr
    (archive,) = out.glob("asmh-backup-*.tar.gz")
    assert archive.stat().st_mode & 0o077 == 0  # private
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert "app.db" in names and "projects/proj/project.json" in names
    assert not any(n.endswith((".mp4", ".mov")) for n in names)  # no media in backups


def test_check_dependencies_runs(env: dict[str, str]) -> None:
    r = run("check_dependencies.py", env_extra=env)
    assert "Python" in r.stdout and r.returncode in (0, 1)
