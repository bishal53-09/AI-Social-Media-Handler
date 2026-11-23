# Installation

Prerequisites: git, Python 3.11+, Node.js 20+, npm, FFmpeg and ffprobe (macOS: `brew install ffmpeg`;
Debian/Ubuntu: `sudo apt install ffmpeg`).

```bash
curl -fsSL https://raw.githubusercontent.com/bishal53-09/AI-Social-Media-Handler/main/setup.sh -o setup.sh && bash setup.sh
```

The script checks prerequisites, clones (or reuses) the checkout, creates `.venv`, installs backend and frontend
dependencies, creates `.env` (mode 600) only if absent, runs migrations and validates configuration. It never runs
`git pull` or overwrites local changes. Override with `INSTALL_DIR`, `REPO_URL`, `BRANCH`.

Start: `.venv/bin/python -m app.cli serve` and `cd web && npm run dev`. Verify with `python -m app.cli doctor`.
Tested on Linux only so far; macOS is supported by design but unverified.
