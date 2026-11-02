#!/bin/bash
# Double-click to open the Sheet Reviewer. The app starts in its own window; this Terminal window can be closed.
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/.cache"
nohup "$HERE/run-review.sh" "$@" >> "$HERE/.cache/review-app.log" 2>&1 &
disown
echo "Sheet Reviewer is starting… (log: notes-verifier/.cache/review-app.log)"
