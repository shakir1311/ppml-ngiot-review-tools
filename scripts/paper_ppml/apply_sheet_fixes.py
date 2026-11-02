#!/usr/bin/env python3
"""Check and apply the readers' corrections of the evidence sheets (search-ppml/evidence/sheet-fix/results/<key>.json).

A corrected answer is applied only if
  - every tag value is allowed (or "other: …"), with the same fields as the sheet's answer;
  - every quotation is found word for word on the page it names (the check every sheet passed: check_sheets.py), is at
    most 45 words and has no ellipsis — quotations marked "source": "table" / "image" are listed for the author to look at;
  - the answer text is not empty.
Before a sheet is written, its untouched original is kept in notes-verifier/history/<key>/SHEET-original.json (as the
Sheet Reviewer does); after writing, the whole sheet is checked again (check_sheets.check) and put back if it fails.
Every applied change goes to search-ppml/evidence/sheet-fix/APPLIED.jsonl (key, question, why, before, after, time).

Usage: python3 scripts/paper_ppml/apply_sheet_fixes.py [--apply] [key ...]
       (without --apply: checks only, writes nothing)
"""
import argparse
import copy
import datetime
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sheets as cs

ROOT = cs.ROOT
SHEETS = cs.SHEETS
FIX = ROOT / 'search-ppml' / 'evidence' / 'sheet-fix'
HISTORY = ROOT / 'notes-verifier' / 'history'


def page_texts(folder, page):
    out = []
    for sub in ('pages', 'pages_ocr'):
        f = folder / 'text' / sub / f'page_{int(page):04d}.txt'
        if f.exists():
            out.append(f.read_text(encoding='utf-8', errors='ignore'))
    return out


def check_answer(q, old, new, folder):
    """Problems with a corrected answer (empty list = fine) and the quotations to look at by hand."""
    problems, manual = [], []
    if not str(new.get('answer', '')).strip():
        problems.append('empty answer')
    allowed = cs.ALLOWED.get(q, {})
    vals = new.get('values') or {}
    known = set(allowed) | {'verification_other_means', 'own_limitations'}   # fields the rules (or the sheets) use
    if not set(old.get('values') or {}) <= set(vals):
        problems.append(f"tag fields {sorted(set(old.get('values') or {}) - set(vals))} of the sheet are missing")
    if set(vals) - set(old.get('values') or {}) - known:
        problems.append(f"tag fields {sorted(set(vals) - set(old.get('values') or {}) - known)} are not in the rules")
    for field, rule in allowed.items():
        if rule is None or field not in vals:
            continue
        for x in (vals[field] if isinstance(vals[field], list) else [vals[field]]):
            if not (isinstance(x, str) and x.startswith('other:')) and x not in rule:
                problems.append(f'{field}: {x!r} is not an allowed value')
    for e in new.get('evidence') or []:
        if not isinstance(e, dict) or 'page' not in e or 'quote' not in e:
            problems.append('evidence entry without page/quote')
            continue
        quote = str(e['quote'])
        if e.get('source') in ('table', 'image'):        # as check_sheets.py: table/figure rows are looked at by hand
            manual.append(f"p{e['page']} ({e['source']}): {quote[:80]}")
            continue
        if len(quote.split()) > 45:
            problems.append(f"p{e['page']}: quotation longer than 45 words")
        if '…' in quote or '...' in quote:
            problems.append(f"p{e['page']}: ellipsis inside a quotation")
        try:
            texts = page_texts(folder, int(e['page']))
        except (TypeError, ValueError):
            problems.append(f"page {e['page']!r} is not a number")
            continue
        if not texts:
            problems.append(f"page {e['page']} does not exist")
        elif not any(cs.found(quote, t) for t in texts):
            problems.append(f"p{e['page']}: quotation not found on its page: \"{quote[:70]}\"")
    if not new.get('evidence') and not str(new.get('answer', '')).lower().startswith('not stated'):
        problems.append('answer without evidence')
    return problems, manual


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--results', default='results', help="folder of reader results under sheet-fix/ (e.g. check2/results)")
    ap.add_argument('keys', nargs='*')
    a = ap.parse_args()
    results = FIX / a.results
    keys = a.keys or sorted(p.stem for p in results.glob('*.json'))
    studies = cs.studies()
    totals = {'correct': 0, 'corrected': 0, 'unsettled': 0, 'rejected': 0, 'applied': 0}
    log = (FIX / 'APPLIED.jsonl').open('a', encoding='utf-8') if a.apply else None
    for key in keys:
        res = json.loads((results / f'{key}.json').read_text(encoding='utf-8'))
        path = SHEETS / f'{key}.json'
        text = path.read_text(encoding='utf-8')
        sheet = json.loads(text)
        folder = cs.folder_of(key)
        new_sheet, changes = copy.deepcopy(sheet), []
        for q, r in res.get('answers', {}).items():
            v = r.get('verdict')
            totals[v] = totals.get(v, 0) + 1
            if v != 'corrected':
                if v == 'unsettled':
                    print(f'  {key} {q}: unsettled — {r.get("why", "")[:150]}')
                continue
            old = sheet['answers'][q]
            new = copy.deepcopy(old)
            for f in ('answer', 'values', 'evidence', 'searched'):
                if f in r:
                    new[f] = r[f]
            new['located_via'] = 'full text'
            if new == old:                                 # applied before: nothing to do
                continue
            problems, manual = check_answer(q, old, new, folder)
            if problems:
                totals['rejected'] += 1
                print(f'  {key} {q}: NOT applied — ' + '; '.join(problems))
                continue
            for m in manual:
                print(f'  {key} {q}: look at by hand — {m}')
            new_sheet['answers'][q] = new
            changes.append((q, r.get('why', ''), old, new))
        if not changes:
            continue
        print(f"{key}: {len(changes)} answer(s) to correct: {', '.join(q for q, *_ in changes)}")
        if not a.apply:
            continue
        hist = HISTORY / key
        hist.mkdir(parents=True, exist_ok=True)
        if not (hist / 'SHEET-original.json').exists():
            (hist / 'SHEET-original.json').write_text(text, encoding='utf-8')
        stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        (hist / f'SHEET-before-fix-{stamp}.json').write_text(text, encoding='utf-8')
        indent = 2 if text.startswith('{\n  "') else 1
        path.write_text(json.dumps(new_sheet, indent=indent, ensure_ascii=False) + ('\n' if text.endswith('\n') else ''),
                        encoding='utf-8')
        check = cs.check(key, studies)
        if check['status'] != 'PASS':
            path.write_text(text, encoding='utf-8')          # put the sheet back as it was
            totals['rejected'] += len(changes)
            print(f'  {key}: sheet check FAILED after the change, sheet put back: ' + '; '.join(check['problems'][:5]))
            continue
        totals['applied'] += len(changes)
        for q, why, old, new in changes:
            log.write(json.dumps({'key': key, 'q': q, 'why': why, 'pass': a.results, 'before': old, 'after': new,
                                  'on': datetime.datetime.now().isoformat(timespec='seconds')}, ensure_ascii=False) + '\n')
    if log:
        log.close()
    print('\n' + ' · '.join(f'{k} {v}' for k, v in totals.items()) + ('' if a.apply else '  (check only: nothing written)'))


if __name__ == '__main__':
    main()
