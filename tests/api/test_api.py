from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import AppConfig, Settings
from app.main import create_app
from tests.conftest import make_video, needs_ffmpeg

V1 = "/api/v1"


def create_project(client: TestClient, name: str = "Trip", **kw: Any) -> dict[str, Any]:
    r = client.post(f"{V1}/projects", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def wait_for(client: TestClient, job_id: str, timeout: float = 60) -> dict[str, Any]:
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"{V1}/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job  # type: ignore[no-any-return]
        time.sleep(0.1)
    raise AssertionError("job did not finish")


# --- health & settings ------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    r = client.get(f"{V1}/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["database"] == "ok" and body["version"]
    assert set(body) >= {"ffmpeg", "ffprobe", "python"}


def test_settings_endpoint_never_exposes_secrets(settings: Settings, config: AppConfig) -> None:
    secret_settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=settings.database_url,
        data_dir=settings.data_dir,
        media_root=settings.media_root,
        anthropic_api_key="sk-ant-api03-SUPERSECRET123",
        meta_app_id="meta-id",
        meta_app_secret="meta-secret-xyz",
        google_client_id="goog-id",
        google_client_secret="goog-secret-xyz",
    )
    with TestClient(create_app(secret_settings, config)) as c:
        r = c.get(f"{V1}/settings")
    assert r.status_code == 200
    text = r.text
    for secret in ("SUPERSECRET123", "meta-secret-xyz", "goog-secret-xyz"):
        assert secret not in text
    body = r.json()
    assert body["ai_key_configured"] is True and body["localhost_only"] is True
    assert body["require_publish_approval"] is True and body["ai_frame_upload_allowed"] is False
    plat = {p["name"]: p for p in body["platforms"]}
    assert plat["youtube"]["credentials_configured"] is True
    assert all(p["publishing_implemented"] is False for p in body["platforms"])
    stages = {s["name"]: s["implemented"] for s in body["pipeline_stages"]}
    assert stages["proxies"] is True and stages["reframing"] is False


def test_only_loopback_host_headers_are_accepted(client: TestClient) -> None:
    r = client.get(f"{V1}/health", headers={"host": "evil.example.com"})
    assert r.status_code == 400  # DNS-rebinding protection
    assert client.get(f"{V1}/health", headers={"host": "127.0.0.1:8000"}).status_code == 200


