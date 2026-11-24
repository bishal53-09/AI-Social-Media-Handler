"""Browser adapters driven against a fake page (no real browser, no network)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import PlatformError
from platforms.base import Credentials, PublishRequest
from platforms.browser import BrowserAdapter, parse_count
from platforms.registry import create_adapter


@pytest.mark.parametrize(
    ("text", "n"), [("1,234 likes", 1234), ("1.2K", 1200), ("3M views", 3_000_000), ("no number", None), (None, None)]
)
def test_parse_count(text: str | None, n: int | None) -> None:
    assert parse_count(text) == n


def _fake(monkeypatch: pytest.MonkeyPatch, page: MagicMock) -> None:
    @contextmanager
    def launch(self: BrowserAdapter, *, headless: bool) -> Iterator[Any]:
        yield page

    monkeypatch.setattr(BrowserAdapter, "_launch", launch)


def test_signed_out_session_is_refused_with_the_fix(monkeypatch: pytest.MonkeyPatch) -> None:
    page = MagicMock()
    page.locator.return_value.count.return_value = 1  # login form present
    _fake(monkeypatch, page)
    with pytest.raises(PlatformError, match="asmh login instagram"):
        create_adapter("instagram").get_analytics(Credentials(platform="instagram"), "https://www.instagram.com/p/x/")
    assert create_adapter("instagram").is_signed_in() is False


def test_youtube_publish_returns_the_watch_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    page = MagicMock()
    page.locator.return_value.count.return_value = 0  # signed in
    page.locator.return_value.first.get_attribute.return_value = "https://youtu.be/abcdefghijk"
    _fake(monkeypatch, page)
    media = tmp_path / "a.mp4"
    media.write_bytes(b"x")
    res = create_adapter("youtube").publish(
        Credentials(platform="youtube"), PublishRequest(post_id="p", media_path=media, caption="Title\nbody")
    )
    assert res.status == "published" and res.external_post_id == "https://www.youtube.com/watch?v=abcdefghijk"
    page.locator.return_value.first.set_input_files.assert_called_once_with(str(media))


def test_youtube_publish_with_unreadable_link_is_processing_not_published(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = MagicMock()
    page.locator.return_value.count.return_value = 0
    page.locator.return_value.first.get_attribute.return_value = "garbage"
    _fake(monkeypatch, page)
    res = create_adapter("youtube").publish(
        Credentials(platform="youtube"), PublishRequest(post_id="p", media_path=tmp_path / "a.mp4")
    )
    assert res.status == "processing" and res.external_post_id is None


def test_instagram_publish_needs_a_handle(tmp_path: Path) -> None:
    from app.core.exceptions import ValidationFailedError

    with pytest.raises(ValidationFailedError, match="handle"):
        create_adapter("instagram").publish(
            Credentials(platform="instagram"), PublishRequest(post_id="p", media_path=tmp_path / "a.mp4")
        )


def test_missing_like_control_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    page = MagicMock()
    page.locator.return_value.count.return_value = 0  # signed in, but no like button on the page
    page.locator.return_value.first.count.return_value = 0
    _fake(monkeypatch, page)
    with pytest.raises(PlatformError, match="could not find the like"):
        create_adapter("youtube").like_post(Credentials(platform="youtube"), "https://www.youtube.com/watch?v=x")


def test_settings_session_check_and_login_endpoints(client, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    page = MagicMock()
    page.locator.return_value.count.return_value = 1  # signed out
    _fake(monkeypatch, page)
    base = "/api/v1/settings/platforms"
    assert client.post(f"{base}/youtube/session/check").json() == {"signed_in": False}
    page.locator.return_value.count.return_value = 0
    assert client.post(f"{base}/youtube/session/check").json() == {"signed_in": True}
    assert client.post(f"{base}/nope/session/check").status_code == 404
    assert client.post(f"{base}/youtube/session/login").status_code == 202
