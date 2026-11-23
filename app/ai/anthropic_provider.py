"""Anthropic (Claude) provider using the official SDK and structured outputs."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import Any

import anthropic

from app.ai.base import AIProvider, ImagePart, Part, T, TextPart, enforce_media_consent
from app.core.config import AnthropicConfig, MediaTransmissionConfig
from app.core.exceptions import AIResponseError, ConfigurationError
from app.core.security import redact

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None,
        config: AnthropicConfig,
        transmission: MediaTransmissionConfig,
        client: Any | None = None,
    ) -> None:
        if client is None:
            if not api_key:
                raise ConfigurationError(
                    "ANTHROPIC_API_KEY is not set. Add it to your .env file "
                    "(see .env.example). Create a key at https://console.anthropic.com/."
                )
            client = anthropic.Anthropic(api_key=api_key, timeout=config.timeout_seconds, max_retries=2)
        self._client = client
        self._cfg = config
        self._transmission = transmission

    @staticmethod
    def _content(parts: Sequence[Part]) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = []
        for part in parts:
            if isinstance(part, TextPart):
                content.append({"type": "text", "text": part.text})
            elif isinstance(part, ImagePart):
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": part.media_type,
                            "data": base64.standard_b64encode(part.data).decode(),
                        },
                    }
                )
        return content

    def generate(
        self,
        *,
        system: str,
        parts: Sequence[Part],
        response_model: type[T],
        max_tokens: int | None = None,
    ) -> T:
        enforce_media_consent(parts, self._transmission)
        kwargs: dict[str, Any] = {
            "model": self._cfg.model,
            "max_tokens": max_tokens or self._cfg.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": self._content(parts)}],
            "output_format": response_model,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self._cfg.effort},
        }
        if self._cfg.server_side_fallbacks:
            kwargs.update(betas=[FALLBACK_BETA], fallbacks="default")
        try:
            response = self._client.beta.messages.parse(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise AIResponseError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY.") from exc
        except anthropic.RateLimitError as exc:
            raise AIResponseError("Anthropic rate limit reached. Wait and retry.") from exc
        except anthropic.APIConnectionError as exc:
            raise AIResponseError("Could not reach the Anthropic API. Check your network.") from exc
        except anthropic.BadRequestError as exc:
            raise AIResponseError(f"Anthropic rejected the request: {redact(exc.message)}") from exc
        except anthropic.APIStatusError as exc:
            raise AIResponseError(f"Anthropic API error ({exc.status_code}): {redact(exc.message)}") from exc

        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            details = getattr(response, "stop_details", None)
            raise AIResponseError(
                "The model declined this request.",
                details={"category": getattr(details, "category", None)},
            )
        if stop == "max_tokens":
            raise AIResponseError("The response was cut off (max_tokens). Increase ai.yaml max_tokens.")
        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise AIResponseError("The model returned no valid structured output.")
        if not isinstance(parsed, response_model):  # pragma: no cover - SDK guarantees this
            raise AIResponseError("The model returned an unexpected structure.")
        return parsed
