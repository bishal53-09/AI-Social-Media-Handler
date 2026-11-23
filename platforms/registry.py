"""Adapter registry. Third-party adapters can call :func:`register`."""

from __future__ import annotations

from typing import Any

from platforms.base import PlatformAdapter

_REGISTRY: dict[str, type[PlatformAdapter]] = {}


def register(adapter_cls: type[PlatformAdapter]) -> type[PlatformAdapter]:
    """Register an adapter class (usable as a decorator)."""
    name = adapter_cls.name
    if not name:
        raise ValueError("Adapter must define a platform name.")
    _REGISTRY[name] = adapter_cls
    return adapter_cls


def get_registry() -> dict[str, type[PlatformAdapter]]:
    if not _REGISTRY:
        _load_builtin()
    return dict(_REGISTRY)


def create_adapter(name: str, config: dict[str, Any] | None = None) -> PlatformAdapter:
    registry = get_registry()
    if name not in registry:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(f"No adapter registered for '{name}'.", details={"available": sorted(registry)})
    return registry[name](config)


def _load_builtin() -> None:
    from platforms.instagram.adapter import InstagramAdapter
    from platforms.tiktok.adapter import TikTokAdapter
    from platforms.youtube.adapter import YouTubeAdapter

    for cls in (InstagramAdapter, TikTokAdapter, YouTubeAdapter):
        register(cls)
