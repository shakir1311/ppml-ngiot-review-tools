#!/usr/bin/env bash
# The mechanical half of the extraction, for the whole corpus or for another manifest of the same form:
#   1. prepare_corpus.py    one folder per paper, manifest with stable IDs (the corpus only; skipped with --manifest)
#   2. extract_corpus.py    runs extract_paper.py on every paper, each in a process of its own:
#                           text in reading order, the other engines' readings, page renders, figures, tables
#   3. ocr_scanned.py       OCR for any page without a text layer
#   4. verify_ocr.py        every page against local OCR of the rendered page (Apple Vision; Tesseract as a second engine):
#                           visible text missing from the reading text, text that is not visible, page images under a
#                           stamp (OCR then stands in), reading order where the engines could not confirm it
#   4b. sections.py         the verified full text broken down into its sections (outline, or type and numbering), lossless
#   5. check_extraction.py  audit: every page is extracted again and compared, the OCR verification and sections included;
#                           printable report in Docs/
#
#   ./scripts/run_extraction.sh [--force | --text-only] [--jobs N] [--dpi N] [--manifest PATH] [--no-verify]
#
# --force      re-extracts papers that are already extracted (a run from scratch)
# --text-only  rewrites only the text of papers that are already extracted
# --manifest   runs steps 2-5 on another manifest of the corpus form (e.g. corpus/ppmlcorpus/check-szk/MANIFEST-S-ZK.json)
# --no-verify  leaves out step 4 (it reads every page by OCR and takes a few seconds a page)
# The reading half (notes) is described in scripts/NOTES-PROTOCOL.md.

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/.venv/bin/python"
JOBS=6
DPI=150
MODE=""
MANIFEST=""
VERIFY=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)     MODE="--force"; shift ;;
    --text-only) MODE="--text-only"; shift ;;
    --jobs)      JOBS="$2"; shift 2 ;;
    --dpi)       DPI="$2"; shift 2 ;;
    --manifest)  MANIFEST="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"; shift 2 ;;
    --no-verify) VERIFY=0; shift ;;
    -h|--help)   sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ -x "$PY" ]] || { echo "Python environment missing. Run: $SCRIPT_DIR/setup_env.sh" >&2; exit 1; }
export ORT_DISABLE_TELEMETRY=1
cd "$SCRIPT_DIR" || exit 1
MAN=()
[[ -n "$MANIFEST" ]] && MAN=(--manifest "$MANIFEST")

if [[ -z "$MANIFEST" ]]; then
  echo "== 1. prepare"
  "$PY" prepare_corpus.py 2>&1 | tail -3
fi

echo "== 2. extract  (jobs $JOBS, dpi $DPI ${MODE:-papers not yet extracted})"
"$PY" extract_corpus.py "${MAN[@]}" --jobs "$JOBS" --dpi "$DPI" $MODE 2>&1 | tail -4

echo "== 3. OCR pages without a text layer"
if [[ -n "$MANIFEST" ]]; then
  "$PY" ocr_scanned.py --manifest --manifest-file "$MANIFEST" 2>&1 | grep -v "^  page"
else
  "$PY" ocr_scanned.py --manifest 2>&1 | grep -v "^  page"
fi

if [[ "$VERIFY" == 1 ]]; then
  echo "== 4. verify every page against local OCR (Apple Vision; Tesseract where installed)"
  "$PY" verify_ocr.py "${MAN[@]}" --jobs 4 --tesseract --apply 2>&1 | tail -3
fi

echo "== 4b. break the verified full text into sections"
"$PY" sections.py "${MAN[@]}" 2>&1 | tail -2

echo "== 5. audit"
if [[ -n "$MANIFEST" ]]; then
  "$PY" check_extraction.py "${MAN[@]}" --json "$(dirname "$MANIFEST")/extraction-audit.json" \
        --report "Docs/EXTRACTION-AUDIT-$(basename "$(dirname "$MANIFEST")" | tr '[:lower:]' '[:upper:]')-$(date +%Y-%m-%d).html"
else
  "$PY" check_extraction.py --report "Docs/EXTRACTION-AUDIT-$(date +%Y-%m-%d).html"
fi
