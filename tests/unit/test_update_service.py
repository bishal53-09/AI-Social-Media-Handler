"""Update check against throwaway git repositories (no network)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import update_service
from app.services.update_service import UpdateChecker

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    """A bare 'origin', a clone of it (the install) and a second clone to push from."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    upstream = tmp_path / "upstream"
    git(tmp_path, "clone", "-q", str(origin), str(upstream))
    git(upstream, "checkout", "-q", "-b", "main")
    commit(upstream, "a.txt")
    git(upstream, "push", "-q", "-u", "origin", "main")
    install = tmp_path / "install"
    git(tmp_path, "clone", "-q", str(origin), str(install))
    return install, upstream


def test_up_to_date(repos: tuple[Path, Path]) -> None:
    install, _ = repos
    status = UpdateChecker(install).check()
    assert status.supported and not status.update_available
    assert status.branch == "main" and status.upstream == "origin/main"
    assert status.behind == 0 and status.fetched
    assert status.message == "Up to date."


def test_detects_new_commits_without_changing_checkout(repos: tuple[Path, Path]) -> None:
    install, upstream = repos
    before = git(install, "rev-parse", "HEAD")
    commit(upstream, "b.txt")
    commit(upstream, "c.txt")
    git(upstream, "push", "-q")

    status = UpdateChecker(install).check()
    assert status.update_available and status.behind == 2 and status.ahead == 0
    assert status.command == "make update"
    assert status.remote_commit == git(upstream, "rev-parse", "--short", "HEAD")
    assert git(install, "rev-parse", "HEAD") == before  # read-only
    assert not (install / "b.txt").exists()


def test_reports_local_changes_and_divergence(repos: tuple[Path, Path]) -> None:
    install, upstream = repos
    commit(upstream, "b.txt")
    git(upstream, "push", "-q")
    (install / "a.txt").write_text("edited")
    status = UpdateChecker(install).check()
    assert status.dirty and "stash" in status.message

    git(install, "checkout", "-q", "--", "a.txt")
    commit(install, "local.txt")
    status = UpdateChecker(install).check()
    assert status.ahead == 1 and status.behind == 1
    assert "Fast-forward is not possible" in status.message


def test_fetch_is_rate_limited(repos: tuple[Path, Path]) -> None:
    install, upstream = repos
    checker = UpdateChecker(install, fetch_interval=3600)
    assert checker.check().fetched
    commit(upstream, "b.txt")
    git(upstream, "push", "-q")
    cached = checker.check()
    assert not cached.fetched and cached.behind == 0
    forced = checker.check(force=True)
    assert forced.fetched and forced.behind == 1


def test_fetch_disabled_uses_local_refs(repos: tuple[Path, Path]) -> None:
    install, upstream = repos
    commit(upstream, "b.txt")
    git(upstream, "push", "-q")
    status = UpdateChecker(install).check(fetch=False)
    assert not status.fetched and status.behind == 0


def test_unreachable_remote_is_not_an_error(repos: tuple[Path, Path], tmp_path: Path) -> None:
    install, _ = repos
    git(install, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    status = UpdateChecker(install).check()
    assert status.supported and not status.fetched
    assert "Could not reach the remote" in status.message


def test_not_a_checkout_and_no_upstream(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert not UpdateChecker(plain).check().supported

    git(tmp_path, "init", "-q", "-b", "main", str(plain))
    commit(plain, "a.txt")
    status = UpdateChecker(plain).check()
    assert status.supported and not status.update_available
    assert "no upstream" in status.message


def test_api_endpoint(client: TestClient, repos: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    install, upstream = repos
    commit(upstream, "b.txt")
    git(upstream, "push", "-q")
    monkeypatch.setattr(update_service, "_checker", UpdateChecker(install))
    r = client.get("/api/v1/system/update")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["update_available"] is True and body["behind"] == 1
    assert body["command"] == "make update"


# --- scripts/update.sh and scripts/dev.sh -----------------------------------------------

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.mark.parametrize("name", ["dev.sh", "update.sh"])
def test_shell_scripts_parse(name: str) -> None:
    subprocess.run(["bash", "-n", str(SCRIPTS / name)], check=True)


def _install_update_script(install: Path) -> Path:
    (install / "scripts").mkdir()
    target = install / "scripts" / "update.sh"
    shutil.copy(SCRIPTS / "update.sh", target)
    # Keep the copied script out of `git status` so it doesn't count as a local change.
    (install / ".git" / "info" / "exclude").write_text("scripts/\n")
    return target


def test_update_script_refuses_local_changes(repos: tuple[Path, Path]) -> None:
    install, upstream = repos
    script = _install_update_script(install)
    commit(upstream, "b.txt")
    git(upstream, "push", "-q")
    (install / "a.txt").write_text("edited")
    r = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert r.returncode != 0
    assert "uncommitted changes" in r.stderr
    assert not (install / "b.txt").exists()
    assert (install / "a.txt").read_text() == "edited"


def test_update_script_refuses_diverged_branch(repos: tuple[Path, Path]) -> None:
    install, upstream = repos
    script = _install_update_script(install)
    commit(upstream, "b.txt")
    git(upstream, "push", "-q")
    commit(install, "local.txt")
    r = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert r.returncode != 0 and "Fast-forward is not possible" in r.stderr
    assert not (install / "b.txt").exists()


def test_update_script_noop_when_up_to_date(repos: tuple[Path, Path]) -> None:
    install, _ = repos
    script = _install_update_script(install)
    r = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "Already up to date" in r.stdout
