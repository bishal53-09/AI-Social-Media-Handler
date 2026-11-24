from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import setup as setup_route
from platforms import browser as browser_mod

V1 = "/api/v1"


@pytest.fixture(autouse=True)
def _reset() -> None:
    setup_route._reset_for_tests()


def test_status_lists_accounts_and_plain_items(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser_mod, "browser_installed", lambda: False)
    body = client.get(f"{V1}/setup/status").json()
    assert {a["name"] for a in body["accounts"]} == {"instagram", "tiktok", "youtube"}
    assert all(a["connected"] is False for a in body["accounts"])
    assert body["any_account_connected"] is False
    ids = {i["id"]: i for i in body["items"]}
    assert ids["browser"]["ok"] is False and ids["browser"]["required"] is False
    assert ids["video-tools"]["required"] is True
    assert body["browser_install"] == "idle"


def test_status_reports_saved_login(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser_mod, "browser_installed", lambda: True)
    profile = browser_mod.profile_root() / "tiktok"
    profile.mkdir(parents=True)
    (Path(profile) / "Cookies").write_text("x")
    body = client.get(f"{V1}/setup/status").json()
    assert {a["name"]: a["connected"] for a in body["accounts"]}["tiktok"] is True
    assert body["any_account_connected"] is True
    assert {i["id"]: i["ok"] for i in body["items"]}["browser"] is True


def test_install_browser_runs_in_background(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(setup_route, "run_command", lambda args, **kw: calls.append(list(args)))
    r = client.post(f"{V1}/setup/browser/install")
    assert r.status_code == 202
    for _ in range(50):
        if client.get(f"{V1}/setup/status").json()["browser_install"] == "done":
            break
        time.sleep(0.05)
    assert client.get(f"{V1}/setup/status").json()["browser_install"] == "done"
    assert calls and calls[0][1:] == ["-m", "playwright", "install", "chromium"]


def test_install_browser_failure_is_plain_language(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(args: list[str], **kw: object) -> None:
        raise RuntimeError("network down: traceback-ish detail")

    monkeypatch.setattr(setup_route, "run_command", boom)
    client.post(f"{V1}/setup/browser/install")
    for _ in range(50):
        body = client.get(f"{V1}/setup/status").json()
        if body["browser_install"] == "failed":
            break
        time.sleep(0.05)
    assert body["browser_install"] == "failed"
    assert "traceback" not in body["browser_install_message"]
