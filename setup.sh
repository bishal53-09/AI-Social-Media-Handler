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
  Darwin) OS=macos ;;
  Linux) OS=linux ;;
  *) fail "Unsupported OS $(uname -s). macOS and Linux are supported." ;;
esac
say "Detected $OS"

# --- system prerequisites: install whatever is missing, ask for a password only if needed ---
SUDO=""; [ "$(id -u)" -eq 0 ] || SUDO="sudo"
PM=""
for m in brew apt-get dnf pacman zypper; do command -v "$m" >/dev/null 2>&1 && { PM="$m"; break; }; done

# pkg_install <brew-pkg> <apt-pkg> <dnf-pkg> <pacman-pkg> <zypper-pkg>
pkg_install() {
  case "$PM" in
    brew) brew install "$1" ;;
    apt-get) $SUDO apt-get update -qq && $SUDO apt-get install -y "$2" ;;
    dnf) $SUDO dnf install -y "$3" ;;
    pacman) $SUDO pacman -S --noconfirm "$4" ;;
    zypper) $SUDO zypper install -y "$5" ;;
    *) return 1 ;;
  esac
}
ensure() { # ensure <command> <label> <pkgs...>
  local cmd="$1" label="$2"; shift 2
  command -v "$cmd" >/dev/null 2>&1 && return 0
  say "Installing $label"
  pkg_install "$@" || true
  command -v "$cmd" >/dev/null 2>&1 || { echo "  could not install $label automatically"; missing=1; }
}

missing=0
ensure git git git git git git git
ensure ffmpeg "FFmpeg" ffmpeg ffmpeg ffmpeg ffmpeg ffmpeg
ensure ffprobe "FFmpeg" ffmpeg ffmpeg ffmpeg ffmpeg ffmpeg
ensure npm "Node.js" node nodejs npm nodejs npm nodejs npm

find_python() {
  for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then echo "$c"; return; fi
  done
}
PYTHON="$(find_python)"
if [ -z "$PYTHON" ]; then
  say "Installing Python"
  pkg_install python@3.12 python3 python3 python python3 || true
  PYTHON="$(find_python)"
fi
[ -n "$PYTHON" ] || { echo "  could not install Python 3.11+ automatically"; missing=1; }
# Debian/Ubuntu ship venv separately.
if [ -n "$PYTHON" ] && ! "$PYTHON" -c 'import venv, ensurepip' >/dev/null 2>&1 && [ "$PM" = apt-get ]; then
  say "Installing Python venv support"
  $SUDO apt-get install -y python3-venv || true
fi
if command -v node >/dev/null 2>&1 && ! node -e 'process.exit(parseInt(process.versions.node) >= 20 ? 0 : 1)'; then
  echo "  Node.js is too old (20+ needed). Install a current version from https://nodejs.org/ and re-run this installer."
  missing=1
fi
[ "$missing" -eq 0 ] || fail "Some required software could not be installed automatically (see above). Install it, then re-run this installer."

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

say "Browser for connecting your accounts (one-time download)"
.venv/bin/python -m playwright install chromium
# Linux needs a few system libraries for the browser; best effort, never fatal.
[ "$OS" = linux ] && { $SUDO .venv/bin/python -m playwright install-deps chromium >/dev/null 2>&1 || echo "  (could not install browser system libraries; if the browser fails to start, re-run this installer with sudo access)"; }

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
  2. Start the app:       make dev   (backend + frontend; Ctrl+C stops both)
  3. Open http://localhost:3000
  Update later:           make update
  Create a project:       .venv/bin/python -m app.cli init-project --name "My Project"
MSG
