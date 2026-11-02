#!/bin/bash
# Opens the Sheet Reviewer: each study's evidence sheet against its PDF, with your verification recorded fact by fact.
#   notes-verifier/run-review.sh               open the app
#   notes-verifier/run-review.sh --self-test   check the app on generated sample files (no real paper is opened)
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$HERE/.venv/bin/python"
[ -x "$PY" ] || "$HERE/setup.sh" || exit 1
[ -f "$HERE/data/papers.json" ] || "$PY" "$HERE/build_list.py" || exit 1
cd "$HERE" && exec "$PY" "$HERE/sheet_reviewer.py" "$@"
