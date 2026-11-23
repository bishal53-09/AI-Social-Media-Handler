"""Application exception hierarchy.

Every error raised deliberately by the application derives from ``AppError`` so
the API layer can map it to a stable HTTP response and the CLI can print an
actionable message instead of a traceback.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected, user-facing errors."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(AppError):
    status_code = 500
    code = "configuration_error"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_failed"


class PathSecurityError(AppError):
    """A path escaped its allowed root (path traversal) or is otherwise unsafe."""

    status_code = 400
    code = "unsafe_path"


class DependencyMissingError(AppError):
    """An external tool (ffmpeg, ffprobe, ...) is not installed."""

    status_code = 503
    code = "dependency_missing"


class MediaProcessingError(AppError):
    status_code = 500
    code = "media_processing_failed"


class InvalidStateTransitionError(AppError):
    status_code = 409
    code = "invalid_state_transition"


class UnsupportedOperationError(AppError):
    """The operation is a documented extension point that is not implemented yet."""

    status_code = 501
    code = "unsupported_operation"


class ConsentRequiredError(AppError):
    """An action would send user media outside this machine without consent."""

    status_code = 403
    code = "consent_required"


class AIResponseError(AppError):
    """An AI provider returned a response that failed validation or was refused."""

    status_code = 502
    code = "ai_response_invalid"


class CancelledError(AppError):
    status_code = 409
    code = "cancelled"
