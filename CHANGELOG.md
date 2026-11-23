# Changelog

## 0.1.0 — Unreleased
Initial foundation: project format and schemas, SQLite + Alembic, ingest/probe/thumbnail/proxy/validation pipeline,
job tracking, publishing state machine, platform adapter contract (publishing not implemented), AI provider
abstraction with Anthropic provider, FastAPI API, CLI, Next.js dashboard, CI.

Source-agnostic media: any video ffprobe can read is imported, probed, thumbnailed and proxied, whatever the device
(phone, camera, drone, screen recording, finished edit). More video extensions are scanned by default, proxies cap the
shorter side so vertical video keeps its quality, a 2:1 video is treated as 360 only with spherical metadata or when
placed in `media/stitched/`, and the default camera applies to every source. 360 handling stays an optional workflow.
