# Installation

Prerequisites: git, Python 3.11+, Node.js 20+, npm, FFmpeg and ffprobe (macOS: `brew install ffmpeg`;
Debian/Ubuntu: `sudo apt install ffmpeg`).

```bash
curl -fsSL https://raw.githubusercontent.com/bishal53-09/AI-Social-Media-Handler/main/setup.sh -o setup.sh && bash setup.sh
```

The script checks prerequisites, clones (or reuses) the checkout, creates `.venv`, installs backend and frontend
dependencies, creates `.env` (mode 600) only if absent, runs migrations and validates configuration. It never runs
`git pull` or overwrites local changes. Override with `INSTALL_DIR`, `REPO_URL`, `BRANCH`.

Start both servers with `make dev` and open the URL it prints (http://localhost:3000); Ctrl+C stops both. You can
still start them separately with `.venv/bin/python -m app.cli serve` and `cd web && npm run dev`. Verify with
`python -m app.cli doctor`.

## Updating

Stop the app, run `make update`, then `make dev` again. The update fetches the remote and fast-forwards only; it
refuses when tracked files have uncommitted changes or the branch has diverged, so nothing local is ever overwritten.
It then reinstalls dependencies and runs migrations. The dashboard shows a banner when an update is available
(the API compares `HEAD` with its upstream after a `git fetch`, at most every 15 minutes; disable with
`UPDATE_CHECK=false`).
Tested on Linux only so far; macOS is supported by design but unverified.
