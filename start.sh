#!/usr/bin/env bash
# One-step launcher: installs anything missing on first run, starts the app and opens it in your browser.
# Double-click Start.command on a Mac, or run ./start.sh. Press Ctrl+C (or close the window) to stop.
set -uo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ] || [ ! -d web/node_modules ] || [ ! -f .env ]; then
  printf '\033[1m==> First start: setting everything up (this takes a few minutes, only once)\033[0m\n'
  bash setup.sh || { printf '\033[31mSetup did not finish. Fix the message above, then start this again.\033[0m\n' >&2; exit 1; }
fi
OPEN_BROWSER=1 exec bash scripts/dev.sh
