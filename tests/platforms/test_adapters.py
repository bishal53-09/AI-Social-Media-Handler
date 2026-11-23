from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import load_app_config
from app.core.exceptions import NotFoundError, UnsupportedOperationError
from platforms.base import Credentials, PlatformAdapter, PublishRequest
from platforms.registry import create_adapter, get_registry, register


def probe(**kw):  # type: ignore[no-untyped-def]
    base = {"duration": 30.0, "width": 1080, "height": 1920, "is_equirectangular": False}
    base.update(kw)
    return base


@pytest.fixture
def mp4(tmp_path: Path) -> Path:
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x" * 1024)
    return f


def test_registry_has_the_three_initial_platforms() -> None:
    assert set(get_registry()) == {"instagram", "tiktok", "youtube"}
    assert create_adapter("youtube").display_name == "YouTube"
    with pytest.raises(NotFoundError):
        create_adapter("myspace")


@pytest.mark.parametrize("name", ["instagram", "tiktok", "youtube"])
def test_no_adapter_pretends_to_publish(name: str) -> None:
    a = create_adapter(name)
    creds = Credentials(platform=name, access_token="secret-token")
    assert a.publishing_implemented is False
    req = PublishRequest(post_id="post_1", media_path=Path("a.mp4"))
    calls = [
        a.authenticate,
        lambda: a.refresh_credentials(creds),
        lambda: a.publish(creds, req),
        lambda: a.get_post_status(creds, external_post_id="x"),
        lambda: a.get_analytics(creds, "x"),
    ]
    for call in calls:
        with pytest.raises(UnsupportedOperationError, match="not implemented yet") as exc:
            call()
        assert name in str(exc.value.details["platform"])


def test_credentials_repr_never_shows_tokens() -> None:
    c = Credentials(
        platform="youtube",
        access_token="AAA-secret",
        refresh_token="RRR-secret",
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert "secret" not in repr(c) and "secret" not in str(c)
    assert c.is_expired(datetime(2026, 6, 1, tzinfo=UTC))


def test_reels_accepts_vertical_video_and_rejects_the_rest(mp4: Path) -> None:
    a = create_adapter("instagram")
    assert a.validate_media(mp4, probe()).ok
    wide = a.validate_media(mp4, probe(width=1920, height=1080))
    assert not wide.ok and any("Aspect ratio" in e for e in wide.errors)
    long = a.validate_media(mp4, probe(duration=1000))
    assert not long.ok and any("exceeds" in e for e in long.errors)
    short = a.validate_media(mp4, probe(duration=1))
    assert not short.ok and any("below" in e for e in short.errors)
    mkv = mp4.with_suffix(".mkv")
    mkv.write_bytes(b"x")
    assert not a.validate_media(mkv, probe()).ok


def test_raw_equirectangular_is_never_publishable(mp4: Path) -> None:
    for name in ("instagram", "tiktok", "youtube"):
        r = create_adapter(name).validate_media(mp4, probe(width=3840, height=1920, is_equirectangular=True))
        assert not r.ok and any("reframed" in e for e in r.errors), name


def test_file_size_limit(mp4: Path) -> None:
    cfg = {"media": {"video": {"max_file_size_mb": 0.0001, "containers": ["mp4"]}}}
    r = create_adapter("tiktok", cfg).validate_media(mp4, probe())
    assert not r.ok and any("MB" in e for e in r.errors)


def test_youtube_shorts_is_a_variant_of_the_same_adapter(mp4: Path) -> None:
    yt = create_adapter("youtube")
    assert "shorts" in yt.default_limits and "video" in yt.default_limits
    assert yt.validate_media(mp4, probe(duration=45), "shorts").ok
    assert not yt.validate_media(mp4, probe(duration=400), "shorts").ok  # > 3 minutes
    assert yt.validate_media(mp4, probe(duration=400), "video").ok
    assert "shorts" not in [c.name for c in get_registry().values()]  # no duplicate adapter


def test_unknown_variant_is_reported(mp4: Path) -> None:
    with pytest.raises(UnsupportedOperationError, match="no variant"):
        create_adapter("instagram").validate_media(mp4, probe(), "stories-xyz")


def test_limits_come_from_config_yaml() -> None:
    cfg = load_app_config().platforms.platforms
    a = create_adapter("instagram", cfg["instagram"])
    assert a.limits_for("reels").max_duration_seconds == 900
    assert create_adapter("youtube", cfg["youtube"]).limits_for("shorts").max_duration_seconds == 180


def test_third_party_adapters_can_be_registered() -> None:
    class Dummy(PlatformAdapter):
        name = "dummy"
        display_name = "Dummy"

    register(Dummy)
    try:
        assert create_adapter("dummy").display_name == "Dummy"
    finally:
        get_registry()  # registry copy; remove for isolation
        from platforms import registry

        registry._REGISTRY.pop("dummy", None)
