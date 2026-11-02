#!/bin/bash
# Double-click to open the Notes Verifier. The app starts in its own window; this Terminal window can be closed.
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/.cache"
nohup "$HERE/run.sh" "$@" >> "$HERE/.cache/app.log" 2>&1 &
disown
echo "Notes Verifier is starting… (log: notes-verifier/.cache/app.log)"
