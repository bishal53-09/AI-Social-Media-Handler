# AI Social Media Handler

A **local-first** application for organising video from any source (phone, camera, drone, screen recording or a
finished edit), preparing it for editing, and (eventually) publishing it to social platforms. AI plans; deterministic software executes. Your footage never leaves your
machine unless you explicitly allow it.

> **Status: early foundation (v0.1.0).** Media ingest, probing, thumbnails, proxies, project tracking, the API, the
> dashboard and the AI/platform abstractions are implemented and tested. Colour grading, 360° reframing, editing,
> subtitles, rendering and **real publishing are not implemented yet**. See [Roadmap](docs/roadmap.md).

## What works today

- Multiple independent projects stored **outside** the repository, with JSON metadata validated against schemas.
- Any video ffprobe can read (MP4, MOV, MKV, WebM, AVI, MTS and more) works: landscape, vertical or square.
  Put it in `media/raw/` (date folders such as `media/raw/2026-11-23/` are optional); originals are never modified.
- Optional 360 workflow: stitched 360 exports go in `media/stitched/`; `.osv`/`.insv` camera originals are recognised
  but must be stitched in the camera vendor's software first. 360 reframing is not implemented yet.
- Pipeline stages: ingest (SHA-256), probe (ffprobe, with 360 detection from spherical metadata), thumbnails, proxies
  (with progress and cancellation), validation. Re-running skips finished work.
- Persistent jobs with event trace (SQLite), restart recovery of interrupted jobs.
- Publishing state machine with approval gate, idempotency keys and an `unknown` state that requires reconciliation
  (no blind retries). Platform adapters validate media against platform limits but **cannot publish yet**.
- AI provider abstraction with an Anthropic provider (structured, validated plans); frames are sent only with consent.
- Post-first management: a post with the platforms it is shared to, per-platform analytics, comment list and interactions
  (reply, like, hide, delete) through the adapter contract. Storage, API and UI are built and tested with a fake platform;
  **no real platform integration exists yet**, so real posts show "not implemented" instead of data.
- FastAPI backend, CLI, and a Next.js dashboard (dark/light) that shows real data and honest "not implemented" states.

## Requirements

Python 3.11+, Node.js 20+, FFmpeg + ffprobe, git. macOS and Linux.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/bishal53-09/AI-Social-Media-Handler/main/setup.sh -o setup.sh && bash setup.sh
```

`setup.sh` is safe to re-run; it never overwrites `.env` or local changes. Overrides: `INSTALL_DIR`, `REPO_URL`, `BRANCH`.

## Run

```bash
# backend (http://127.0.0.1:8000, docs at /docs)
.venv/bin/python -m app.cli serve
# frontend (http://localhost:3000)
cd web && npm run dev
```

## Create a project

```bash
.venv/bin/python -m app.cli init-project --name "Alps Trip" --path ~/Content/alps
# copy videos from any device into ~/Content/alps/media/raw/ , then:
.venv/bin/python -m app.cli scan ~/Content/alps
.venv/bin/python -m app.cli process ~/Content/alps
.venv/bin/python -m app.cli inventory ~/Content/alps
```

Other commands: `doctor`, `version`, `analyze`, `serve`. Run `python -m app.cli --help`.

## Configuration

Secrets live in `.env` (never committed); behaviour lives in `config/*.yaml`. See [configuration](docs/configuration.md).
Publishing requires human approval by default.

## Development

```bash
make check      # ruff, mypy, pytest, eslint, tsc
make test
```

Docs: [architecture](docs/architecture.md) · [installation](docs/installation.md) · [project format](docs/project-format.md) ·
[pipeline](docs/pipeline.md) · [AI workflow](docs/ai-workflow.md) · [platforms](docs/platform-integrations.md) ·
[security](docs/security.md) · [troubleshooting](docs/troubleshooting.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). MIT licensed.
