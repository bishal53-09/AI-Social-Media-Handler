"""Comments, interactions, analytics and the post-first API, using a fake platform adapter.

The shipped adapters implement no engagement, so a ``FakePlatform`` (registered only for
these tests) stands in for a real API. Tests also assert the honest behaviour for the
real adapters: unsupported operations report why and invent no data.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

from platforms import registry
from platforms.base import (
    Analytics,
    Capability,
    CommentPage,
    Credentials,
    MediaLimits,
    PlatformAdapter,
    RemoteComment,
)

V1 = "/api/v1"
ALL = frozenset(Capability)


class FakePlatform(PlatformAdapter):
    name = "fakeplatform"
    display_name = "Fake Platform"
    default_limits: ClassVar[dict[str, MediaLimits]] = {"video": MediaLimits()}
    api_capabilities = ALL
    implemented_capabilities = ALL - {Capability.PUBLISH, Capability.DELETE_COMMENT}

    #: Shared across instances because the service creates a new adapter per request.
    comments: ClassVar[list[RemoteComment]] = []
    calls: ClassVar[list[tuple[str, Any]]] = []
    fail_next: ClassVar[bool] = False

    def list_comments(
        self, credentials: Credentials, external_post_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> CommentPage:
        type(self).calls.append(("list", cursor))
        if cursor is None:
            return CommentPage(comments=type(self).comments[:2], next_cursor="p2")
        return CommentPage(comments=type(self).comments[2:])

    def get_analytics(self, credentials: Credentials, external_post_id: str) -> Analytics:
        return Analytics(
            collected_at=datetime(2026, 11, 24, 12, 0, tzinfo=UTC),
            metrics={"views": 100, "likes": 10, "comments": 3, "reach": 90},
        )

    def reply_to_comment(
        self, credentials: Credentials, external_post_id: str, parent_comment_id: str, text: str
    ) -> RemoteComment:
        if type(self).fail_next:
            type(self).fail_next = False
            raise RuntimeError("platform exploded with token=abc123secret")
        type(self).calls.append(("reply", (parent_comment_id, text)))
        return RemoteComment(external_id=f"reply-{len(type(self).calls)}", text=text, author_name="me")

    def like_comment(
        self, credentials: Credentials, external_post_id: str, comment_id: str, *, like: bool = True
    ) -> None:
        type(self).calls.append(("like", (comment_id, like)))

    def set_comment_hidden(
        self, credentials: Credentials, external_post_id: str, comment_id: str, *, hidden: bool = True
    ) -> None:
        type(self).calls.append(("hide", (comment_id, hidden)))

    def like_post(self, credentials: Credentials, external_post_id: str, *, like: bool = True) -> None:
        type(self).calls.append(("like_post", like))


def _remote(i: int, **kw: Any) -> RemoteComment:
    return RemoteComment(
        external_id=f"c{i}",
        text=f"comment {i}",
        author_name=f"user{i}",
        like_count=i,
        posted_at=datetime(2026, 11, 24, 10, i, tzinfo=UTC),
        **kw,
    )


@pytest.fixture(autouse=True)
def fake_platform() -> Iterator[None]:
    registry.get_registry()
    registry.register(FakePlatform)
    FakePlatform.comments = [_remote(1), _remote(2), _remote(3)]
    FakePlatform.calls = []
    FakePlatform.fail_next = False
    yield
    registry._REGISTRY.pop("fakeplatform", None)


def _project(client: TestClient) -> dict[str, Any]:
    existing = client.get(f"{V1}/projects").json()["items"]
    if existing:
        return existing[0]  # type: ignore[no-any-return]
    r = client.post(f"{V1}/projects", json={"name": "Trip"})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _create_post(client: TestClient, platforms: list[dict[str, Any]] | None = None, **kw: Any) -> dict[str, Any]:
    project = _project(client)
    body = {
        "project_id": project["id"],
        "title": "Sunset ride",
        "output_file": "media/ready/ride.mp4",
        "caption": "Golden hour",
        "hashtags": ["#ride", "sunset"],
        "platforms": platforms or [{"platform": "fakeplatform"}, {"platform": "youtube", "variant": "shorts"}],
        **kw,
    }
    r = client.post(f"{V1}/content-posts", json=body)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _publish(client: TestClient, platform_post_id: str, external_id: str = "ext-1") -> None:
    """Mark a platform post published through the real state machine."""
    from app.services.post_service import PostService

    session = client.app.state.db.session()  # type: ignore[attr-defined]
    try:
        svc = PostService(session)
        svc.approve(platform_post_id, "tester")
        svc.queue(platform_post_id)
        attempt = svc.begin_attempt(platform_post_id)
        svc.mark_processing(platform_post_id)
        svc.complete_attempt(platform_post_id, attempt, external_post_id=external_id, external_url="https://x/y")
    finally:
        session.close()


def _pid(post: dict[str, Any], platform: str) -> str:
    return next(p["id"] for p in post["platform_posts"] if p["platform"] == platform)


# --- creating posts ---------------------------------------------------------------------


def test_create_post_makes_one_draft_per_platform(client: TestClient) -> None:
    post = _create_post(client)
    assert post["title"] == "Sunset ride" and post["hashtags"] == ["ride", "sunset"]
    assert {(p["platform"], p["variant"], p["status"]) for p in post["platform_posts"]} == {
        ("fakeplatform", None, "draft"),
        ("youtube", "shorts", "draft"),
    }
    assert post["totals"] == {} and post["comment_total"] == 0
    listing = client.get(f"{V1}/content-posts").json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == post["id"]


def test_create_post_validation(client: TestClient) -> None:
    project = _project(client)
    base = {"project_id": project["id"], "title": "t", "output_file": "media/ready/a.mp4"}
    assert client.post(f"{V1}/content-posts", json={**base, "platforms": []}).status_code == 422
    assert client.post(f"{V1}/content-posts", json={**base, "platforms": [{"platform": "myspace"}]}).status_code == 422
    dup = [{"platform": "fakeplatform"}, {"platform": "fakeplatform"}]
    assert client.post(f"{V1}/content-posts", json={**base, "platforms": dup}).status_code == 422
    bad_variant = [{"platform": "youtube", "variant": "nope"}]
    assert client.post(f"{V1}/content-posts", json={**base, "platforms": bad_variant}).status_code == 422
    escape = {**base, "output_file": "../../etc/passwd", "platforms": [{"platform": "fakeplatform"}]}
    assert client.post(f"{V1}/content-posts", json=escape).status_code == 422
    assert client.get(f"{V1}/content-posts").json()["total"] == 0  # failed creates leave nothing behind
    missing = {**base, "project_id": "nope", "platforms": [{"platform": "fakeplatform"}]}
    assert client.post(f"{V1}/content-posts", json=missing).status_code == 404
    assert client.get(f"{V1}/content-posts/none").status_code == 404


# --- honest behaviour ---------------------------------------------------------------------


def test_sync_requires_a_published_post(client: TestClient) -> None:
    post = _create_post(client)
    r = client.post(f"{V1}/posts/{_pid(post, 'fakeplatform')}/sync")
    assert r.status_code == 409


def test_real_adapters_report_not_implemented_and_invent_nothing(client: TestClient) -> None:
    post = _create_post(client)
    yt = _pid(post, "youtube")
    _publish(client, yt, "yt-123")
    report = client.post(f"{V1}/posts/{yt}/sync").json()
    assert report["comments"]["status"] == "unsupported" and "not implemented" in report["comments"]["message"]
    assert report["analytics"]["status"] == "unsupported"
    assert client.get(f"{V1}/posts/{yt}/comments").json() == {"items": [], "total": 0}
    detail = client.get(f"{V1}/content-posts/{post['id']}").json()
    ytd = next(p for p in detail["platform_posts"] if p["platform"] == "youtube")
    assert ytd["metrics"] == {} and ytd["snapshots"] == []
    assert ytd["capabilities"]["list_comments"] == "planned"
    assert ytd["capabilities"]["like_comment"] == "unavailable"
    assert "videos.rate" in ytd["engagement_notes"]
    for path, method in [
        (f"{V1}/posts/{yt}/like", "post"),
    ]:
        r = getattr(client, method)(path)
        assert r.status_code == 501
    assert client.get(f"{V1}/posts/{yt}/comments").json()["total"] == 0
    # nothing was attempted, so there is nothing in the audit trail
    assert ytd["actions"] == []


def test_unavailable_capability_message_differs_from_planned(client: TestClient) -> None:
    post = _create_post(client)
    fake = _pid(post, "fakeplatform")
    _publish(client, fake)
    client.post(f"{V1}/posts/{fake}/sync")
    cid = client.get(f"{V1}/posts/{fake}/comments").json()["items"][0]["id"]
    r = client.delete(f"{V1}/posts/{fake}/comments/{cid}")  # in api_capabilities, not implemented
    assert r.status_code == 501 and "not implemented" in r.json()["error"]["message"]


# --- sync -------------------------------------------------------------------------------


def test_sync_stores_paged_comments_and_metrics(client: TestClient) -> None:
    post = _create_post(client)
    fake = _pid(post, "fakeplatform")
    _publish(client, fake)
    report = client.post(f"{V1}/posts/{fake}/sync").json()
    assert report["comments"] == {"status": "ok", "count": 3, "message": None}
    assert report["analytics"]["status"] == "ok"
    assert [c[0] for c in FakePlatform.calls] == ["list", "list"]  # followed the cursor

    comments = client.get(f"{V1}/posts/{fake}/comments").json()
    assert comments["total"] == 3 and comments["items"][0]["external_id"] == "c3"  # newest first

    detail = client.get(f"{V1}/content-posts/{post['id']}").json()
    assert detail["totals"] == {"views": 100, "likes": 10, "comments": 3}  # reach is not additive
    assert detail["comment_total"] == 3
    fp = next(p for p in detail["platform_posts"] if p["platform"] == "fakeplatform")
    assert fp["metrics"]["reach"] == 90 and len(fp["snapshots"]) == 1 and fp["comment_count"] == 3

    client.post(f"{V1}/posts/{fake}/sync")  # idempotent: no duplicate comments, history grows
    assert client.get(f"{V1}/posts/{fake}/comments").json()["total"] == 3
    again = client.get(f"{V1}/content-posts/{post['id']}").json()
    assert len(next(p for p in again["platform_posts"] if p["platform"] == "fakeplatform")["snapshots"]) == 2


def test_comment_deleted_on_platform_is_flagged(client: TestClient) -> None:
    post = _create_post(client)
    fake = _pid(post, "fakeplatform")
    _publish(client, fake)
    client.post(f"{V1}/posts/{fake}/sync")
    FakePlatform.comments = FakePlatform.comments[:1]
    client.post(f"{V1}/posts/{fake}/sync")
    items = client.get(f"{V1}/posts/{fake}/comments").json()["items"]
    assert {c["external_id"]: c["removed_remotely"] for c in items} == {"c1": False, "c2": True, "c3": True}
    summary = client.get(f"{V1}/content-posts").json()["items"][0]
    assert summary["comment_total"] == 1  # removed comments are not counted


# --- interactions -----------------------------------------------------------------------


def _synced(client: TestClient) -> tuple[str, list[dict[str, Any]]]:
    post = _create_post(client)
    fake = _pid(post, "fakeplatform")
    _publish(client, fake)
    client.post(f"{V1}/posts/{fake}/sync")
    return fake, client.get(f"{V1}/posts/{fake}/comments").json()["items"]


def test_reply_like_hide_and_audit_trail(client: TestClient) -> None:
    fake, items = _synced(client)
    target = next(c for c in items if c["external_id"] == "c1")

    r = client.post(f"{V1}/posts/{fake}/comments/{target['id']}/reply", json={"text": "  thanks!  "})
    assert r.status_code == 201
    reply = r.json()
    assert reply["is_own"] and reply["text"] == "thanks!" and reply["parent_external_id"] == "c1"

    liked = client.post(f"{V1}/posts/{fake}/comments/{target['id']}/like").json()
    assert liked["liked_by_me"] is True
    assert (
        client.post(f"{V1}/posts/{fake}/comments/{target['id']}/like", json={"like": False}).json()["liked_by_me"]
        is False
    )
    hidden = client.post(f"{V1}/posts/{fake}/comments/{target['id']}/hide").json()
    assert hidden["hidden"] is True
    assert client.post(f"{V1}/posts/{fake}/like").status_code == 204

    parent = next(c for c in client.get(f"{V1}/posts/{fake}/comments").json()["items"] if c["id"] == target["id"])
    assert parent["reply_count"] == 1
    assert (
        client.get(f"{V1}/posts/{fake}/comments", params={"include_hidden": "false"}).json()["total"] == 3
    )  # 3 visible of 4

    sent = [c[0] for c in FakePlatform.calls if c[0] != "list"]
    assert sent == ["reply", "like", "like", "hide", "like_post"]

    detail = client.get(f"{V1}/content-posts/{_content_id(client)}").json()
    actions = next(p for p in detail["platform_posts"] if p["id"] == fake)["actions"]
    assert {a["action"] for a in actions} == {"reply", "like_comment", "unlike_comment", "hide_comment", "like_post"}
    assert all(a["outcome"] == "succeeded" for a in actions)


def _content_id(client: TestClient) -> str:
    return client.get(f"{V1}/content-posts").json()["items"][0]["id"]  # type: ignore[no-any-return]


def test_reply_validation_and_ownership(client: TestClient) -> None:
    fake, items = _synced(client)
    cid = items[0]["id"]
    assert client.post(f"{V1}/posts/{fake}/comments/{cid}/reply", json={"text": "   "}).status_code == 422
    assert client.post(f"{V1}/posts/{fake}/comments/{cid}/reply", json={"text": "x" * 2001}).status_code == 422
    assert client.post(f"{V1}/posts/{fake}/comments/nope/reply", json={"text": "hi"}).status_code == 404
    assert not [c for c in FakePlatform.calls if c[0] == "reply"]
    other = _create_post(client)
    other_fake = _pid(other, "fakeplatform")
    _publish(client, other_fake, "ext-2")
    r = client.post(f"{V1}/posts/{other_fake}/comments/{cid}/reply", json={"text": "hi"})
    assert r.status_code == 404  # a comment cannot be reached through another post


def test_failed_interaction_is_audited_and_redacted(client: TestClient) -> None:
    fake, items = _synced(client)
    FakePlatform.fail_next = True
    r = client.post(f"{V1}/posts/{fake}/comments/{items[0]['id']}/reply", json={"text": "hello"})
    assert r.status_code == 502 and "abc123secret" not in r.text
    detail = client.get(f"{V1}/content-posts/{_content_id(client)}").json()
    actions = next(p for p in detail["platform_posts"] if p["id"] == fake)["actions"]
    failed = [a for a in actions if a["outcome"] == "failed"]
    assert len(failed) == 1 and "abc123secret" not in (failed[0]["error"] or "")
    assert client.get(f"{V1}/posts/{fake}/comments").json()["total"] == 3  # no phantom reply stored


# --- analytics ------------------------------------------------------------------------------


def test_analytics_overview(client: TestClient) -> None:
    empty = client.get(f"{V1}/analytics/overview").json()
    assert empty["published_posts"] == 0 and empty["totals"] == {} and empty["top_posts"] == []

    post = _create_post(client)
    fake, yt = _pid(post, "fakeplatform"), _pid(post, "youtube")
    _publish(client, fake)
    _publish(client, yt, "yt-1")
    client.post(f"{V1}/posts/{fake}/sync")
    client.post(f"{V1}/posts/{yt}/sync")  # unsupported: contributes no data

    o = client.get(f"{V1}/analytics/overview").json()
    assert o["published_posts"] == 2 and o["posts_with_data"] == 1
    assert o["totals"]["views"] == 100
    by = {b["platform"]: b for b in o["by_platform"]}
    assert by["youtube"]["posts_with_data"] == 0 and by["youtube"]["totals"] == {}
    assert by["fakeplatform"]["totals"]["likes"] == 10
    assert o["top_posts"][0]["title"] == "Sunset ride" and o["last_collected_at"]


def test_settings_lists_platform_capabilities(client: TestClient) -> None:
    platforms = {p["name"]: p for p in client.get(f"{V1}/settings").json()["platforms"]}
    assert platforms["tiktok"]["capabilities"]["list_comments"] == "unavailable"
    assert platforms["instagram"]["capabilities"]["reply_comment"] == "planned"
    assert all(v != "implemented" for p in platforms.values() for v in p["capabilities"].values())


# --- multi-media posts and picker data ---------------------------------------------------------------


def _index_media(client: TestClient, project: dict[str, Any], names: list[str]) -> list[str]:
    """Put placeholder files in the project and index them (no ffprobe needed)."""
    from pathlib import Path

    root = Path(project["path"])
    for n in names:
        f = root / n
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
    client.post(f"{V1}/projects/{project['id']}/media/scan", json={"probe": False})
    return names


def test_picker_data_lists_postable_media_only(client: TestClient) -> None:
    project = _project(client)
    _index_media(client, project, ["media/raw/2026-11-23/a.mp4", "media/proxies/a.mp4"])
    everything = client.get(f"{V1}/projects/{project['id']}/media").json()["items"]
    postable = client.get(f"{V1}/projects/{project['id']}/media", params={"postable": "true"}).json()["items"]
    assert {m["stage"] for m in postable}.isdisjoint({"proxy", "thumbnail"})
    assert any(m["relative_path"] == "media/raw/2026-11-23/a.mp4" for m in postable)
    assert len(postable) <= len(everything)
    assert client.get(f"{V1}/projects/{project['id']}/media/nope/thumbnail").status_code == 404


def test_post_with_several_media_files(client: TestClient) -> None:
    project = _project(client)
    files = _index_media(client, project, ["media/raw/a.mp4", "media/raw/b.mp4"])
    body = {
        "project_id": project["id"],
        "title": "Carousel",
        "media_files": files,
        "platforms": [{"platform": "instagram", "variant": "carousel"}],
    }
    r = client.post(f"{V1}/content-posts", json=body)
    assert r.status_code == 201, r.text
    post = r.json()
    assert post["media_files"] == files and post["output_file"] == files[0]
    detail = client.get(f"{V1}/content-posts/{post['id']}").json()
    assert detail["media_files"] == files


def test_multiple_media_rejected_where_a_platform_takes_one(client: TestClient) -> None:
    project = _project(client)
    files = _index_media(client, project, ["media/raw/a.mp4", "media/raw/b.mp4"])
    body = {"project_id": project["id"], "title": "t", "media_files": files}
    r = client.post(f"{V1}/content-posts", json={**body, "platforms": [{"platform": "youtube", "variant": "shorts"}]})
    assert r.status_code == 422 and "1 media file" in r.text
    r = client.post(f"{V1}/content-posts", json={**body, "platforms": [{"platform": "instagram", "variant": "reels"}]})
    assert r.status_code == 422
    assert client.get(f"{V1}/content-posts").json()["total"] == 0


def test_selected_media_must_be_indexed_and_unique(client: TestClient) -> None:
    project = _project(client)
    _index_media(client, project, ["media/raw/a.mp4"])
    base = {"project_id": project["id"], "title": "t", "platforms": [{"platform": "youtube"}]}
    assert client.post(f"{V1}/content-posts", json={**base, "media_files": ["media/raw/ghost.mp4"]}).status_code == 422
    assert client.post(f"{V1}/content-posts", json={**base, "media_files": ["../x.mp4"]}).status_code == 422
    dup = ["media/raw/a.mp4", "media/raw/a.mp4"]
    assert client.post(f"{V1}/content-posts", json={**base, "media_files": dup}).status_code == 422
    assert client.post(f"{V1}/content-posts", json=base).status_code == 422  # nothing selected
    ok = client.post(f"{V1}/content-posts", json={**base, "media_files": ["media/raw/a.mp4"]})
    assert ok.status_code == 201


# --- upload and rename ---------------------------------------------------------------------------------


def test_upload_copies_into_raw_and_never_overwrites(client: TestClient) -> None:
    from pathlib import Path

    project = _project(client)
    url = f"{V1}/projects/{project['id']}/media/upload"
    r = client.post(url, files=[("files", ("../../My Clip!.MP4", b"data", "video/mp4"))])
    assert r.status_code == 201, r.text
    [asset] = r.json()
    assert asset["relative_path"].startswith("media/raw/") and asset["stage"] == "raw"
    assert asset["name"] == "My Clip_.mp4" and ".." not in asset["relative_path"]
    assert (Path(project["path"]) / asset["relative_path"]).read_bytes() == b"data"
    again = client.post(url, files=[("files", ("My Clip!.mp4", b"other", "video/mp4"))])
    assert again.status_code == 409
    assert (Path(project["path"]) / asset["relative_path"]).read_bytes() == b"data"
    assert client.post(url, files=[("files", ("notes.exe", b"x", "application/octet-stream"))]).status_code == 422
    assert client.post(url, files=[("files", ("empty.mp4", b"", "video/mp4"))]).status_code == 422


def test_rename_changes_only_the_display_name(client: TestClient) -> None:
    from pathlib import Path

    project = _project(client)
    [asset] = client.post(
        f"{V1}/projects/{project['id']}/media/upload", files=[("files", ("a.mp4", b"x", "video/mp4"))]
    ).json()
    url = f"{V1}/projects/{project['id']}/media/{asset['id']}"
    renamed = client.patch(url, json={"display_name": "  Sunset ride final  "}).json()
    assert renamed["name"] == "Sunset ride final" and renamed["relative_path"] == asset["relative_path"]
    assert (Path(project["path"]) / asset["relative_path"]).exists()
    client.post(f"{V1}/projects/{project['id']}/media/scan", json={"probe": False})  # rescan keeps the name
    listed = client.get(f"{V1}/projects/{project['id']}/media").json()["items"]
    assert any(m["name"] == "Sunset ride final" for m in listed)
    assert client.patch(url, json={"display_name": ""}).json()["name"] == "a.mp4"
    assert client.patch(f"{V1}/projects/{project['id']}/media/nope", json={"display_name": "x"}).status_code == 404


def test_processed_and_ready_files_are_indexed_for_posts(client: TestClient) -> None:
    project = _project(client)
    _index_media(client, project, ["media/processed/cut.mp4", "media/ready/final.mp4"])
    stages = {
        m["stage"]
        for m in client.get(f"{V1}/projects/{project['id']}/media", params={"postable": "true"}).json()["items"]
    }
    assert {"processed", "ready"} <= stages
