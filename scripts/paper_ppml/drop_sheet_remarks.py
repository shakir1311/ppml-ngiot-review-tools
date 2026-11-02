#!/usr/bin/env python3
"""Remove the "remarks" field — the log of how a sheet was built and corrected — from the evidence sheets
(the author, 12 October 2026: these sections are not needed in the sheets). Nothing reads the field: the paper's build,
check_sheets.py and the apps use the answers only. The history stays in the records: the sheet as it was is kept in
notes-verifier/history/<key>/SHEET-before-drop-remarks-<time>.json, beside SHEET-original.json, and the corrections in
search-ppml/evidence/sheet-fix/APPLIED.jsonl and the Docs report.

Usage: python3 scripts/paper_ppml/drop_sheet_remarks.py [--apply]   (without --apply: counts only)
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sheets as cs

HISTORY = cs.ROOT / 'notes-verifier' / 'history'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    studies, changed = cs.studies(), 0
    for path in sorted(cs.SHEETS.glob('*.json')):
        text = path.read_text(encoding='utf-8')
        sheet = json.loads(text)
        if 'remarks' not in sheet:
            continue
        changed += 1
        if not a.apply:
            continue
        hist = HISTORY / path.stem
        hist.mkdir(parents=True, exist_ok=True)
        (hist / f'SHEET-before-drop-remarks-{stamp}.json').write_text(text, encoding='utf-8')
        del sheet['remarks']
        indent = 2 if text.startswith('{\n  "') else 1
        path.write_text(json.dumps(sheet, indent=indent, ensure_ascii=False) + ('\n' if text.endswith('\n') else ''),
                        encoding='utf-8')
        if cs.check(path.stem, studies)['status'] != 'PASS':
            path.write_text(text, encoding='utf-8')
            sys.exit(f'{path.stem}: sheet check failed after the change; sheet put back')
    print(f"sheets with remarks: {changed}" + (' — removed; copies kept in notes-verifier/history/' if a.apply
                                               else '  (counts only: nothing written)'))


if __name__ == '__main__':
    main()
