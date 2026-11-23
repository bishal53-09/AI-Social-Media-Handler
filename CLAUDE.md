# CLAUDE.md

Guidance for AI coding assistants working in this repo.

- Principles: AI plans, deterministic code executes; originals immutable; publishing independent of production;
  approval required by default; user data outside the repo.
- Layout: `app/` backend (api, services, pipeline/stages, ai, tracking, database), `platforms/` adapters, `web/` Next.js.
- Commands: `make check`, `make test`, `python -m app.cli doctor`. Backend env: `.venv`.
- Never run external tools through a shell; use `app.core.security.run_command`. Validate paths with `safe_join`.
- Unimplemented stages (`app/pipeline/stages/_future.py`) must keep `implemented = False`; do not fake output.
- Docs must distinguish implemented from planned. Never commit secrets, media or `project.json` of real projects.
- Never force-push. Schema changes need an Alembic migration plus tests.
