#!/usr/bin/env bash
# AI Social Media Handler installer. Safe to re-run: never overwrites .env or local changes.
# Overrides: INSTALL_DIR, REPO_URL, BRANCH
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/bishal53-09/AI-Social-Media-Handler.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/AI-Social-Media-Handler}"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

case "$(uname -s)" in
  Darwin) OS=macos; HINT_FFMPEG="brew install ffmpeg"; HINT_PY="brew install python@3.12"; HINT_NODE="brew install node" ;;
  Linux) OS=linux; HINT_FFMPEG="sudo apt install ffmpeg (or your distro's package)"; HINT_PY="sudo apt install python3.11 python3.11-venv"; HINT_NODE="https://nodejs.org/ or nvm" ;;
  *) fail "Unsupported OS $(uname -s). macOS and Linux are supported." ;;
esac
say "Detected $OS"

missing=0
need() { command -v "$1" >/dev/null 2>&1 || { echo "  missing: $1 — $2"; missing=1; }; }
need git "install git"
need ffmpeg "$HINT_FFMPEG"
need ffprobe "$HINT_FFMPEG"
need npm "$HINT_NODE"

PYTHON=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then PYTHON="$c"; break; fi
done
[ -n "$PYTHON" ] || { echo "  missing: Python 3.11+ — $HINT_PY"; missing=1; }
if command -v node >/dev/null 2>&1; then
  node -e 'process.exit(parseInt(process.versions.node) >= 20 ? 0 : 1)' || { echo "  Node.js 20+ required — $HINT_NODE"; missing=1; }
else
  echo "  missing: node — $HINT_NODE"; missing=1
fi
[ "$missing" -eq 0 ] || fail "Install the missing prerequisites above and re-run."

# Use the current checkout if run from inside one, otherwise clone.
if [ -f "./pyproject.toml" ] && [ -d "./app" ] && [ -d "./web" ]; then
  INSTALL_DIR="$(pwd)"
  say "Using existing checkout at $INSTALL_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
  say "Existing checkout found at $INSTALL_DIR (left untouched; run 'git pull' yourself to update)"
else
  [ ! -e "$INSTALL_DIR" ] || [ -z "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ] || fail "$INSTALL_DIR exists and is not an empty git checkout."
  say "Cloning $REPO_URL ($BRANCH) into $INSTALL_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

say "Python environment"
[ -d .venv ] || "$PYTHON" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -e ".[dev]"

say "Frontend dependencies"
(cd web && if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi)

say "Runtime folders and configuration"
mkdir -p data logs projects
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "  created .env (mode 600) — add your API keys there"
else
  echo "  .env already exists, not modified"
fi
[ -f web/.env.local ] || cp web/.env.example web/.env.local

say "Initialising database and validating configuration"
.venv/bin/python -c "from app.core.config import get_settings; from app.database.migrate import upgrade_database; upgrade_database(get_settings().resolved_database_url)"
.venv/bin/python scripts/validate_config.py
.venv/bin/python -m app.cli doctor || echo "  (doctor reported problems above; the app can still start)"

cat <<MSG

Done. Next steps:
  cd $INSTALL_DIR
  1. Edit .env and add ANTHROPIC_API_KEY (optional until you use AI features)
  2. Start the backend:   .venv/bin/python -m app.cli serve
  3. Start the frontend:  cd web && npm run dev
  4. Open http://localhost:3000
  Create a project:       .venv/bin/python -m app.cli init-project --name "My Project"
MSG
