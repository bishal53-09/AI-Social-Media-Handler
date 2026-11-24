"""Browser-session adapters: drive the platform website as the logged-in user.

No developer app, API key or OAuth is involved. The user signs in once, by hand, in a
visible browser window (``asmh login <platform>``); the cookies live in a persistent
profile directory *outside the repo* (``BROWSER_PROFILE_DIR``, default
``~/.asmh/browser-profiles``) and are reused headlessly afterwards. Passwords are never
seen or stored by this code.

Trade-offs, stated plainly:

* Automating the sites may breach their terms of service and can get an account
  restricted. Every action is paced and only runs when the user asks for it.
* Selectors break whenever a site changes its markup, so every capability here is
  ``experimental``: it fails loudly (``PlatformError``) instead of pretending.
"""

from __future__ import annotations

import os
import random
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ClassVar

from app.core.exceptions import DependencyMissingError, PlatformError
from app.core.paths import expand
from platforms.base import Credentials, PlatformAdapter

DEFAULT_PROFILE_DIR = "~/.asmh/browser-profiles"
NAV_TIMEOUT_MS = 45_000
#: Publishing waits for server-side processing, which can take minutes.
PUBLISH_TIMEOUT_MS = 10 * 60_000


def profile_root() -> Path:
    return expand(os.environ.get("BROWSER_PROFILE_DIR") or DEFAULT_PROFILE_DIR)


def parse_count(text: str | None) -> int | None:
    """'1,234' → 1234, '1.2K' → 1200, '3M' → 3000000; None when there is no number."""
    m = re.search(r"([\d][\d,.]*)\s*([KkMmBb]?)", text or "")
    if not m:
        return None
    mult = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[m.group(2).lower()]
    try:
        return round(float(m.group(1).replace(",", "")) * mult)
    except ValueError:
        return None


def pause(page: Any, low: int = 700, high: int = 1800) -> None:
    """Human-ish delay between actions."""
    page.wait_for_timeout(random.randint(low, high))  # noqa: S311 - pacing, not security


class BrowserAdapter(PlatformAdapter):
    """Base for adapters that act through a logged-in browser profile."""

    login_url: ClassVar[str] = ""
    #: CSS selector that is present only when the visitor is NOT signed in.
    logged_out_selector: ClassVar[str] = ""

    # -- session ---------------------------------------------------------------

    @property
    def profile_dir(self) -> Path:
        return profile_root() / self.name

    @contextmanager
    def _launch(self, *, headless: bool) -> Iterator[Any]:
        """Open the persistent profile and yield a page. Tests replace this."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise DependencyMissingError(
                "Playwright is not installed. Run: pip install -e '.[browser]' && playwright install chromium"
            ) from exc
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(self.profile_dir), headless=headless, no_viewport=not headless
            )
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.set_default_timeout(NAV_TIMEOUT_MS)
                yield page
            finally:
                ctx.close()

    @contextmanager
    def session(self, url: str | None = None) -> Iterator[Any]:
        """A headless page on ``url`` (or the login URL), verified to be signed in."""
        with self._launch(headless=True) as page:
            page.goto(url or self.login_url)
            page.wait_for_load_state("domcontentloaded")
            if self.logged_out_selector and page.locator(self.logged_out_selector).count():
                raise PlatformError(
                    f"{self.display_name}: not signed in. Run `asmh login {self.name}` and sign in.",
                    details={"platform": self.name},
                )
            yield page

    def authenticate(self) -> Credentials:
        """Open a visible window so the user can sign in; returns when they close it."""
        with self._launch(headless=False) as page:
            page.goto(self.login_url)
            page.wait_for_event("close", timeout=0)
        return Credentials(platform=self.name)

    def is_signed_in(self) -> bool:
        with self._launch(headless=True) as page:
            page.goto(self.login_url)
            page.wait_for_load_state("domcontentloaded")
            return not (self.logged_out_selector and page.locator(self.logged_out_selector).count())

    def refresh_credentials(self, credentials: Credentials) -> Credentials:
        return credentials  # the browser profile holds the session; nothing to refresh
