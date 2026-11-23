# Configuration

- `.env` (git-ignored; from `.env.example`): API keys, `APP_HOST`, `APP_PORT`, `DATABASE_URL`, `MEDIA_ROOT`.
- `config/app.yaml`, `pipeline.yaml`, `ai.yaml`, `platforms.yaml`, `export-presets.yaml`: behaviour; validated at startup.
- Frontend: `web/.env.local` with `NEXT_PUBLIC_API_URL` (public; never put secrets there).

Validate: `python scripts/validate_config.py`. The dashboard Settings page shows effective, non-secret values.
