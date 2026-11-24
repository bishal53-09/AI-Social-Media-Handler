"""Common contract for every social platform.

Adapters are independently replaceable: nothing outside this package depends on
a specific platform, and platforms do not import each other. The application
talks to ``PlatformAdapter`` only.

Honesty rule: operations an adapter cannot perform raise
``UnsupportedOperationError`` with a clear message. They never pretend to
succeed. Browser-driven capabilities are reported as ``experimental`` until they have
been verified against the live site.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
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
    #: How many media files one post of this variant may contain.
    max_files: int = 1

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> MediaLimits:
        return cls(
            max_duration_seconds=cfg.get("max_duration_seconds"),
            min_duration_seconds=cfg.get("min_duration_seconds"),
            aspect_ratios=tuple(cfg.get("aspect_ratios", ())),
            max_file_size_mb=cfg.get("max_file_size_mb"),
            containers=tuple(cfg.get("containers", ())),
            max_files=int(cfg.get("max_files", 1)),
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


#: Normalised metric names. Adapters map platform-specific names onto these and may
#: add extra keys. Only ``ADDITIVE_METRICS`` are summed across platforms.
METRIC_KEYS = (
    "views",
    "likes",
    "comments",
    "shares",
    "saves",
    "reach",
    "impressions",
    "watch_time_seconds",
    "avg_view_duration_seconds",
)
ADDITIVE_METRICS = ("views", "likes", "comments", "shares", "saves", "watch_time_seconds")


class Capability(StrEnum):
    """Operations a platform adapter may offer."""

    PUBLISH = "publish"
    ANALYTICS = "analytics"
    LIST_COMMENTS = "list_comments"
    REPLY_COMMENT = "reply_comment"
    LIKE_COMMENT = "like_comment"
    HIDE_COMMENT = "hide_comment"
    DELETE_COMMENT = "delete_comment"
    LIKE_POST = "like_post"


class CapabilityState(StrEnum):
    #: Adapter code exists and is tested against the real API.
    IMPLEMENTED = "implemented"
    #: The platform's official API appears to allow it, but the adapter does not do it yet.
    PLANNED = "planned"
    #: The platform's official API does not offer it (or only to restricted programs).
    UNAVAILABLE = "unavailable"
    #: Browser-automation code exists but has not been verified against the live site;
    #: it works only while the site's markup matches what the code expects.
    EXPERIMENTAL = "experimental"


@dataclass
class RemoteComment:
    """A comment as reported by the platform."""

    external_id: str
    text: str
    author_name: str | None = None
    author_external_id: str | None = None
    parent_external_id: str | None = None
    like_count: int = 0
    reply_count: int = 0
    posted_at: datetime | None = None
    #: True when written by the connected account itself (e.g. our own reply).
    is_own: bool = False
    hidden: bool = False


@dataclass
class CommentPage:
    comments: list[RemoteComment] = field(default_factory=list)
    next_cursor: str | None = None


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
    elif probe.get("possible_360"):
        warnings.append(
            "2:1 frame without 360 metadata. Fine for an ordinary wide video; "
            "if this is an unreframed 360 export, reframe it first."
        )
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
    #: What the platform's official API is believed to allow. This is *documentation of
    #: intent*, to be verified against current platform docs when implementing; it does
    #: not mean the adapter can do it. ``engagement_notes`` explains caveats.
    api_capabilities: ClassVar[frozenset[Capability]] = frozenset()
    #: Capabilities with real, tested adapter code. Nothing sets this yet.
    implemented_capabilities: ClassVar[frozenset[Capability]] = frozenset()
    #: Capabilities driven through a logged-in browser session (see ``platforms.browser``).
    experimental_capabilities: ClassVar[frozenset[Capability]] = frozenset()
    engagement_notes: ClassVar[str] = ""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    # -- capabilities -----------------------------------------------------------

    @classmethod
    def capability_state(cls, capability: Capability) -> CapabilityState:
        if capability in cls.implemented_capabilities:
            return CapabilityState.IMPLEMENTED
        if capability in cls.experimental_capabilities:
            return CapabilityState.EXPERIMENTAL
        if capability in cls.api_capabilities:
            return CapabilityState.PLANNED
        return CapabilityState.UNAVAILABLE

    @classmethod
    def capability_map(cls) -> dict[str, str]:
        return {c.value: cls.capability_state(c).value for c in Capability}

    def require(self, capability: Capability) -> None:
        """Raise a precise error unless this adapter can really perform ``capability``."""
        state = self.capability_state(capability)
        if state in (CapabilityState.IMPLEMENTED, CapabilityState.EXPERIMENTAL):
            return
        reason = (
            "is not supported for this platform" if state is CapabilityState.UNAVAILABLE else "is not implemented yet"
        )
        raise UnsupportedOperationError(
            f"{self.display_name}: {capability.value} {reason}.",
            details={"platform": self.name, "capability": capability.value, "state": state.value},
        )

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
            f"{self.display_name}: {operation}() is not implemented yet. See platforms/{self.name}/README.md).",
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

    # -- engagement: comments and interactions (not implemented) ------------------
    #
    # Contract for implementers: these act on the *connected account's* behalf, must
    # use only official APIs, and must raise on failure rather than return success.

    def list_comments(
        self, credentials: Credentials, external_post_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> CommentPage:
        raise self._unsupported("list_comments")

    def reply_to_comment(
        self, credentials: Credentials, external_post_id: str, parent_comment_id: str, text: str
    ) -> RemoteComment:
        raise self._unsupported("reply_to_comment")

    def like_comment(
        self, credentials: Credentials, external_post_id: str, comment_id: str, *, like: bool = True
    ) -> None:
        raise self._unsupported("like_comment")

    def set_comment_hidden(
        self, credentials: Credentials, external_post_id: str, comment_id: str, *, hidden: bool = True
    ) -> None:
        raise self._unsupported("set_comment_hidden")

    def delete_comment(self, credentials: Credentials, external_post_id: str, comment_id: str) -> None:
        raise self._unsupported("delete_comment")

    def like_post(self, credentials: Credentials, external_post_id: str, *, like: bool = True) -> None:
        raise self._unsupported("like_post")
