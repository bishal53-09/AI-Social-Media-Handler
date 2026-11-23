"""Configuration loading.

Two sources are combined:

* **Environment / ``.env``** — machine-specific values and all secrets
  (:class:`Settings`).
* **``config/*.yaml``** — non-secret, version-controlled defaults
  (:class:`AppConfig`).

Secrets are held as ``SecretStr`` so they never appear in ``repr`` or logs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.exceptions import ConfigurationError
from app.core.paths import CONFIG_DIR, REPO_ROOT, expand


class Settings(BaseSettings):
    """Environment-derived settings (see ``.env.example``)."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)

    database_url: str = "sqlite:///./data/app.db"

    anthropic_api_key: SecretStr | None = None

    meta_app_id: str | None = None
    meta_app_secret: SecretStr | None = None
    tiktok_client_key: str | None = None
    tiktok_client_secret: SecretStr | None = None
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None

    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: SecretStr | None = None
    s3_secret_key: SecretStr | None = None
    s3_region: str | None = None

    media_root: str = "./projects"

    # Let the API run `git fetch` (at most every 15 minutes) to tell the UI when
    # a newer version is available. Nothing is installed automatically.
    update_check: bool = True

    # Where runtime state (SQLite DB, credentials) lives. Derived from the
    # DATABASE_URL by default; override with DATA_DIR.
    data_dir: str = "./data"
    config_dir: str | None = None

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _empty_secret_is_none(cls, v: Any) -> Any:
        return None if v in ("", None) else v

    # -- derived paths -----------------------------------------------------

    @property
    def data_path(self) -> Path:
        return expand(self.data_dir)

    @property
    def media_root_path(self) -> Path:
        return expand(self.media_root)

    @property
    def config_path(self) -> Path:
        return expand(self.config_dir) if self.config_dir else CONFIG_DIR

    @property
    def resolved_database_url(self) -> str:
        """``DATABASE_URL`` with relative SQLite paths anchored at the repo root."""
        prefix = "sqlite:///"
        url = self.database_url
        if url.startswith(prefix) and not url.startswith("sqlite:////") and url != "sqlite://":
            rel = url[len(prefix) :]
            if rel and rel != ":memory:":
                return f"{prefix}{expand(rel)}"
        return url

    @property
    def is_localhost_bind(self) -> bool:
        return self.app_host in {"127.0.0.1", "localhost", "::1"}

    def configured_secrets(self) -> dict[str, bool]:
        """Which credentials are set — booleans only, never the values."""
        return {
            "anthropic_api_key": self.anthropic_api_key is not None,
            "meta": bool(self.meta_app_id and self.meta_app_secret),
            "tiktok": bool(self.tiktok_client_key and self.tiktok_client_secret),
            "google": bool(self.google_client_id and self.google_client_secret),
            "s3": bool(self.s3_bucket and self.s3_access_key and self.s3_secret_key),
        }


class MediaConfig(BaseModel):
    video_extensions: list[str] = [".mp4", ".mov", ".m4v", ".mkv", ".osv", ".insv"]
    image_extensions: list[str] = [".jpg", ".jpeg", ".png", ".dng", ".heic"]
    max_file_size_gb: float = 200
    scan_folders: list[str] = ["media/raw", "media/stitched"]

    @property
    def max_file_size_bytes(self) -> int:
        return int(self.max_file_size_gb * 1024**3)


class ProjectsConfig(BaseModel):
    default_root: str = "./projects"
    allowed_roots: list[str] = ["~"]


class AppSection(BaseModel):
    name: str = "AI Social Media Handler"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://127.0.0.1:3000", "http://localhost:3000"]


class LoggingConfig(BaseModel):
    level: str = "INFO"
    directory: str = "logs"


class ThumbnailConfig(BaseModel):
    width: int = 480
    position: float = Field(default=0.1, ge=0, le=1)
    format: str = "jpg"
    quality: int = Field(default=85, ge=1, le=100)


class ProxyConfig(BaseModel):
    height: int = 540
    equirect_height: int = 960
    video_codec: str = "libx264"
    preset: str = "veryfast"
    crf: int = 28
    audio_codec: str = "aac"
    audio_bitrate: str = "96k"
    timeout_seconds: int = 3600


class FfmpegConfig(BaseModel):
    binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    probe_timeout_seconds: int = 60


class StageConfig(BaseModel):
    name: str
    implemented: bool = False


class PipelineConfig(BaseModel):
    stages: list[StageConfig] = []
    thumbnails: ThumbnailConfig = ThumbnailConfig()
    proxies: ProxyConfig = ProxyConfig()
    ffmpeg: FfmpegConfig = FfmpegConfig()


class AnthropicConfig(BaseModel):
    model: str = "claude-opus-5-5"
    max_tokens: int = 16000
    effort: str = "high"
    timeout_seconds: int = 300
    # Opt in to server-side fallback if the primary model declines a request.
    server_side_fallbacks: bool = True


class MediaTransmissionConfig(BaseModel):
    allow_frames: bool = False
    max_frames_per_clip: int = Field(default=8, ge=1, le=20)
    frame_width: int = Field(default=768, ge=128, le=2048)
    jpeg_quality: int = Field(default=80, ge=30, le=95)


class EditPlanConfig(BaseModel):
    max_segments: int = 60
    max_duration_seconds: float = 600
    allowed_formats: list[str] = ["9:16", "16:9", "1:1"]
    fov_range: tuple[float, float] = (30, 120)


class AIConfig(BaseModel):
    provider: str = "anthropic"
    anthropic: AnthropicConfig = AnthropicConfig()
    media_transmission: MediaTransmissionConfig = MediaTransmissionConfig()
    edit_plan: EditPlanConfig = EditPlanConfig()


class PlatformsConfig(BaseModel):
    publishing: dict[str, Any] = {"require_approval": True}
    platforms: dict[str, dict[str, Any]] = {}

    @property
    def require_approval(self) -> bool:
        return bool(self.publishing.get("require_approval", True))


class AppConfig(BaseModel):
    app: AppSection = AppSection()
    logging: LoggingConfig = LoggingConfig()
    projects: ProjectsConfig = ProjectsConfig()
    media: MediaConfig = MediaConfig()
    pipeline: PipelineConfig = PipelineConfig()
    ai: AIConfig = AIConfig()
    platforms: PlatformsConfig = PlatformsConfig()
    export_presets: dict[str, dict[str, Any]] = {}


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Missing configuration file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"{path} must contain a mapping at the top level.")
    return data


def load_app_config(config_dir: Path | None = None) -> AppConfig:
    """Load and validate every ``config/*.yaml`` file."""
    d = config_dir or CONFIG_DIR
    app_yaml = _read_yaml(d / "app.yaml")
    try:
        return AppConfig(
            app=app_yaml.get("app", {}),
            logging=app_yaml.get("logging", {}),
            projects=app_yaml.get("projects", {}),
            media=app_yaml.get("media", {}),
            pipeline=PipelineConfig.model_validate(_read_yaml(d / "pipeline.yaml")),
            ai=AIConfig.model_validate(_read_yaml(d / "ai.yaml")),
            platforms=PlatformsConfig.model_validate(_read_yaml(d / "platforms.yaml")),
            export_presets=_read_yaml(d / "export-presets.yaml").get("presets", {}),
        )
    except ValueError as exc:  # pydantic.ValidationError subclasses ValueError
        raise ConfigurationError(f"Invalid configuration: {exc}") from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    return load_app_config(get_settings().config_path)


def clear_config_caches() -> None:
    get_settings.cache_clear()
    get_app_config.cache_clear()
