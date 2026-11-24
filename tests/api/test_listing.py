"""Pagination, search, filters and sorting on list endpoints, plus media file serving for previews."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import make_video, needs_ffmpeg

V1 = "/api/v1"


def _project(client: TestClient, name: str, **kw: Any) -> dict[str, Any]:
    r = client.post(f"{V1}/projects", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _index(client: TestClient, project: dict[str, Any], files: dict[str, bytes]) -> None:
    root = Path(project["path"])
    for rel, data in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    assert client.post(f"{V1}/projects/{project['id']}/media/scan", json={"probe": False}).status_code == 200


def _paths(r: Any) -> list[str]:
    assert r.status_code == 200, r.text
    return [m["relative_path"] for m in r.json()["items"]]


# --- projects ---------------------------------------------------------------------------------------


def test_project_list_search_sort_and_paging(client: TestClient) -> None:
    for n, d in [("Alpine trip", "mountains"), ("Beach day", None), ("City_walk 100%", "urban")]:
        _project(client, n, description=d)
    names = lambda r: [p["name"] for p in r.json()["items"]]  # noqa: E731
    assert names(client.get(f"{V1}/projects", params={"sort": "name", "order": "asc"})) == [
        "Alpine trip",
        "Beach day",
        "City_walk 100%",
    ]
    assert names(client.get(f"{V1}/projects", params={"q": "MOUNTAIN"})) == ["Alpine trip"]  # description, any case
    # LIKE wildcards in the search text are literal, not patterns
    assert names(client.get(f"{V1}/projects", params={"q": "%"})) == ["City_walk 100%"]
    assert names(client.get(f"{V1}/projects", params={"q": "_"})) == ["City_walk 100%"]
    page = client.get(f"{V1}/projects", params={"sort": "name", "order": "asc", "limit": 2, "offset": 2}).json()
    assert page["total"] == 3 and page["limit"] == 2 and page["offset"] == 2
    assert [p["name"] for p in page["items"]] == ["City_walk 100%"]
    assert client.get(f"{V1}/projects", params={"sort": "path"}).status_code == 422
    assert client.get(f"{V1}/projects", params={"limit": 0}).status_code == 422


# --- media ------------------------------------------------------------------------------------------


def test_media_list_filters_search_and_sort(client: TestClient) -> None:
    p = _project(client, "Media")
    _index(
        client,
        p,
        {
            "media/raw/2026-11-20/beach.mp4": b"a" * 10,
            "media/raw/2026-11-22/city.mp4": b"b" * 30,
            "media/raw/2026-11-23/photo.jpg": b"c" * 20,
            "media/stitched/2026-11-24/pano.mp4": b"d" * 40,
        },
    )
    url = f"{V1}/projects/{p['id']}/media"
    assert _paths(client.get(url, params={"q": "BEACH"})) == ["media/raw/2026-11-20/beach.mp4"]
    assert _paths(client.get(url, params={"kind": "image"})) == ["media/raw/2026-11-23/photo.jpg"]
    assert _paths(client.get(url, params={"stage": "stitched"})) == ["media/stitched/2026-11-24/pano.mp4"]
    assert _paths(client.get(url, params={"day_from": "2026-11-22", "day_to": "2026-11-23"})) == [
        "media/raw/2026-11-23/photo.jpg",
        "media/raw/2026-11-22/city.mp4",
    ]
    assert _paths(client.get(url, params={"sort": "size", "order": "asc"}))[0].endswith("beach.mp4")
    assert _paths(client.get(url, params={"sort": "size", "order": "desc"}))[0].endswith("pano.mp4")
    assert _paths(client.get(url, params={"sort": "name", "order": "asc"}))[0].endswith("beach.mp4")
    page = client.get(url, params={"sort": "name", "order": "asc", "limit": 2, "offset": 3}).json()
    assert page["total"] == 4 and len(page["items"]) == 1
    assert client.get(url, params={"sort": "sha256"}).status_code == 422
    assert client.get(url, params={"media_type": "vr"}).status_code == 422
    assert client.get(url, params={"day_from": "yesterday"}).status_code == 422


def test_media_search_matches_display_name(client: TestClient) -> None:
    p = _project(client, "Names")
    _index(client, p, {"media/raw/2026-11-23/clip001.mp4": b"x"})
    asset = client.get(f"{V1}/projects/{p['id']}/media").json()["items"][0]
    client.patch(f"{V1}/projects/{p['id']}/media/{asset['id']}", json={"display_name": "Sunset timelapse"})
    assert _paths(client.get(f"{V1}/projects/{p['id']}/media", params={"q": "sunset"})) == [asset["relative_path"]]


# --- media file serving -------------------------------------------------------------------------------


def test_media_file_serves_bytes_with_range_support(client: TestClient) -> None:
    p = _project(client, "Serve")
    data = bytes(range(256)) * 4
    _index(client, p, {"media/raw/2026-11-23/a.mp4": data})
    asset = client.get(f"{V1}/projects/{p['id']}/media").json()["items"][0]
    url = f"{V1}/projects/{p['id']}/media/{asset['id']}/file"

    full = client.get(url)
    assert full.status_code == 200 and full.content == data
    assert full.headers["content-type"] == "video/mp4"
    assert full.headers["accept-ranges"] == "bytes"
    assert full.headers["x-content-type-options"] == "nosniff"

    part = client.get(url, headers={"Range": "bytes=10-19"})
    assert part.status_code == 206 and part.content == data[10:20]
    assert part.headers["content-range"] == f"bytes 10-19/{len(data)}"
    tail = client.get(url, headers={"Range": "bytes=1000-"})
    assert tail.status_code == 206 and tail.content == data[1000:]


def test_media_file_errors_and_traversal(client: TestClient, tmp_path: Path) -> None:
    p = _project(client, "Guard")
    _index(client, p, {"media/raw/2026-11-23/a.mp4": b"x"})
    base = f"{V1}/projects/{p['id']}/media"
    asset = client.get(base).json()["items"][0]
    assert client.get(f"{base}/nope/file").status_code == 404
    assert client.get(f"{V1}/projects/ghost/media/{asset['id']}/file").status_code == 404
    assert client.get(f"{base}/{asset['id']}/file", params={"variant": "proxy"}).status_code == 404  # no proxy yet
    assert client.get(f"{base}/{asset['id']}/file", params={"variant": "../../etc"}).status_code == 422
    # path segments in the id never reach the filesystem: ids are looked up in the index
    assert client.get(f"{base}/..%2F..%2Fapp.db/file").status_code == 404

    # a file deleted from disk is a clean 404, not a 500
    (Path(p["path"]) / "media/raw/2026-11-23/a.mp4").unlink()
    assert client.get(f"{base}/{asset['id']}/file").status_code == 404


def test_media_file_refuses_symlink_escaping_the_project(client: TestClient, tmp_path: Path) -> None:
    p = _project(client, "Link")
    secret = tmp_path / "secret.mp4"
    secret.write_bytes(b"top secret")
    link = Path(p["path"]) / "media/raw/2026-11-23/link.mp4"
    link.parent.mkdir(parents=True)
    link.symlink_to(secret)
    client.post(f"{V1}/projects/{p['id']}/media/scan", json={"probe": False})
    items = client.get(f"{V1}/projects/{p['id']}/media").json()["items"]
    for a in items:
        r = client.get(f"{V1}/projects/{p['id']}/media/{a['id']}/file")
        assert r.status_code in (403, 404) and b"top secret" not in r.content


@needs_ffmpeg
def test_media_file_prefers_proxy_when_available(client: TestClient) -> None:
    p = _project(client, "Proxy")
    root = Path(p["path"])
    make_video(root / "media/raw/2026-11-23/a.mp4", seconds=1)
    proxy = make_video(root / "media/proxies/a_proxy.mp4", size="160x80", seconds=1)
    client.post(f"{V1}/projects/{p['id']}/media/scan")
    asset = next(a for a in client.get(f"{V1}/projects/{p['id']}/media").json()["items"] if a["stage"] == "raw")
    from app.database.session import Database  # set the proxy link as the pipeline would
    from app.models import MediaAsset

    db: Database = client.app.state.db  # type: ignore[attr-defined]
    with db.session() as s:
        s.get(MediaAsset, asset["id"]).proxy_path = "media/proxies/a_proxy.mp4"  # type: ignore[union-attr]
        s.commit()
    base = f"{V1}/projects/{p['id']}/media/{asset['id']}/file"
    assert client.get(base).content == proxy.read_bytes()
    assert client.get(base, params={"variant": "original"}).content == (root / asset["relative_path"]).read_bytes()


# --- posts ------------------------------------------------------------------------------------------


def test_post_list_search_filters_sort_and_paging(client: TestClient) -> None:
    p = _project(client, "Posts")
    other = _project(client, "Other")

    def make(title: str, project: dict[str, Any], platforms: list[dict[str, Any]], caption: str | None = None) -> None:
        body = {
            "project_id": project["id"],
            "title": title,
            "output_file": "media/ready/x.mp4",
            "caption": caption,
            "platforms": platforms,
        }
        r = client.post(f"{V1}/content-posts", json=body)
        assert r.status_code == 201, r.text

    make("Sunset ride", p, [{"platform": "youtube", "variant": "shorts"}], caption="golden hour")
    make("Beach party", p, [{"platform": "tiktok", "variant": "video"}])
    make("Mountain hike", other, [{"platform": "youtube", "variant": "video"}, {"platform": "tiktok"}])

    titles = lambda **kw: [x["title"] for x in client.get(f"{V1}/content-posts", params=kw).json()["items"]]  # noqa: E731
    assert sorted(titles()) == ["Beach party", "Mountain hike", "Sunset ride"]
    assert titles(project_id=other["id"]) == ["Mountain hike"]
    assert titles(q="GOLDEN") == ["Sunset ride"]  # caption search
    assert sorted(titles(platform="youtube")) == ["Mountain hike", "Sunset ride"]
    assert sorted(titles(platform="tiktok")) == ["Beach party", "Mountain hike"]
    assert sorted(titles(status="draft")) == ["Beach party", "Mountain hike", "Sunset ride"]
    assert titles(status="published") == []
    assert titles(platform="youtube", status="published") == []
    assert titles(sort="title", order="asc") == ["Beach party", "Mountain hike", "Sunset ride"]
    assert titles(created_from="2999-01-01") == []
    assert len(titles(created_from="2000-01-01", created_to="2999-01-01")) == 3
    page = client.get(f"{V1}/content-posts", params={"sort": "title", "order": "asc", "limit": 2, "offset": 2}).json()
    assert page["total"] == 3 and [x["title"] for x in page["items"]] == ["Sunset ride"]
    assert client.get(f"{V1}/content-posts", params={"sort": "caption"}).status_code == 422
    assert client.get(f"{V1}/content-posts", params={"created_from": "soon"}).status_code == 422


def test_platform_post_list_filters(client: TestClient) -> None:
    p = _project(client, "Plat")
    client.post(
        f"{V1}/content-posts",
        json={
            "project_id": p["id"],
            "title": "T",
            "output_file": "media/ready/x.mp4",
            "platforms": [{"platform": "youtube", "variant": "shorts"}, {"platform": "tiktok"}],
        },
    )
    assert client.get(f"{V1}/posts", params={"platform": "tiktok"}).json()["total"] == 1
    assert (
        client.get(f"{V1}/posts", params={"status": "draft", "sort": "platform", "order": "asc"}).json()["items"][0][
            "platform"
        ]
        == "tiktok"
    )
    assert client.get(f"{V1}/posts", params={"sort": "caption"}).status_code == 422


# --- jobs -------------------------------------------------------------------------------------------


def test_job_list_filters_search_and_paging(client: TestClient) -> None:
    p = _project(client, "Jobs")
    for _ in range(3):
        assert client.post(f"{V1}/jobs", json={"type": "media.scan", "project_id": p["id"]}).status_code == 202
    total = client.get(f"{V1}/jobs").json()["total"]
    assert total == 3
    assert client.get(f"{V1}/jobs", params={"type": "media.scan"}).json()["total"] == 3
    assert client.get(f"{V1}/jobs", params={"type": "pipeline.process"}).json()["total"] == 0
    assert client.get(f"{V1}/jobs", params={"q": "SCAN"}).json()["total"] == 3
    assert client.get(f"{V1}/jobs", params={"q": "zzz"}).json()["total"] == 0
    assert client.get(f"{V1}/jobs", params={"created_from": "2999-01-01"}).json()["total"] == 0
    assert client.get(f"{V1}/jobs", params={"created_to": "2000-01-01"}).json()["total"] == 0
    page = client.get(f"{V1}/jobs", params={"limit": 2, "offset": 2, "sort": "created", "order": "asc"}).json()
    assert page["total"] == 3 and len(page["items"]) == 1 and page["limit"] == 2
    assert client.get(f"{V1}/jobs", params={"sort": "params"}).status_code == 422
