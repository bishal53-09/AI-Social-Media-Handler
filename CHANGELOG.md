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
- Preview before posting: videos play and photos show inside the app (media library, project media list, and the new-post
  picker). `GET /projects/{id}/media/{asset}/file` streams the file with HTTP Range support (seeking), prefers the
  proxy when one exists (`?variant=original|proxy` to force), and re-checks the path against the project folder.
  Formats a browser cannot play (and have no proxy yet) say so instead of showing a broken player.
- List pages for projects, posts, media and jobs: server-side pagination, search, filters (status, platform, project,
  type/stage/format, date range) and sorting, with the state kept in the URL. Shared building blocks live in
  `web/src/components/list-controls.tsx` and `web/src/hooks/use-list-state.ts`; list endpoints return `limit`/`offset`.
