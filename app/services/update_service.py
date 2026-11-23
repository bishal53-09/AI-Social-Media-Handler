"""Check whether the local checkout is behind its upstream branch.

Read-only: this module runs ``git fetch`` and inspects refs, but never changes
the working tree. Applying an update is a manual step (``make update``) so the
user decides when the running app restarts.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.exceptions import AppError
from app.core.paths import REPO_ROOT
from app.core.security import run_command, which

logger = logging.getLogger(__name__)

UPDATE_COMMAND = "make update"
FETCH_INTERVAL_SECONDS = 15 * 60
FETCH_TIMEOUT_SECONDS = 20


@dataclass
class UpdateStatus:
    supported: bool
    update_available: bool = False
    branch: str | None = None
    upstream: str | None = None
    local_commit: str | None = None
    remote_commit: str | None = None
    behind: int = 0
    ahead: int = 0
    dirty: bool = False
    fetched: bool = False
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    command: str = UPDATE_COMMAND
    message: str = ""


def _git(repo: Path, *args: str, timeout: float = 10) -> str:
    # Never let git block on a credential prompt for a private remote.
    env = {"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": ""}
    argv = ["git", "-C", str(repo), "-c", "credential.interactive=never", *args]
    return run_command(argv, timeout=timeout, env=env).stdout.strip()


class UpdateChecker:
    """Compares HEAD with its upstream; fetches at most every ``fetch_interval`` seconds."""

    def __init__(self, repo: Path = REPO_ROOT, fetch_interval: float = FETCH_INTERVAL_SECONDS) -> None:
        self.repo = repo
        self.fetch_interval = fetch_interval
        self._last_fetch: float | None = None
        self._lock = threading.Lock()

    def _maybe_fetch(self, force: bool) -> tuple[bool, str]:
        with self._lock:
            recent = self._last_fetch is not None and time.monotonic() - self._last_fetch < self.fetch_interval
            if recent and not force:
                return False, ""
            self._last_fetch = time.monotonic()
        try:
            _git(self.repo, "fetch", "--quiet", "--no-tags", timeout=FETCH_TIMEOUT_SECONDS)
            return True, ""
        except AppError as exc:
            logger.info("Update check: git fetch failed: %s", exc)
            return False, "Could not reach the remote; showing the last known state."

    def check(self, *, fetch: bool = True, force: bool = False) -> UpdateStatus:
        if which("git") is None:
            return UpdateStatus(supported=False, message="git is not installed.")
        try:
            if _git(self.repo, "rev-parse", "--is-inside-work-tree") != "true":
                raise AppError("not a work tree")
        except AppError:
            return UpdateStatus(supported=False, message="This install is not a git checkout.")

        status = UpdateStatus(supported=True)
        status.local_commit = _git(self.repo, "rev-parse", "--short", "HEAD")
        try:
            status.branch = _git(self.repo, "symbolic-ref", "--quiet", "--short", "HEAD")
        except AppError:
            status.message = "HEAD is detached; switch to a branch to receive updates."
            return status
        try:
            status.upstream = _git(self.repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
        except AppError:
            status.message = f"Branch '{status.branch}' has no upstream to compare with."
            return status

        fetch_note = ""
        if fetch:
            status.fetched, fetch_note = self._maybe_fetch(force)
        status.remote_commit = _git(self.repo, "rev-parse", "--short", "@{upstream}")
        counts = _git(self.repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        ahead, behind = (int(n) for n in counts.split())
        status.ahead, status.behind = ahead, behind
        status.dirty = bool(_git(self.repo, "status", "--porcelain", "--untracked-files=no"))
        status.update_available = behind > 0

        if behind and ahead:
            status.message = (
                f"{behind} new commit(s) on {status.upstream}, but this branch also has {ahead} "
                "local commit(s). Fast-forward is not possible; merge or rebase manually."
            )
        elif behind:
            status.message = f"{behind} new commit(s) on {status.upstream}."
            if status.dirty:
                status.message += " Commit or stash your local changes first."
        else:
            status.message = "Up to date."
        if fetch_note:
            status.message = f"{status.message} {fetch_note}"
        return status


_checker: UpdateChecker | None = None


def get_update_checker() -> UpdateChecker:
    global _checker
    if _checker is None:
        _checker = UpdateChecker()
    return _checker
