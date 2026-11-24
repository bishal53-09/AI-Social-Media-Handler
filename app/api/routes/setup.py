"""First-run setup: a plain-language checklist plus a one-click browser install."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.api.deps import ConfigDep, SettingsDep
from app.core.security import run_command
from app.pipeline.ffmpeg import check_binary
from platforms import browser as browser_mod
from platforms.browser import BrowserAdapter, profile_root

log = logging.getLogger(__name__)
router = APIRouter(prefix="/setup", tags=["setup"])

_install_lock = threading.Lock()
#: idle | running | done | failed
_install: dict[str, str] = {"state": "idle", "message": ""}


class SetupItem(BaseModel):
    id: str
    title: str
    ok: bool
    required: bool
    help: str


class SetupAccount(BaseModel):
    name: str
    title: str
    #: A sign-in is saved on this computer. Use "Check" to confirm it still works.
    connected: bool
    #: Whether posting through this account works yet (experimental) or is planned.
    can_publish: bool


class SetupStatus(BaseModel):
    items: list[SetupItem]
    accounts: list[SetupAccount]
    #: Everything required to run is in place.
    ready: bool
    #: At least one account has a saved sign-in.
    any_account_connected: bool
    browser_install: str
    browser_install_message: str


@router.get("/status", response_model=SetupStatus)
async def setup_status(settings: SettingsDep, config: ConfigDep) -> SetupStatus:
    from platforms.registry import get_registry

    ffmpeg_ok = check_binary(config.pipeline.ffmpeg.binary) is not None
    ffprobe_ok = check_binary(config.pipeline.ffmpeg.ffprobe_binary) is not None
    browser_ok = await run_in_threadpool(browser_mod.browser_installed)
    secrets = settings.configured_secrets()

    items = [
        SetupItem(
            id="video-tools",
            title="Video tools (FFmpeg)",
            ok=ffmpeg_ok and ffprobe_ok,
            required=True,
            help="Needed to read and prepare your videos. Close this app and run the installer again "
            "(Start.command on a Mac, or ./setup.sh); it adds them for you.",
        ),
        SetupItem(
            id="browser",
            title="Connection browser",
            ok=browser_ok,
            required=False,
            help="A private browser window the app uses to sign in to your accounts and post for you. "
            "Press “Install it now” to download it (about 150 MB, one time).",
        ),
        SetupItem(
            id="ai-key",
            title="AI assistant key",
            ok=secrets["anthropic_api_key"],
            required=False,
            help="Optional. Only needed for AI suggestions. Everything else works without it.",
        ),
    ]
    accounts = []
    for name, cfg in config.platforms.platforms.items():
        cls = get_registry().get(name)
        if cls is None or not issubclass(cls, BrowserAdapter) or not cfg.get("enabled"):
            continue
        profile = profile_root() / name
        caps = cls.capability_map()
        accounts.append(
            SetupAccount(
                name=name,
                title=cls.display_name,
                connected=profile.is_dir() and any(profile.iterdir()),
                can_publish=caps.get("publish") in ("implemented", "experimental"),
            )
        )
    return SetupStatus(
        items=items,
        accounts=accounts,
        ready=all(i.ok for i in items if i.required),
        any_account_connected=any(a.connected for a in accounts),
        browser_install=_install["state"],
        browser_install_message=_install["message"],
    )


class InstallStarted(BaseModel):
    state: str
    message: str


def _run_install() -> None:
    try:
        run_command([sys.executable, "-m", "playwright", "install", "chromium"], timeout=1800)
        # Linux may also need system libraries; best effort, never fatal.
        if sys.platform.startswith("linux"):
            try:
                run_command([sys.executable, "-m", "playwright", "install-deps", "chromium"], timeout=900, check=False)
            except Exception:
                log.info("Could not install browser system libraries", exc_info=True)
        _install.update(state="done", message="The connection browser is installed.")
    except Exception as exc:
        log.exception("Browser install failed")
        _install.update(
            state="failed",
            message="The download did not finish. Check your internet connection and try again. "
            "If it keeps failing, run the installer again.",
        )
        log.debug("install error: %s", exc)


@router.post("/browser/install", response_model=InstallStarted, status_code=202)
def install_browser() -> InstallStarted:
    """Download the browser used to connect accounts. Runs in the background; poll /setup/status."""
    with _install_lock:
        if _install["state"] == "running":
            return InstallStarted(state="running", message="Already downloading…")
        _install.update(state="running", message="Downloading the connection browser…")
    threading.Thread(target=_run_install, daemon=True).start()
    return InstallStarted(state="running", message=_install["message"])


def _reset_for_tests(**kw: Any) -> None:  # pragma: no cover - test helper
    _install.update({"state": "idle", "message": ""} | kw)
