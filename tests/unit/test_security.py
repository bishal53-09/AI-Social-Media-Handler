from __future__ import annotations

import logging
import os
import stat
from pathlib import Path

import pytest

from app.core.exceptions import DependencyMissingError, PathSecurityError, ValidationFailedError
from app.core.logging import RedactingFilter
from app.core.paths import ensure_within, safe_join, to_project_relative
from app.core.security import (
    CredentialVault,
    redact,
    redact_mapping,
    run_command,
    validate_file,
)

# --- path traversal ---------------------------------------------------------


@pytest.mark.parametrize(
    "evil",
    ["../outside.txt", "a/../../outside.txt", "/etc/passwd", "~/x", "a/\x00b"],
)
def test_safe_join_rejects_escapes(tmp_path: Path, evil: str) -> None:
    with pytest.raises(PathSecurityError):
        safe_join(tmp_path, evil)


def test_safe_join_allows_nested_paths(tmp_path: Path) -> None:
    assert safe_join(tmp_path, "a", "b/c.mp4") == (tmp_path / "a/b/c.mp4").resolve()
    assert safe_join(tmp_path, "a/../b.txt") == (tmp_path / "b.txt").resolve()  # stays inside


def test_symlink_pointing_outside_is_rejected(tmp_path: Path) -> None:
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    (root / "link").symlink_to(outside)
    with pytest.raises(PathSecurityError):
        safe_join(root, "link/secret.txt")
    with pytest.raises(PathSecurityError):
        ensure_within(root / "link", root)


def test_to_project_relative_is_posix(tmp_path: Path) -> None:
    f = tmp_path / "media" / "raw" / "a.mp4"
    f.parent.mkdir(parents=True)
    f.touch()
    assert to_project_relative(f, tmp_path) == "media/raw/a.mp4"
    with pytest.raises(PathSecurityError):
        to_project_relative(tmp_path.parent / "x.mp4", tmp_path)


# --- subprocess ---------------------------------------------------------------


def test_run_command_does_not_use_a_shell(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    result = run_command(["echo", f"hello; touch {marker}"])
    assert "touch" in result.stdout  # printed literally, not executed
    assert not marker.exists()


def test_run_command_missing_binary_is_actionable() -> None:
    with pytest.raises(DependencyMissingError, match="is missing"):
        run_command(["definitely-not-a-real-binary-xyz"])


def test_run_command_failure_is_redacted() -> None:
    from app.core.exceptions import MediaProcessingError

    with pytest.raises(MediaProcessingError) as exc:
        run_command(["sh", "-c", "echo 'token=abcdef123456' >&2; exit 3"])
    assert "abcdef123456" not in str(exc.value.details)


def test_run_command_timeout() -> None:
    with pytest.raises(ValidationFailedError, match="timed out"):
        run_command(["sleep", "5"], timeout=0.2)


# --- redaction ---------------------------------------------------------------


def test_redact_known_and_pattern_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("META_APP_SECRET", "supersecretvalue")
    text = "key sk-ant-api03-ABCDEFGH12345 and Bearer abcdefghijkl and supersecretvalue ok"
    out = redact(text)
    assert "sk-ant-api03" not in out
    assert "abcdefghijkl" not in out
    assert "supersecretvalue" not in out
    assert "ok" in out


def test_redact_mapping() -> None:
    out = redact_mapping({"name": "a", "api_key": "x", "nested": {"client_secret": "y", "n": 1}})
    assert out["name"] == "a" and out["api_key"] != "x"
    assert out["nested"]["client_secret"] != "y" and out["nested"]["n"] == 1


def test_logging_filter_scrubs_secrets() -> None:
    rec = logging.LogRecord("t", logging.INFO, "f", 1, "token=%s", ("sk-ant-abcdefghijk",), None)
    assert RedactingFilter().filter(rec)
    assert "sk-ant-abcdefghijk" not in rec.getMessage()


# --- file validation -------------------------------------------------------------


def test_validate_file(tmp_path: Path) -> None:
    f = tmp_path / "a.mp4"
    f.write_bytes(b"12345")
    assert validate_file(f, allowed_extensions=[".mp4"]) == 5
    with pytest.raises(ValidationFailedError, match="not allowed"):
        validate_file(f, allowed_extensions=[".mov"])
    with pytest.raises(ValidationFailedError, match="size limit"):
        validate_file(f, allowed_extensions=[".mp4"], max_size_bytes=2)
    with pytest.raises(ValidationFailedError, match="regular file"):
        validate_file(tmp_path, allowed_extensions=[".mp4"])


# --- credential vault -----------------------------------------------------------


def test_vault_roundtrip_with_private_permissions(tmp_path: Path) -> None:
    vault = CredentialVault(tmp_path / "creds")
    vault.put("youtube.main", {"refresh_token": "r-token"})
    f = tmp_path / "creds" / "youtube.main.json"
    assert stat.S_IMODE(os.stat(f).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(tmp_path / "creds").st_mode) == 0o700
    assert vault.get("youtube.main") == {"refresh_token": "r-token"}
    assert vault.get("missing") is None
    assert vault.delete("youtube.main") is True


@pytest.mark.parametrize("key", ["../x", "a/b", "", "UPPER", ".hidden"])
def test_vault_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    with pytest.raises(PathSecurityError):
        CredentialVault(tmp_path).put(key, {})


def test_vault_cipher_is_pluggable(tmp_path: Path) -> None:
    class Rot13:
        name = "rot13"

        def encrypt(self, b: bytes) -> bytes:
            return bytes((c + 1) % 256 for c in b)

        def decrypt(self, b: bytes) -> bytes:
            return bytes((c - 1) % 256 for c in b)

    vault = CredentialVault(tmp_path, Rot13())
    vault.put("k", {"t": "secret"})
    assert "secret" not in (tmp_path / "k.json").read_text()
    assert vault.get("k") == {"t": "secret"}
    with pytest.raises(ValidationFailedError, match="different cipher"):
        CredentialVault(tmp_path).get("k")
