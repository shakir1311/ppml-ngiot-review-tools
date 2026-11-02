#!/bin/bash
# Double-click to open the Evidence Verifier. The app starts in its own window; this Terminal window can be closed.
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/.cache"
nohup "$HERE/run-evidence.sh" "$@" >> "$HERE/.cache/evidence-app.log" 2>&1 &
disown
echo "Evidence Verifier is starting… (log: notes-verifier/.cache/evidence-app.log)"
