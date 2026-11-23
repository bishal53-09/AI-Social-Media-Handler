from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy.orm import Session

from app.core.config import AppConfig, Settings
from app.core.exceptions import ConflictError, PathSecurityError, ValidationFailedError
from app.core.paths import SCHEMA_DIR
from app.services.project_service import PROJECT_DIRS, ProjectService, slugify
from app.tracking.json_store import read_json, validate_document, write_json
from app.tracking.repository import ProjectRepository

NOW = "2026-11-23T10:00:00+00:00"


def clip(**over):  # type: ignore[no-untyped-def]
    base = {
        "id": "clip_001",
        "title": "Mountain Ride",
        "source": {"file": "media/raw/2026-11-23/ride.osv", "type": "360", "camera": "DJI Osmo 360 II"},
        "processing": {"status": "completed", "color_profile": None, "lut": None, "edit_version": 1},
        "outputs": [],
        "posts": [],
    }
    base.update(over)
    return base


# --- schemas ---------------------------------------------------------------------


@pytest.mark.parametrize("name", ["project", "day", "clip", "post"])
def test_schema_files_are_valid_json_schema(name: str) -> None:
    Draft202012Validator.check_schema(json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text()))


def test_spec_example_day_document_validates() -> None:
    validate_document("day", {"date": "2026-11-23", "project_id": "travel-2026", "clips": [clip()]})


@pytest.mark.parametrize("bad_file", ["/abs/path.mp4", "../escape.mp4", "media/../../escape.mp4"])
def test_clip_source_must_be_project_relative(bad_file: str) -> None:
    c = clip()
    c["source"]["file"] = bad_file
    with pytest.raises(ValidationFailedError):
        validate_document("clip", c)


def test_day_rejects_bad_date_and_unknown_fields() -> None:
    with pytest.raises(ValidationFailedError):
        validate_document("day", {"date": "23/11/2026", "project_id": "p", "clips": []})
    with pytest.raises(ValidationFailedError):
        validate_document("day", {"date": "2026-11-23", "project_id": "p", "clips": [], "x": 1})


def test_day_validates_nested_clips_through_ref() -> None:
    bad = clip(id="NOT VALID")
    with pytest.raises(ValidationFailedError, match="clips"):
        validate_document("day", {"date": "2026-11-23", "project_id": "p", "clips": [bad]})


def post(**over):  # type: ignore[no-untyped-def]
    base = {
        "id": "post_ab12",
        "platform": "youtube",
        "output_file": "exports/approved/a.mp4",
        "status": "draft",
        "created_at": NOW,
        "updated_at": NOW,
        "attempts": [],
    }
    base.update(over)
    return base


def test_post_schema_status_enum_and_fields() -> None:
    validate_document("post", post())
    validate_document(
        "post",
        post(
            status="published",
            external_post_id="abc",
            external_url="https://x/y",
            published_at=NOW,
            hashtags=["#travel", "osmo"],
            scheduled_at=NOW,
        ),
    )
    with pytest.raises(ValidationFailedError):
        validate_document("post", post(status="sent"))
    with pytest.raises(ValidationFailedError):
        validate_document("post", post(scheduled_at="not-a-date"))


def test_json_store_is_atomic_and_validating(tmp_path: Path) -> None:
    target = tmp_path / "data" / "days" / "2026-11-23.json"
    with pytest.raises(ValidationFailedError):
        write_json(target, {"date": "bad"}, "day")
    assert not target.exists()
    assert not list(tmp_path.rglob("*.tmp"))  # no temp litter after failure
    doc = {"date": "2026-11-23", "project_id": "p", "clips": []}
    write_json(target, doc, "day")
    assert read_json(target, "day") == doc
    assert not list(tmp_path.rglob("*.tmp"))


def test_read_json_reports_corruption(tmp_path: Path) -> None:
    f = tmp_path / "x.json"
    f.write_text("{not json")
    with pytest.raises(ValidationFailedError, match="not valid JSON"):
        read_json(f)


