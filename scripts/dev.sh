#!/usr/bin/env bash
# Start the FastAPI backend and the Next.js frontend together (localhost only).
# Ctrl+C stops both. Used by `make dev`.
#
# Overrides: BACKEND_PORT (default: APP_PORT from .env, else 8000), FRONTEND_PORT (3000),
#            OPEN_BROWSER=1 to open the dashboard automatically once it is ready.
# Works with the bash 3.2 that ships with macOS.
set -uo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PY:-$ROOT/.venv/bin/python}"
HOST=127.0.0.1

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[ -x "$PY" ] || fail "Python environment not found at $PY. Run 'make install' (or bash setup.sh) first."
[ -d web/node_modules ] || fail "Frontend dependencies missing. Run 'make install' (or: cd web && npm ci)."
command -v npm >/dev/null 2>&1 || fail "npm is not on PATH."
command -v curl >/dev/null 2>&1 || fail "curl is required to wait for the servers to start."

env_port=""
[ -f .env ] && env_port="$(sed -n 's/^[[:space:]]*APP_PORT[[:space:]]*=[[:space:]]*\([0-9][0-9]*\).*/\1/p' .env | tail -n 1)"
BACKEND_PORT="${BACKEND_PORT:-${env_port:-8000}}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_URL="http://$HOST:$BACKEND_PORT"
FRONTEND_URL="http://localhost:$FRONTEND_PORT"

if [ "$FRONTEND_PORT" != 3000 ]; then
  echo "Note: add http://localhost:$FRONTEND_PORT to server.cors_origins in config/app.yaml, or the dashboard cannot call the API."
fi

prefix() { while IFS= read -r line || [ -n "$line" ]; do printf '%s %s\n' "$1" "$line"; done; }
port_busy() { curl -s -o /dev/null --max-time 1 "http://$HOST:$1/" ; }
port_busy "$BACKEND_PORT" && fail "Port $BACKEND_PORT is already in use. Stop the other process or set BACKEND_PORT."
port_busy "$FRONTEND_PORT" && fail "Port $FRONTEND_PORT is already in use. Stop the other process or set FRONTEND_PORT."

# Job control gives each server its own process group, so stopping it also stops
# the children it spawns (npm -> next, uvicorn workers).
set -m
BACKEND_PID=""
FRONTEND_PID=""
STOPPING=0

stop_all() {
  [ "$STOPPING" -eq 1 ] && return
  STOPPING=1
  echo
  bold "Stopping backend and frontend…"
  exec 2>/dev/null  # hide the shell's "Terminated" job notices
  for pid in $FRONTEND_PID $BACKEND_PID; do
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
  done
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    alive=0
    for pid in $FRONTEND_PID $BACKEND_PID; do kill -0 "$pid" 2>/dev/null && alive=1; done
    [ "$alive" -eq 0 ] && break
    sleep 0.5
  done
  for pid in $FRONTEND_PID $BACKEND_PID; do
    kill -KILL -- "-$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  bold "Stopped."
}
trap 'stop_all; exit 0' INT
trap 'stop_all; exit 143' TERM
trap 'stop_all' EXIT

bold "Starting backend on $BACKEND_URL"
( PYTHONUNBUFFERED=1 "$PY" -m app.cli serve --host "$HOST" --port "$BACKEND_PORT" 2>&1 </dev/null | prefix "[api]" ) &
BACKEND_PID=$!

bold "Starting frontend on $FRONTEND_URL"
(
  cd web
  NEXT_PUBLIC_API_URL="$BACKEND_URL" npx --no-install next dev --hostname "$HOST" --port "$FRONTEND_PORT" \
    2>&1 </dev/null | prefix "[web]"
) &
FRONTEND_PID=$!

wait_for() { # url, seconds
  local i=0
  while [ "$i" -lt "$2" ]; do
    curl -s -o /dev/null --max-time 2 "$1" && return 0
    kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null || return 1
    sleep 1
    i=$((i + 1))
  done
  return 1
}

if wait_for "$BACKEND_URL/api/v1/health" 60 && wait_for "http://$HOST:$FRONTEND_PORT/" 120; then
  cat <<MSG

$(printf '\033[1;32m')  AI Social Media Handler is running.$(printf '\033[0m')

  Open the dashboard:  $(printf '\033[1;36m')$FRONTEND_URL$(printf '\033[0m')
  API:                 $BACKEND_URL  (docs: $BACKEND_URL/docs)

  Press Ctrl+C to stop both.

MSG
  if [ "${OPEN_BROWSER:-0}" = "1" ]; then
    if command -v open >/dev/null 2>&1; then open "$FRONTEND_URL"
    elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$FRONTEND_URL" >/dev/null 2>&1
    fi
  fi
else
  printf '\033[33mOne of the servers did not start. See the [api] / [web] output above.\033[0m\n' >&2
fi

# Exit (and stop the other one) as soon as either server exits.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
printf '\033[33mA server exited; shutting down the other one.\033[0m\n' >&2
exit 1
