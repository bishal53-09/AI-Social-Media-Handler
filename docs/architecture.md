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
