# Architecture

```
web (Next.js) ──HTTP──▶ app/api (FastAPI) ──▶ services ──▶ pipeline stages ──▶ ffmpeg/ffprobe
                                   │              │
                                   │              ├─▶ ai/ (provider abstraction)
                                   ▼              └─▶ tracking/ (JSON in project) 
                              SQLite (jobs, posts, media index)      platforms/ (adapters)
```

Principles: AI plans, deterministic code executes; originals are immutable; production is independent of publishing;
every stage is traceable (job events + sidecar JSON); human approval is the default; user data lives outside the repo.

- **Project JSON** (in the project folder) is the portable record; **SQLite** (`data/app.db`) holds operational state
  (jobs, events, post tracking). Migrations via Alembic run at startup.
- **API** is localhost-only with a Host-header allowlist. Errors use `{error:{code,message,details}}`.
- **Pipeline**: `Stage` ABC with `StageContext`/`StageResult`; the orchestrator runs stages per asset, skipping
  finished work. Stages not yet built are registered with `implemented = False` and refuse to run.
- **Platforms**: `platforms/base.py` defines the adapter contract; `registry.py` discovers adapters.
- **Deviations from the original spec tree**: `app/api/__init__.py` aggregates routers (no `api.py`);
  `app/pipeline/stages/_future.py` holds the placeholder stages instead of separate empty files; analysis output
  goes to `data/analysis/<clip>.json`; media listing routes live in `projects.py`.

## Post-first data model

- **Post** (`content_posts`): the user-facing unit: one video, caption and hashtags. The dashboard is organised around it.
- **Platform post** (`posts`, with `content_post_id`): that post's copy on one platform and variant, with the publishing
  state machine, attempts and the latest analytics.
- `comments`, `metric_snapshots` and `engagement_actions` hang off a platform post.
- API: `GET/POST /content-posts`, `GET /content-posts/{id}` (platforms, totals, per-platform metrics, capabilities,
  history, audit trail); `GET /posts/{platform_post_id}/comments`; `POST /posts/{id}/sync`; comment actions
  (`reply`, `like`, `hide`, `DELETE`) and `POST /posts/{id}/like`; `GET /analytics/overview`.
- Totals add only additive metrics (views, likes, comments, shares, saves, watch time); reach and averages are never summed.
