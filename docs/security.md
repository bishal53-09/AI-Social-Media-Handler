# Security

- API binds to 127.0.0.1 by default; `serve` refuses other hosts without `--allow-non-localhost`. TrustedHost
  middleware allows loopback names only; CORS allows `http://localhost:3000`. No authentication: local use only.
- No `shell=True`; external tools run via `run_command` with argument lists and timeouts.
- User paths go through `safe_join`/`ensure_within` (no traversal or symlink escape).
- Secrets: `.env` (mode 600) or `CredentialVault` (0600, pluggable cipher; the default is **obfuscation, not
  encryption** — use an OS keyring cipher for real protection). Logs are redacted.
- Frames to AI only with consent; originals are never modified; publishing requires approval by default.
- `make dev` binds both servers to 127.0.0.1. The update check only runs `git fetch` and reads refs (no credential
  prompts, no changes to the checkout); `make update` fast-forwards only and refuses when there are local changes.
- `.gitignore` blocks `.env`, tokens, databases, logs and common media formats.
