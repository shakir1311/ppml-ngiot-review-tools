#!/bin/bash
# Opens the Evidence Verifier: each study's evidence sheet against its notes, summary and PDF.
#   notes-verifier/run-evidence.sh               open the app
#   notes-verifier/run-evidence.sh --self-test   check the app on generated sample files (no real paper is opened)
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$HERE/.venv/bin/python"
[ -x "$PY" ] || "$HERE/setup.sh" || exit 1
[ -f "$HERE/data/papers.json" ] || "$PY" "$HERE/build_list.py" || exit 1
cd "$HERE" && exec "$PY" "$HERE/evidence_app.py" "$@"
