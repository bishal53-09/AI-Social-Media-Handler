# Security Policy

Report vulnerabilities privately via GitHub Security Advisories on this repository. Do not open public issues for them.

Design guarantees (see [docs/security.md](docs/security.md)): API binds to localhost and rejects non-local Host
headers; no shell invocation of external tools; path traversal checks on all user paths; secrets only in `.env` or the
credential vault (mode 0600) and redacted from logs; video frames are sent to an AI provider only with explicit consent.
The API has **no authentication** because it is intended for local use only; do not expose it to a network.
