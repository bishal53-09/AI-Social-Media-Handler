# Configuration

- `.env` (git-ignored; from `.env.example`): API keys, `APP_HOST`, `APP_PORT`, `DATABASE_URL`, `MEDIA_ROOT`,
  `UPDATE_CHECK` (default `true`: the API runs `git fetch` at most every 15 minutes so the dashboard can show when an
  update is available; it never installs anything).
- `make dev` reads `APP_PORT` from `.env` for the backend; `BACKEND_PORT`/`FRONTEND_PORT` override the ports (a
  non-default frontend port must also be added to `server.cors_origins` in `config/app.yaml`).
- `config/app.yaml`, `pipeline.yaml`, `ai.yaml`, `platforms.yaml`, `export-presets.yaml`: behaviour; validated at startup.
- Frontend: `web/.env.local` with `NEXT_PUBLIC_API_URL` (public; never put secrets there).

Validate: `python scripts/validate_config.py`. The dashboard Settings page shows effective, non-secret values.
