#!/usr/bin/env bash
# Update this checkout to the latest commit of its upstream branch, then refresh
# dependencies and the database schema. Used by `make update`.
#
# Non-destructive: refuses to run with uncommitted changes to tracked files,
# only fast-forwards (never merges, rebases or resets), and never touches .env,
# data/ or your projects. Stop `make dev` before running it, then start it again.
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "This folder is not a git checkout; re-install with setup.sh."
branch="$(git symbolic-ref --quiet --short HEAD)" || fail "HEAD is detached. Switch to a branch (e.g. 'git switch main') first."
upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)" \
  || fail "Branch '$branch' has no upstream. Set one with: git branch --set-upstream-to=origin/$branch"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  git status --short --untracked-files=no
  fail "You have uncommitted changes (listed above). Commit or stash them, then run 'make update' again."
fi

say "Fetching $upstream"
git fetch --quiet --no-tags

read -r ahead behind < <(git rev-list --left-right --count "HEAD...@{upstream}")
if [ "$behind" -eq 0 ]; then
  say "Already up to date ($(git rev-parse --short HEAD) on $branch)."
  [ "$ahead" -eq 0 ] || echo "  (your branch has $ahead local commit(s) not on $upstream)"
  [ "${FORCE_DEPS:-0}" = "1" ] || exit 0
else
  [ "$ahead" -eq 0 ] || fail "Your branch has $ahead local commit(s) and $upstream has $behind new one(s). Fast-forward is not possible; merge or rebase yourself."
  old="$(git rev-parse --short HEAD)"
  say "Updating $branch: $behind new commit(s)"
  git log --oneline --no-decorate "HEAD..@{upstream}" | sed 's/^/  /'
  git merge --ff-only --quiet "@{upstream}"
  echo "  $old -> $(git rev-parse --short HEAD)"
fi

say "Python dependencies"
[ -x "$PY" ] || fail "Python environment not found at $PY. Run 'make install' first."
"$PY" -m pip install --quiet -e ".[dev]"

say "Frontend dependencies"
(cd web && if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi)

say "Database migrations"
"$PY" -c "from app.core.config import get_settings; from app.database.migrate import upgrade_database; upgrade_database(get_settings().resolved_database_url)"
"$PY" scripts/validate_config.py

cat <<MSG

Update complete. If the app is running, stop it (Ctrl+C) and start it again with: make dev
Check .env.example for new settings you may want to copy into .env.
MSG
