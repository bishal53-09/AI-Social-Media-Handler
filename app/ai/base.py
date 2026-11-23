"""Provider abstraction. Add a provider by subclassing :class:`AIProvider`
and registering it in ``app.ai.registry``."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import MediaTransmissionConfig
from app.core.exceptions import ConsentRequiredError

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class ImagePart:
    data: bytes
    media_type: str = "image/jpeg"


Part = TextPart | ImagePart


def enforce_media_consent(parts: Sequence[Part], policy: MediaTransmissionConfig) -> None:
    """Refuse to transmit images unless the user enabled it in configuration.

    Called by every provider before any network I/O, so no code path can send
    footage frames without consent.
    """
    images = [p for p in parts if isinstance(p, ImagePart)]
    if not images:
        return
    if not policy.allow_frames:
        raise ConsentRequiredError(
            "This request would send video frames to the AI provider. Set "
            "media_transmission.allow_frames: true in config/ai.yaml (or pass --allow-frames "
            "on the CLI) to consent.",
            details={"frames": len(images)},
        )
    if len(images) > policy.max_frames_per_clip:
        raise ConsentRequiredError(
            f"Refusing to send {len(images)} frames; the configured limit is {policy.max_frames_per_clip}."
        )


class AIProvider(ABC):
    name: str

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        parts: Sequence[Part],
        response_model: type[T],
        max_tokens: int | None = None,
    ) -> T:
        """Return a validated ``response_model`` instance or raise ``AIResponseError``."""
