#!/bin/bash
# Opens the Notes Verifier (the same as double-clicking "Notes Verifier.app" in this folder).
#   notes-verifier/run.sh                  open the app
#   notes-verifier/run.sh --refresh-list   rebuild the paper list from the newest version of the review, then open
#   notes-verifier/run.sh --self-test      check the app on generated sample files (no real paper is opened)
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$HERE/.venv/bin/python"
[ -x "$PY" ] || "$HERE/setup.sh" || exit 1
if [ "$1" = "--refresh-list" ] || [ ! -f "$HERE/data/papers.json" ]; then
  "$PY" "$HERE/build_list.py" || exit 1
  [ "$1" = "--refresh-list" ] && shift
fi
exec "$PY" "$HERE/app.py" "$@"
