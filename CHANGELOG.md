# Changelog

## 0.1.0 — Unreleased
Initial foundation: project format and schemas, SQLite + Alembic, ingest/probe/thumbnail/proxy/validation pipeline,
job tracking, publishing state machine, platform adapter contract (publishing not implemented), AI provider
abstraction with Anthropic provider, FastAPI API, CLI, Next.js dashboard, CI.

- `make dev` starts backend and frontend together and prints the dashboard URL; Ctrl+C stops both.
- `make update` fast-forwards to the latest upstream commit, reinstalls dependencies and runs migrations.
- `GET /api/v1/system/update` and a dashboard banner / Settings card show when an update is available.
