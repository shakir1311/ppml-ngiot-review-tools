#!/usr/bin/env bash
# Create the local Python environment used by the extraction scripts.
#
# --copies is deliberate: these folders live on an external volume whose
# filesystem does not preserve the symlinks a normal venv relies on, so a
# symlinked venv loses its interpreter the moment the volume is remounted.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY=""
for candidate in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.12 \
                 /usr/local/bin/python3 "$(command -v python3 || true)"; do
  [[ -x "$candidate" ]] && { PY="$candidate"; break; }
done
[[ -n "$PY" ]] || { echo "No python3 found." >&2; exit 1; }

echo "Interpreter: $PY"
rm -rf "$SCRIPT_DIR/.venv"
"$PY" -m venv --copies "$SCRIPT_DIR/.venv"
"$SCRIPT_DIR/.venv/bin/pip" install --quiet --upgrade pip
# pymupdf            the reading text of every page, page renders, figures, tables
# pymupdf4llm        text/full.md; it brings onnxruntime, which only markdown_pdf.py ever loads, in its own process
# pyobjc (Quartz, Vision)   Apple PDFKit as a second reader of every page; Apple Vision for OCR
# pdfminer.six       a reading of every page by its own analysis of the layout (verify_ocr.py judges it with the others)
"$SCRIPT_DIR/.venv/bin/pip" install --quiet pymupdf pymupdf4llm pyobjc-framework-Quartz pyobjc-framework-Vision pdfminer.six
ORT_DISABLE_TELEMETRY=1 "$SCRIPT_DIR/.venv/bin/python" -c "import pymupdf, Quartz, Vision; print('pymupdf', pymupdf.__version__, '| PDFKit', hasattr(Quartz, 'PDFDocument'))"

echo "Environment ready: $SCRIPT_DIR/.venv"
command -v pdftotext >/dev/null \
  || echo "NOTE: poppler not found - pdftotext is one of the readers every page is checked against. Install with: brew install poppler"
command -v tesseract >/dev/null \
  || echo "NOTE: tesseract not found - the second OCR engine of ocr_scanned.py and verify_ocr.py. Install with: brew install tesseract"
