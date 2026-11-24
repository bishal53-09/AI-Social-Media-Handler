"""Security helpers: secret redaction, safe subprocess execution, file checks
and a credential vault with pluggable encryption.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.core.exceptions import DependencyMissingError, PathSecurityError, ValidationFailedError

logger = logging.getLogger(__name__)

SECRET_ENV_NAMES = (
    "ANTHROPIC_API_KEY",
    "META_APP_SECRET",
    "TIKTOK_CLIENT_SECRET",
    "GOOGLE_CLIENT_SECRET",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
)

_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)((?:api[_-]?key|secret|token|password|access[_-]?key)[\"']?\s*[:=]\s*[\"']?)[^\s\"',&]{4,}"),
]

REDACTED = "***REDACTED***"


def _missing_program(name: str) -> str:
    return f"A required program ('{name}') is missing. Re-run the installer (setup.sh) or `make update` to install it."


def redact(text: str, extra_values: Sequence[str] = ()) -> str:
    """Remove secrets from ``text``.

    Redacts the current values of known secret environment variables, any
    ``extra_values`` and common token shapes (API keys, bearer tokens,
    ``key=value`` secrets).
    """
    values = [os.environ.get(name, "") for name in SECRET_ENV_NAMES]
    values.extend(extra_values)
    for value in values:
        if value and len(value) >= 4:
            text = text.replace(value, REDACTED)
    for pattern in _SECRET_PATTERNS:
        replacement = (lambda m: f"{m.group(1)}{REDACTED}") if pattern.groups else REDACTED
        text = pattern.sub(replacement, text)
    return text


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``data`` with values of secret-looking keys replaced."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if re.search(r"(?i)(secret|token|password|api_key|access_key)", key):
            out[key] = REDACTED if value else value
        elif isinstance(value, Mapping):
            out[key] = redact_mapping(value)
        else:
            out[key] = value
    return out


# ---------------------------------------------------------------------------
# Subprocess
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def which(binary: str) -> str | None:
    return shutil.which(binary)


def run_command(
    args: Sequence[str],
    *,
    timeout: float | None = 600,
    check: bool = True,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run an external program safely.

    * ``args`` is a list; the shell is never used, so user-controlled values
      cannot inject commands.
    * The executable must be found on PATH (or be an absolute path).
    * Output is captured and secrets are redacted from error messages.
    * ``env`` entries are added to (not substituted for) the current environment.
    """
    if isinstance(args, str):  # pragma: no cover - defensive
        raise TypeError("run_command requires a sequence of arguments, not a string")
    argv = [str(a) for a in args]
    if not argv:
        raise ValueError("empty command")
    exe = argv[0] if os.path.isabs(argv[0]) else which(argv[0])
    if exe is None:
        raise DependencyMissingError(
            _missing_program(argv[0]),
            details={"program": argv[0]},
        )
    argv[0] = exe
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
            env={**os.environ, **env} if env else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValidationFailedError(f"Command timed out after {timeout}s: {Path(argv[0]).name}") from exc
    result = CommandResult(argv, proc.returncode, proc.stdout, proc.stderr)
    if check and proc.returncode != 0:
        from app.core.exceptions import MediaProcessingError

        tail = redact(proc.stderr.strip()[-2000:])
        raise MediaProcessingError(
            f"{Path(argv[0]).name} exited with code {proc.returncode}",
            details={"stderr": tail},
        )
    return result


