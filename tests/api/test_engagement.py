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