# --- project initialisation ---------------------------------------------------------


def svc(session: Session, settings: Settings, config: AppConfig) -> ProjectService:
    return ProjectService(session, settings, config)


def test_slugify() -> None:
    assert slugify("My Travel Project!") == "my-travel-project"
    assert slugify("Ünïcode Näme") == "unicode-name"
    assert slugify("!!!") == "project"


def test_init_project_creates_full_structure_and_valid_metadata(
    session: Session, settings: Settings, config: AppConfig, tmp_path: Path
) -> None:
    root = tmp_path / "My Travel Project"
    project = svc(session, settings, config).init_project(
        "My Travel Project", root, description="Trip", default_camera="DJI Osmo 360 II"
    )
    assert project.id == "my-travel-project"
    for rel in PROJECT_DIRS:
        assert (root / rel).is_dir(), rel
    # spec'd layout spot checks
    for rel in (
        "media/raw",
        "media/stitched",
        "media/proxies",
        "media/processed/color-graded",
        "media/audio/voiceovers",
        "platforms/youtube-shorts",
        "data/days",
        "exports/approved",
    ):
        assert (root / rel).is_dir()
    meta = read_json(root / "project.json", "project")  # validates against the schema
    assert meta["name"] == "My Travel Project"
    assert meta["settings"]["default_camera"] == "DJI Osmo 360 II"
    assert (root / "data" / "index.json").is_file()
    assert "project.created" in (root / "logs" / "events.jsonl").read_text()


def test_init_project_never_overwrites_existing_work(
    session: Session, settings: Settings, config: AppConfig, tmp_path: Path
) -> None:
    root = tmp_path / "existing"
    (root / "media" / "raw").mkdir(parents=True)
    keep = root / "media" / "raw" / "footage.mp4"
    keep.write_bytes(b"precious")
    svc(session, settings, config).init_project("Existing", root)
    assert keep.read_bytes() == b"precious"
    with pytest.raises(ConflictError, match="already contains a project"):
        svc(session, settings, config).init_project("Existing again", root)
    assert keep.read_bytes() == b"precious"


def test_init_project_defaults_into_media_root_and_dedupes_ids(
    session: Session, settings: Settings, config: AppConfig
) -> None:
    s = svc(session, settings, config)
    a = s.init_project("Trip")
    b = s.init_project("Trip", settings.media_root_path / "trip-copy")
    assert Path(a.path) == (settings.media_root_path / "trip").resolve()
    assert (a.id, b.id) == ("trip", "trip-2")


def test_api_style_creation_is_confined_to_allowed_roots(
    session: Session, settings: Settings, config: AppConfig, tmp_path: Path
) -> None:
    s = svc(session, settings, config)
    with pytest.raises(PathSecurityError):
        s.init_project("Evil", tmp_path / "elsewhere", enforce_roots=True)
    assert not (tmp_path / "elsewhere").exists()
    ok = s.init_project("Fine", settings.media_root_path / "fine", enforce_roots=True)
    assert Path(ok.path).is_dir()
    with pytest.raises(PathSecurityError):  # traversal back out of the root
        s.init_project("Sneaky", settings.media_root_path / ".." / "sneaky", enforce_roots=True)


def test_project_is_portable_between_computers(
    session: Session, settings: Settings, config: AppConfig, tmp_path: Path
) -> None:
    import shutil

    from app.database.migrate import upgrade_database
    from app.database.session import Database

    src = svc(session, settings, config).init_project("Portable", tmp_path / "a" / "portable")
    moved = tmp_path / "other-computer" / "portable"
    shutil.copytree(src.path, moved)

    url = f"sqlite:///{tmp_path / 'second.db'}"
    upgrade_database(url)
    db2 = Database(url)
    try:
        s2 = db2.session()
        reg = ProjectService(s2, settings, config).register(moved)
        assert reg.id == "portable" and reg.path == str(moved.resolve())
        assert ProjectRepository(moved).read_project()["id"] == "portable"
        s2.close()
    finally:
        db2.dispose()
