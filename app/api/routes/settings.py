from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import ConfigDep, SettingsDep
from app.core.security import redact
from app.pipeline.ffmpeg import check_binary
from platforms.browser import profile_root

router = APIRouter(prefix="/settings", tags=["settings"])


class PlatformInfo(BaseModel):
    name: str
    enabled: bool
    api: str | None = None
    #: A browser profile with a saved login exists (not proof it is still signed in).
    session_saved: bool
    publishing_implemented: bool
    capabilities: dict[str, str] = {}
    engagement_notes: str = ""


class SettingsRead(BaseModel):
    """Read-only, secret-free view of the effective configuration."""

    app_env: str
    host: str
    port: int
    localhost_only: bool
    media_root: str
    database: str
    require_publish_approval: bool
    ai_provider: str
    ai_model: str
    ai_key_configured: bool
    ai_frame_upload_allowed: bool
    ffmpeg_available: bool
    ffprobe_available: bool
    pipeline_stages: list[dict[str, Any]]
    platforms: list[PlatformInfo]
    export_presets: list[str]


@router.get("", response_model=SettingsRead)
def read_settings(settings: SettingsDep, config: ConfigDep) -> SettingsRead:
    from platforms.registry import get_registry

    secrets = settings.configured_secrets()
    registry = get_registry()
    plat_cfg = config.platforms.platforms
    platforms = []
    for name, cfg in plat_cfg.items():
        adapter_cls = registry.get(name)
        caps = adapter_cls.capability_map() if adapter_cls else {}
        profile = profile_root() / name
        platforms.append(
            PlatformInfo(
                name=name,
                enabled=bool(cfg.get("enabled")),
                api=cfg.get("api"),
                session_saved=profile.is_dir() and any(profile.iterdir()),
                publishing_implemented=caps.get("publish") in ("implemented", "experimental"),
                capabilities=caps,
                engagement_notes=adapter_cls.engagement_notes if adapter_cls else "",
            )
        )
    return SettingsRead(
        app_env=settings.app_env,
        host=settings.app_host,
        port=settings.app_port,
        localhost_only=settings.is_localhost_bind,
        media_root=str(settings.media_root_path),
        database=redact(settings.resolved_database_url),
        require_publish_approval=config.platforms.require_approval,
        ai_provider=config.ai.provider,
        ai_model=config.ai.anthropic.model,
        ai_key_configured=secrets["anthropic_api_key"],
        ai_frame_upload_allowed=config.ai.media_transmission.allow_frames,
        ffmpeg_available=check_binary(config.pipeline.ffmpeg.binary) is not None,
        ffprobe_available=check_binary(config.pipeline.ffmpeg.ffprobe_binary) is not None,
        pipeline_stages=[s.model_dump() for s in config.pipeline.stages],
        platforms=platforms,
        export_presets=sorted(config.export_presets),
    )
