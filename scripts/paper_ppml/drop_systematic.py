#!/usr/bin/env python3
"""Remove the `systematic` category from the surveys' evidence sheets (answer S1) — the author, 12 October 2026: "remove
systematic from the sheet reviewer and its data. as we dont care whether a survey is systematic or not."

For each survey sheet: the sheet as it was is kept in notes-verifier/history/<key>/SHEET-before-drop-systematic-<time>.json,
the value is removed from S1, and the whole sheet is checked again (check_sheets.check; put back on failure). The answer
text and every other value stay as the author verified them, so where the author's record of the Sheet Reviewer
(notes-verifier/data/sheet-review.json) holds a tick for S1 that matched the answer before, its fingerprint is
recomputed for the answer without the removed value; the tick, its time and how it was given stay.
Close the Sheet Reviewer first (it keeps the record in memory).

Usage: python3 scripts/paper_ppml/drop_systematic.py [--apply]
"""
import datetime
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sheets as cs

ROOT = cs.ROOT
HISTORY = ROOT / 'notes-verifier' / 'history'
RECORD = ROOT / 'notes-verifier' / 'data' / 'sheet-review.json'


def fingerprint(*parts):                                   # as notes-verifier/sheet_reviewer.py
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def main():
    apply = '--apply' in sys.argv
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    record = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.exists() else {}
    studies, sheets, ticks = cs.studies(), 0, 0
    for path in sorted(cs.SHEETS.glob('*.json')):
        text = path.read_text(encoding='utf-8')
        sheet = json.loads(text)
        s1 = sheet['answers'].get('S1')
        if not s1 or 'systematic' not in (s1.get('values') or {}):
            continue
        sheets += 1
        old_fp = fingerprint(s1.get('answer'), s1.get('values'))
        values = {k: v for k, v in s1['values'].items() if k != 'systematic'}
        rec = record.get(path.stem, {}).get('S1', {})
        if rec.get('verified') is True and rec.get('answer_fingerprint') == old_fp:
            ticks += 1
            if apply:
                rec['answer_fingerprint'] = fingerprint(s1.get('answer'), values)
        if not apply:
            continue
        hist = HISTORY / path.stem
        hist.mkdir(parents=True, exist_ok=True)
        (hist / f'SHEET-before-drop-systematic-{stamp}.json').write_text(text, encoding='utf-8')
        s1['values'] = values
        indent = 2 if text.startswith('{\n  "') else 1
        path.write_text(json.dumps(sheet, indent=indent, ensure_ascii=False) + ('\n' if text.endswith('\n') else ''),
                        encoding='utf-8')
        if cs.check(path.stem, studies)['status'] != 'PASS':
            path.write_text(text, encoding='utf-8')
            sys.exit(f'{path.stem}: sheet check failed; sheet put back')
    if apply:
        (HISTORY / '_review').mkdir(parents=True, exist_ok=True)
        (HISTORY / '_review' / f'sheet-review-before-drop-systematic-{stamp}.json').write_text(
            RECORD.read_text(encoding='utf-8'), encoding='utf-8')
        tmp = RECORD.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding='utf-8')
        tmp.replace(RECORD)
    print(f"surveys with the value: {sheets}; verified S1 ticks kept valid: {ticks}"
          + ('' if apply else '  (check only: nothing written)'))


if __name__ == '__main__':
    main()
