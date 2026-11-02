#!/usr/bin/env bash
# Creates the Notes Verifier's own Python environment in notes-verifier/.venv (run once; run again to rebuild it).
# --copies: this folder is on an external volume whose filesystem does not keep the symlinks a normal venv relies on.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=""
for candidate in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.12 "$(command -v python3 || true)"; do
  [[ -x "$candidate" ]] && { PY="$candidate"; break; }
done
[[ -n "$PY" ]] || { echo "No python3 found." >&2; exit 1; }
rm -rf "$HERE/.venv"
"$PY" -m venv --copies "$HERE/.venv"
"$HERE/.venv/bin/pip" install --quiet --upgrade pip
# PySide6-Essentials: the Qt window, lists and text editor.  pymupdf: draws the PDF pages and writes the highlights.
"$HERE/.venv/bin/pip" install --quiet PySide6-Essentials pymupdf
"$HERE/.venv/bin/python" -c "import PySide6, pymupdf; print('Notes Verifier environment ready: PySide6', PySide6.__version__, '| PyMuPDF', pymupdf.__version__)"