def test_cors_only_allows_the_local_dashboard(client: TestClient) -> None:
    ok = client.options(
        f"{V1}/projects", headers={"origin": "http://localhost:3000", "access-control-request-method": "POST"}
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options(
        f"{V1}/projects", headers={"origin": "https://evil.example", "access-control-request-method": "POST"}
    )
    assert "access-control-allow-origin" not in bad.headers


# --- projects ----------------------------------------------------------------------------------


def test_project_crud_flow(client: TestClient, settings: Settings) -> None:
    assert client.get(f"{V1}/projects").json() == {"items": [], "total": 0}
    p = create_project(client, "My Trip", description="d", default_camera="DJI Osmo 360 II")
    assert p["id"] == "my-trip" and Path(p["path"]).is_dir()
    assert Path(p["path"]).parent == settings.media_root_path.resolve()

    listed = client.get(f"{V1}/projects").json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == "my-trip"

    detail = client.get(f"{V1}/projects/my-trip").json()
    assert detail["exists_on_disk"] is True and detail["media_count"] == 0 and detail["day_count"] == 0
    assert detail["settings"]["default_camera"] == "DJI Osmo 360 II"


def test_project_validation_and_errors(client: TestClient, tmp_path: Path) -> None:
    assert client.post(f"{V1}/projects", json={"name": ""}).status_code == 422
    assert client.post(f"{V1}/projects", json={"name": "   "}).status_code == 422
    assert client.post(f"{V1}/projects", json={}).status_code == 422
    assert client.get(f"{V1}/projects/nope").status_code == 404

    r = client.post(f"{V1}/projects", json={"name": "Evil", "path": str(tmp_path / "outside")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsafe_path"
    assert not (tmp_path / "outside").exists()

    create_project(client, "Dup", path=str(Path(client.get(f"{V1}/settings").json()["media_root"]) / "dup"))
    again = client.post(
        f"{V1}/projects",
        json={"name": "Dup", "path": str(Path(client.get(f"{V1}/settings").json()["media_root"]) / "dup")},
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "conflict"


def test_error_responses_have_a_stable_shape(client: TestClient) -> None:
    body = client.get(f"{V1}/projects/missing").json()
    assert set(body["error"]) == {"code", "message", "details"} and body["error"]["code"] == "not_found"


def test_days_endpoints(client: TestClient) -> None:
    p = create_project(client, "Calendar")
    assert client.get(f"{V1}/projects/nonexistent/days").status_code == 404
    assert client.get(f"{V1}/projects/{p['id']}/days").json() == {"items": []}
    assert client.get(f"{V1}/projects/{p['id']}/days/2026-11-23").status_code == 404
    assert client.get(f"{V1}/projects/{p['id']}/days/not-a-date").status_code == 422
    assert client.get(f"{V1}/projects/{p['id']}/days/2026-13-45").status_code == 422


def test_media_listing_validates_query_parameters(client: TestClient) -> None:
    p = create_project(client, "Q")
    base = f"{V1}/projects/{p['id']}/media"
    assert client.get(base).json()["total"] == 0
    assert client.get(base, params={"kind": "audio"}).status_code == 422
    assert client.get(base, params={"limit": 0}).status_code == 422
    assert client.get(base, params={"day": "yesterday"}).status_code == 422
    assert client.get(f"{V1}/projects/none/media").status_code == 404
    assert client.post(f"{V1}/projects/none/media/scan").status_code == 404


@needs_ffmpeg
def test_scan_media_and_days_end_to_end(client: TestClient) -> None:
    p = create_project(client, "Scan Me")
    root = Path(p["path"])
    make_video(root / "media/raw/2026-11-23/a.mp4", seconds=1)
    make_video(root / "media/stitched/2026-11-24/pano.mp4", size="640x320", seconds=1)

    scan = client.post(f"{V1}/projects/{p['id']}/media/scan").json()
    assert scan["new"] == 2 and scan["probed"] == 2 and scan["days_written"] >= 1

    media = client.get(f"{V1}/projects/{p['id']}/media").json()
    assert media["total"] == 2
    pano = next(m for m in media["items"] if m["relative_path"].endswith("pano.mp4"))
    assert pano["media_type"] == "360-stitched" and pano["probe"]["width"] == 640
    only_raw = client.get(f"{V1}/projects/{p['id']}/media", params={"stage": "raw"}).json()
    assert [m["relative_path"] for m in only_raw["items"]] == ["media/raw/2026-11-23/a.mp4"]

    days = client.get(f"{V1}/projects/{p['id']}/days").json()["items"]
    assert {d["date"]: d["clip_count"] for d in days} == {"2026-11-23": 1, "2026-11-24": 1}
    day = client.get(f"{V1}/projects/{p['id']}/days/2026-11-23").json()
    assert day["clips"][0]["source"]["file"] == "media/raw/2026-11-23/a.mp4"

    again = client.post(f"{V1}/projects/{p['id']}/media/scan", json={"probe": False}).json()
    assert again["new"] == 0 and again["unchanged"] == 2
    assert client.get(f"{V1}/projects/{p['id']}").json()["media_count"] == 2


# --- jobs ------------------------------------------------------------------------------------------


def test_job_validation(client: TestClient) -> None:
    p = create_project(client, "Jobs")
    assert client.post(f"{V1}/jobs", json={"type": "rm -rf", "project_id": p["id"]}).status_code == 422
    assert client.post(f"{V1}/jobs", json={"type": "media.scan", "project_id": "ghost"}).status_code == 404
    r = client.post(
        f"{V1}/jobs", json={"type": "pipeline.process", "project_id": p["id"], "params": {"stages": ["reframing"]}}
    )
    assert r.status_code == 501 and r.json()["error"]["code"] == "unsupported_operation"
    r = client.post(
        f"{V1}/jobs", json={"type": "pipeline.process", "project_id": p["id"], "params": {"stages": ["teleport"]}}
    )
    assert r.status_code == 422
    assert client.get(f"{V1}/jobs/job_missing").status_code == 404
    assert client.post(f"{V1}/jobs/job_missing/cancel").status_code == 404
    assert client.get(f"{V1}/jobs", params={"status": "bogus"}).status_code == 422


@needs_ffmpeg
def test_scan_and_pipeline_jobs_run_in_background(client: TestClient) -> None:
    p = create_project(client, "Bg")
    root = Path(p["path"])
    make_video(root / "media/raw/2026-11-23/a.mp4", seconds=1)

    scan_job = client.post(f"{V1}/jobs", json={"type": "media.scan", "project_id": p["id"]})
    assert scan_job.status_code == 202
    done = wait_for(client, scan_job.json()["id"])
    assert done["status"] == "completed" and done["result"]["new"] == 1

    job = client.post(f"{V1}/jobs", json={"type": "pipeline.process", "project_id": p["id"]}).json()
    done = wait_for(client, job["id"])
    assert done["status"] == "completed", done
    assert done["progress"] == 1.0 and done["result"]["succeeded"] == 1
    stages = [e["stage"] for e in done["events"] if e["event"] == "completed"]
    assert stages == ["ingest", "probe", "thumbnails", "proxies", "validation"]

    media = client.get(f"{V1}/projects/{p['id']}/media").json()["items"][0]
    assert media["thumbnail_path"] and media["proxy_path"] and media["sha256"]
    assert (root / media["proxy_path"]).is_file()

    listing = client.get(f"{V1}/jobs", params={"project_id": p["id"], "status": "completed"}).json()
    assert listing["total"] == 2
    assert client.post(f"{V1}/jobs/{job['id']}/cancel").status_code == 409  # already finished


def test_cancel_a_queued_job(client: TestClient) -> None:
    p = create_project(client, "Cancel")
    runner = client.app.state.job_runner  # type: ignore[attr-defined]
    runner.submit = lambda _id: None  # keep the job queued
    job = client.post(f"{V1}/jobs", json={"type": "media.scan", "project_id": p["id"]}).json()
    assert job["status"] == "queued"
    cancelled = client.post(f"{V1}/jobs/{job['id']}/cancel").json()
    assert cancelled["status"] == "cancelled" and cancelled["cancel_requested"] is True


# --- posts ------------------------------------------------------------------------------------------


def test_posts_listing_is_read_only_and_empty(client: TestClient) -> None:
    assert client.get(f"{V1}/posts").json() == {"items": [], "total": 0}
    assert client.post(f"{V1}/posts", json={}).status_code == 405


@pytest.mark.parametrize("path", ["/api/v1/health", "/docs", "/openapi.json"])
def test_documentation_and_health_available(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200
