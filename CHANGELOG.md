# Changelog

## 0.1.0 — Unreleased
Initial foundation: project format and schemas, SQLite + Alembic, ingest/probe/thumbnail/proxy/validation pipeline,
job tracking, publishing state machine, platform adapter contract (publishing not implemented), AI provider
abstraction with Anthropic provider, FastAPI API, CLI, Next.js dashboard, CI.

- `make dev` starts backend and frontend together and prints the dashboard URL; Ctrl+C stops both.
- `make update` fast-forwards to the latest upstream commit, reinstalls dependencies and runs migrations.
- `GET /api/v1/system/update` and a dashboard banner / Settings card show when an update is available.
- Source-agnostic media: any video ffprobe can read is imported, probed, thumbnailed and proxied, whatever the device
  (phone, camera, drone, screen recording, finished edit). More video extensions are scanned by default, proxies cap the
  shorter side so vertical video keeps its quality, a 2:1 video is treated as 360 only with spherical metadata or when
  placed in `media/stitched/`, and the default camera applies to every source. 360 handling stays an optional workflow.
- Docs: test entry to verify `make update` and the in-app update banner end to end.
- Add media from the UI: "Add media" on a project copies chosen files into `media/raw/<today>/` (type and size checked,
  names sanitised, never overwrites). Media can be renamed in the UI (display name only; files are never renamed).
- Posts pick their media from the project's media (names and thumbnails) instead of a typed path, and can hold several
  files; each platform variant declares how many it accepts (Instagram carousel: 10, others: 1). `media/processed/`
  and `media/ready/` are now indexed. New post/project forms no longer ask for typed paths or a camera model
  (the camera is detected from file metadata; `default_camera` stays an optional API setting). Migration `0003`.
