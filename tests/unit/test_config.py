from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings, load_app_config
from app.core.exceptions import ConfigurationError


def test_default_yaml_files_load_and_validate() -> None:
    cfg = load_app_config()
    assert cfg.app.host == "127.0.0.1"
    assert [s.name for s in cfg.pipeline.stages][:4] == ["ingest", "probe", "thumbnails", "proxies"]
    implemented = {s.name for s in cfg.pipeline.stages if s.implemented}
    assert implemented == {"ingest", "probe", "thumbnails", "proxies", "validation"}
    assert cfg.platforms.require_approval is True
    assert cfg.ai.media_transmission.allow_frames is False  # no media leaves by default
    assert "youtube-short" in cfg.export_presets


def test_pipeline_yaml_matches_orchestrator_registry() -> None:
    from app.pipeline.orchestrator import STAGES

    cfg = load_app_config()
    for stage in cfg.pipeline.stages:
        assert stage.name in STAGES, stage.name
        assert STAGES[stage.name].implemented == stage.implemented, stage.name


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PORT", "9001")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-value-123")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.app_port == 9001
    assert s.anthropic_api_key is not None
    assert "sk-ant-secret-value-123" not in repr(s)
    assert "sk-ant-secret-value-123" not in str(s.model_dump())
    assert s.configured_secrets()["anthropic_api_key"] is True


def test_empty_api_key_means_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert Settings(_env_file=None).anthropic_api_key is None  # type: ignore[call-arg]


def test_localhost_detection() -> None:
    assert Settings(_env_file=None, app_host="127.0.0.1").is_localhost_bind  # type: ignore[call-arg]
    assert not Settings(_env_file=None, app_host="0.0.0.0").is_localhost_bind  # type: ignore[call-arg]


def test_relative_sqlite_url_is_anchored_to_repo_root() -> None:
    s = Settings(_env_file=None, database_url="sqlite:///./data/app.db")  # type: ignore[call-arg]
    assert s.resolved_database_url.startswith("sqlite:////")
    assert s.resolved_database_url.endswith("/data/app.db")
    assert Settings(_env_file=None, database_url="sqlite://").resolved_database_url == "sqlite://"  # type: ignore[call-arg]


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    for name in ("app", "pipeline", "ai", "platforms", "export-presets"):
        (tmp_path / f"{name}.yaml").write_text("{}\n")
    (tmp_path / "ai.yaml").write_text("a: [unclosed\n")
    with pytest.raises(ConfigurationError, match="Invalid YAML"):
        load_app_config(tmp_path)


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="Missing configuration file"):
        load_app_config(tmp_path)


def test_out_of_range_value_is_rejected(tmp_path: Path) -> None:
    for name in ("app", "pipeline", "ai", "platforms", "export-presets"):
        (tmp_path / f"{name}.yaml").write_text("{}\n")
    (tmp_path / "pipeline.yaml").write_text("thumbnails: {position: 7}\n")
    with pytest.raises(ConfigurationError):
        load_app_config(tmp_path)
