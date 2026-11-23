"""Provider registry."""

from __future__ import annotations

from collections.abc import Callable

from app.ai.base import AIProvider
from app.core.config import AppConfig, Settings
from app.core.exceptions import ConfigurationError

ProviderFactory = Callable[[Settings, AppConfig], AIProvider]
_FACTORIES: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    _FACTORIES[name] = factory


def _anthropic(settings: Settings, config: AppConfig) -> AIProvider:
    from app.ai.anthropic_provider import AnthropicProvider

    key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    return AnthropicProvider(key, config.ai.anthropic, config.ai.media_transmission)


register_provider("anthropic", _anthropic)


def get_provider(settings: Settings, config: AppConfig) -> AIProvider:
    name = config.ai.provider
    if name not in _FACTORIES:
        raise ConfigurationError(f"Unknown AI provider '{name}'. Available: {', '.join(sorted(_FACTORIES))}.")
    return _FACTORIES[name](settings, config)
