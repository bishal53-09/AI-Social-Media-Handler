"""Common contract for every social platform.

Adapters are independently replaceable: nothing outside this package depends on
a specific platform, and platforms do not import each other. The application
talks to ``PlatformAdapter`` only.

Honesty rule: operations an adapter cannot perform raise
``UnsupportedOperationError`` with a clear message. They never pretend to
succeed. In this milestone **no adapter can publish**.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from app.core.exceptions import UnsupportedOperationError

ASPECT_TOLERANCE = 0.02


@dataclass
class Credentials:
    """OAuth credentials for one connected account.

    Held in memory only. Persist through ``app.core.security.CredentialVault``
    (which can be given an encrypting cipher). ``repr`` never shows tokens.
    """

    platform: str
    account_id: str | None = None
    access_token: str | None = field(default=None, repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_at: datetime | None = None
    scopes: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return (
            f"Credentials(platform={self.platform!r}, account_id={self.account_id!r}, "
            f"access_token={'***' if self.access_token else None}, scopes={self.scopes})"
        )

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and now >= self.expires_at


@dataclass
class MediaLimits:
    max_duration_seconds: float | None = None
    min_duration_seconds: float | None = None
    aspect_ratios: tuple[str, ...] = ()
    max_file_size_mb: float | None = None
    containers: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> MediaLimits:
        return cls(
            max_duration_seconds=cfg.get("max_duration_seconds"),
            min_duration_seconds=cfg.get("min_duration_seconds"),
            aspect_ratios=tuple(cfg.get("aspect_ratios", ())),
            max_file_size_mb=cfg.get("max_file_size_mb"),
            containers=tuple(cfg.get("containers", ())),
        )


@dataclass
class MediaValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PublishRequest:
    post_id: str
    media_path: Path
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    scheduled_at: datetime | None = None
    variant: str | None = None
    #: Stable per post+attempt so a retry can be matched to an earlier upload.
    idempotency_key: str | None = None


@dataclass
class PublishResult:
    #: ``published`` | ``processing`` — failures raise instead.
    status: str
    external_post_id: str | None = None
    external_url: str | None = None
    #: Platform-side upload handle, persisted immediately for reconciliation.
    upload_reference: str | None = None


@dataclass
class RemotePostStatus:
    found: bool
    status: str | None = None
    external_post_id: str | None = None
    external_url: str | None = None


@dataclass
class Analytics:
    collected_at: datetime
    metrics: dict[str, float | int] = field(default_factory=dict)


def _ratio(value: str) -> float:
    w, _, h = value.partition(":")
    return float(w) / float(h)


def validate_against_limits(path: Path, probe: dict[str, Any], limits: MediaLimits) -> MediaValidation:
    """Check a rendered file against platform limits using its ffprobe data."""
    errors: list[str] = []
    warnings: list[str] = []
    container = path.suffix.lower().lstrip(".")
    if limits.containers and container not in limits.containers:
        errors.append(f"Container '.{container}' not accepted (use {', '.join(limits.containers)}).")
    if path.is_file() and limits.max_file_size_mb:
        size_mb = path.stat().st_size / 1024**2
        if size_mb > limits.max_file_size_mb:
            errors.append(f"File is {size_mb:.0f} MB; limit is {limits.max_file_size_mb:.0f} MB.")
    duration = probe.get("duration")
    if duration is None:
        warnings.append("Duration unknown; could not check duration limits.")
    else:
        if limits.max_duration_seconds and duration > limits.max_duration_seconds:
            errors.append(f"Duration {duration:.0f}s exceeds {limits.max_duration_seconds:.0f}s.")
        if limits.min_duration_seconds and duration < limits.min_duration_seconds:
            errors.append(f"Duration {duration:.1f}s is below {limits.min_duration_seconds:.0f}s.")
    w, h = probe.get("width"), probe.get("height")
    if limits.aspect_ratios and w and h:
        actual = w / h
        if not any(abs(actual - _ratio(a)) / _ratio(a) <= ASPECT_TOLERANCE for a in limits.aspect_ratios):
            errors.append(
                f"Aspect ratio {w}x{h} is not one of {', '.join(limits.aspect_ratios)}. "
                "Reframe/export with the matching preset first."
            )
    if probe.get("is_equirectangular"):
        errors.append("Equirectangular 360 video must be reframed before publishing.")
    return MediaValidation(ok=not errors, errors=errors, warnings=warnings)


class PlatformAdapter(ABC):
    """Interface every platform implements."""

    name: ClassVar[str]
    display_name: ClassVar[str]
    #: True only once real, tested publishing exists. Nothing sets this yet.
    publishing_implemented: ClassVar[bool] = False
    #: Variants (e.g. reels, shorts) and their default limits.
    default_limits: ClassVar[dict[str, MediaLimits]] = {}
    #: Environment variables holding the app credentials.
    env_vars: ClassVar[tuple[str, ...]] = ()
    docs_url: ClassVar[str] = ""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    # -- limits / validation (implemented) ------------------------------------

    def limits_for(self, variant: str | None) -> MediaLimits:
        media_cfg = self.config.get("media") or {}
        key = variant or next(iter(self.default_limits), "video")
        if key in media_cfg:
            return MediaLimits.from_config(media_cfg[key])
        if key in self.default_limits:
            return self.default_limits[key]
        raise UnsupportedOperationError(
            f"{self.display_name} has no variant '{key}'.",
            details={"variants": sorted({*media_cfg, *self.default_limits})},
        )

    def validate_media(self, path: Path, probe: dict[str, Any], variant: str | None = None) -> MediaValidation:
        return validate_against_limits(path, probe, self.limits_for(variant))

    # -- operations that need real API integration (not implemented) ------------

    def _unsupported(self, operation: str) -> UnsupportedOperationError:
        return UnsupportedOperationError(
            f"{self.display_name}: {operation}() is not implemented yet. "
            "Publishing requires the official platform API integration (see "
            f"platforms/{self.name}/README.md).",
            details={"platform": self.name, "operation": operation},
        )

    def authenticate(self) -> Credentials:
        raise self._unsupported("authenticate")

    def refresh_credentials(self, credentials: Credentials) -> Credentials:
        raise self._unsupported("refresh_credentials")

    def publish(self, credentials: Credentials, request: PublishRequest) -> PublishResult:
        raise self._unsupported("publish")

    def get_post_status(
        self,
        credentials: Credentials,
        *,
        idempotency_key: str | None = None,
        upload_reference: str | None = None,
        external_post_id: str | None = None,
    ) -> RemotePostStatus:
        """Look a post up on the platform. Used to reconcile ``unknown`` posts."""
        raise self._unsupported("get_post_status")

    def get_analytics(self, credentials: Credentials, external_post_id: str) -> Analytics:
        raise self._unsupported("get_analytics")
