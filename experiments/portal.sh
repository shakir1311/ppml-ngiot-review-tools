#!/bin/bash
# ONE command: start the experiments portal (if not already up), pinned to 127.0.0.1:8090 on this Mac, and open it.
# It does not start any experiment; runs are started from the page with the parameters you choose.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${EXPERIMENTS_PORTAL_PORT:-8090}"; URL="http://127.0.0.1:${PORT}/"
if ! curl -s -m 2 "$URL" >/dev/null 2>&1; then
  mkdir -p portal
  PY="${PORTAL_PYTHON:-}"
  if [ -z "$PY" ]; then
    for c in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.12 python3; do
      if command -v "$c" >/dev/null 2>&1; then PY="$(command -v "$c")"; break; fi
    done
  fi
  nohup "$PY" -u portal/portal.py >> portal/portal.log 2>&1 &
  echo $! > portal/portal.pid
  for i in $(seq 1 20); do curl -s -m 2 "$URL" >/dev/null 2>&1 && break; sleep 0.5; done
fi
echo "portal: $URL"
open "$URL" 2>/dev/null || true
