"""Logging setup with secret redaction.

A filter scrubs every record (message and arguments) with
:func:`app.core.security.redact`, so a secret accidentally interpolated into a
log line never reaches the console or the log file.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from app.core.security import redact

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
        except Exception:  # pragma: no cover  # noqa: S110 - logging must never raise
            pass
        return True


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure the root logger. Safe to call repeatedly."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        if getattr(handler, "_asmh", False):
            root.removeHandler(handler)

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                log_dir / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
            )
        )
    for handler in handlers:
        handler.setFormatter(logging.Formatter(_FORMAT))
        handler.addFilter(RedactingFilter())
        handler._asmh = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    # Third-party libraries can log full request headers at DEBUG.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