def run_command_streaming(
    args: Sequence[str],
    *,
    on_line: Callable[[str], None],
    should_cancel: Callable[[], bool] | None = None,
    timeout: float | None = None,
) -> int:
    """Run a program, feeding each stdout line to ``on_line``.

    Same safety rules as :func:`run_command` (no shell, PATH-resolved
    executable). Used for long ffmpeg runs: ``-progress pipe:1`` lines are
    parsed by the caller, and ``should_cancel`` is polled between lines so a
    cancelled job terminates the process promptly. stderr is spooled to a
    temporary file (so it can never fill a pipe and deadlock) and its tail is
    attached to the error on failure.

    Returns the exit code; raises ``CancelledError`` on cancellation.
    """
    import tempfile
    import threading

    from app.core.exceptions import CancelledError, MediaProcessingError

    argv = [str(a) for a in args]
    exe = argv[0] if os.path.isabs(argv[0]) else which(argv[0])
    if exe is None:
        raise DependencyMissingError(
            _missing_program(argv[0]),
            details={"program": argv[0]},
        )
    argv[0] = exe

    timed_out = threading.Event()
    with tempfile.TemporaryFile(mode="w+") as err:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=err,
            stdin=subprocess.DEVNULL,
            text=True,
            shell=False,
        )

        def _kill_on_timeout() -> None:
            timed_out.set()
            proc.kill()

        timer = threading.Timer(timeout, _kill_on_timeout) if timeout else None
        if timer:
            timer.start()
        cancelled = False
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                on_line(line.rstrip("\n"))
                if should_cancel and should_cancel():
                    cancelled = True
                    proc.terminate()
                    break
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        finally:
            if timer:
                timer.cancel()
            if proc.poll() is None:  # pragma: no cover - safety net
                proc.kill()
                proc.wait()
        if cancelled:
            raise CancelledError("Cancelled by user.")
        if timed_out.is_set():
            raise MediaProcessingError(f"{Path(exe).name} timed out after {timeout}s")
        if proc.returncode != 0:
            err.seek(0)
            tail = redact(err.read().strip()[-2000:])
            raise MediaProcessingError(f"{Path(exe).name} exited with code {proc.returncode}", details={"stderr": tail})
        return proc.returncode


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


def validate_file(
    path: Path,
    *,
    allowed_extensions: Sequence[str],
    max_size_bytes: int | None = None,
) -> int:
    """Check that ``path`` is a regular file with an allowed extension and size.

    Returns the file size in bytes.
    """
    if path.is_symlink():
        # Symlinks are allowed only if they resolve to a regular file; callers
        # still apply ensure_within() to the resolved path.
        pass
    if not path.is_file():
        raise ValidationFailedError("Not a regular file.", details={"path": str(path)})
    ext = path.suffix.lower()
    if ext not in {e.lower() for e in allowed_extensions}:
        raise ValidationFailedError(f"File type '{ext}' is not allowed.", details={"path": str(path)})
    size = path.stat().st_size
    if max_size_bytes is not None and size > max_size_bytes:
        raise ValidationFailedError(
            "File exceeds the configured size limit.",
            details={"path": str(path), "size": size, "limit": max_size_bytes},
        )
    return size


def restrict_permissions(path: Path) -> None:
    """chmod 600 — owner read/write only (used for .env and credential files)."""
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# Credential vault
# ---------------------------------------------------------------------------


class Cipher(Protocol):
    """Encrypts credential payloads at rest. Implementations must be reversible."""

    name: str

    def encrypt(self, plaintext: bytes) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> bytes: ...


class PlaintextCipher:
    """No encryption; file permissions (0600) are the only protection.

    TODO(security): add an OS-keychain or Fernet-based cipher before platform
    OAuth tokens are stored (Phase 6). The vault format already records the
    cipher name so existing files can be migrated.
    """

    name = "plaintext"

    def encrypt(self, plaintext: bytes) -> bytes:
        return plaintext

    def decrypt(self, ciphertext: bytes) -> bytes:
        return ciphertext


class CredentialVault:
    """Stores per-account credentials (e.g. OAuth tokens) as one file per key.

    Files live in ``<data_dir>/credentials`` with mode 0600. The vault never
    logs payloads. Keys are restricted to a safe character set.
    """

    _KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")

    def __init__(self, directory: Path, cipher: Cipher | None = None) -> None:
        self.directory = directory
        self.cipher: Cipher = cipher or PlaintextCipher()

    def _path(self, key: str) -> Path:
        if not self._KEY_RE.match(key):
            raise PathSecurityError("Invalid credential key.")
        return self.directory / f"{key}.json"

    def put(self, key: str, payload: Mapping[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        os.chmod(self.directory, stat.S_IRWXU)
        envelope = {
            "cipher": self.cipher.name,
            "data": self.cipher.encrypt(json.dumps(dict(payload)).encode()).decode("latin-1"),
        }
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(envelope, fh)
        os.replace(tmp, path)

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.exists():
            return None
        envelope = json.loads(path.read_text())
        if envelope.get("cipher") != self.cipher.name:
            raise ValidationFailedError(
                "Credential file was written with a different cipher.",
                details={"expected": self.cipher.name, "found": envelope.get("cipher")},
            )
        data: dict[str, Any] = json.loads(self.cipher.decrypt(envelope["data"].encode("latin-1")))
        return data

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if path.exists():
            path.unlink()
            return True
        return False
