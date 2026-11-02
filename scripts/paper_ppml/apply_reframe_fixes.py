#!/usr/bin/env python3
"""Put the readers' findings on the new sheet answers (search-ppml/evidence/reframe-fix/results/<id>-<key>.json) into the
sheets, only where every value is allowed by the form (check_sheets.ALLOWED) and every quotation is found on its page
(check_sheets.found; "source": "image" quotations are listed for a manual look). The sheet before the change goes to
notes-verifier/history/<id>/SHEET-before-fix-<stamp>.json; the Sheet Reviewer's record keeps the answer unticked and notes
that a reader settled it; every decision is logged in search-ppml/evidence/reframe-fix/APPLIED.jsonl. Prints one line per
finding: applied, or refused with the kind of problem — never the paper's text.
Usage: python3 scripts/paper_ppml/apply_reframe_fixes.py [--dry-run]
"""
import datetime, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import check_sheets as CS

ROOT = pathlib.Path(__file__).resolve().parents[2]
RES = ROOT / 'search-ppml' / 'evidence' / 'reframe-fix' / 'results'
LOG = ROOT / 'search-ppml' / 'evidence' / 'reframe-fix' / 'APPLIED.jsonl'
HIST = ROOT / 'notes-verifier' / 'history'
RECORD = ROOT / 'notes-verifier' / 'data' / 'sheet-review.json'
STAMP = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
NOW = datetime.datetime.now().isoformat(timespec='seconds')


def problems(cid, key, r):
    out = []
    kind = CS.studies()[cid]['kind']
    if key not in CS.FORM[kind]:
        return [f'{key} is not part of the form']
    ans = str(r.get('answer', '')).strip()
    if not ans:
        out.append('empty answer')
    if len(ans.split()) > 80:
        out.append('answer longer than 80 words')
    vals = r.get('values') or {}
    for field, allowed in CS.ALLOWED.get(key, {}).items():
        if field not in vals:
            out.append(f'values.{field} missing'); continue
        if allowed is None:
            continue
        items = vals[field] if isinstance(vals[field], list) else [vals[field]]
        for x in items:
            if not (isinstance(x, str) and x.startswith('other:')) and x not in allowed:
                out.append(f'values.{field} has a value outside the form')
    for field in vals:
        if field not in CS.ALLOWED.get(key, {}):
            out.append(f'values.{field} is not a field of {key}')
    ev = r.get('evidence') or []
    if ans.lower().startswith('not stated'):
        if ev:
            out.append('"not stated" with evidence')
        if len(r.get('searched') or []) < 4:
            out.append('"not stated" with fewer than four terms searched')
    elif not ev:
        out.append('answer without evidence')
    pages = CS.folder_of(cid) / 'text' / 'pages'
    for e in ev:
        if not isinstance(e, dict) or not isinstance(e.get('page'), int) or not str(e.get('quote', '')).strip():
            out.append('evidence entry without page/quote'); continue
        if e.get('source') in ('table', 'image'):
            continue
        f = pages / f"page_{e['page']:04d}.txt"; ocr = pages.parent / 'pages_ocr' / f.name
        if not any(g.exists() and CS.found(e['quote'], g.read_text(encoding='utf-8', errors='ignore')) for g in (f, ocr)):
            out.append(f'quotation not found on p{e["page"]}')
        if len(e['quote'].split()) > 45 or '…' in e['quote'] or '...' in e['quote']:
            out.append('quotation too long or with an ellipsis')
    return out


def main(dry):
    record = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.exists() else {}
    n_ok = n_bad = 0
    for f in sorted(RES.glob('*.json')):
        cid, key = f.stem.split('-', 1)
        try:
            r = json.loads(f.read_text(encoding='utf-8'))
        except Exception as ex:
            print(f'{cid}-{key}: refused (not readable JSON)'); n_bad += 1; continue
        probs = problems(cid, key, r)
        manual = [e['page'] for e in (r.get('evidence') or []) if isinstance(e, dict) and e.get('source') in ('table', 'image')]
        entry = {'on': NOW, 'id': cid, 'key': key, 'settled': bool(r.get('settled')), 'problems': probs, 'manual_look_pages': manual,
                 'quotations': len(r.get('evidence') or []), 'applied': not probs and not dry}
        if probs:
            print(f"{cid}-{key}: refused ({'; '.join(sorted(set(probs)))})"); n_bad += 1
        else:
            print(f"{cid}-{key}: {'would apply' if dry else 'applied'} ({entry['quotations']} quotations"
                  f"{', image evidence on p' + ', p'.join(map(str, manual)) + ' for a manual look' if manual else ''})"); n_ok += 1
            if not dry:
                sp = CS.SHEETS / f'{cid}.json'; text = sp.read_text(encoding='utf-8'); sheet = json.loads(text)
                (HIST / cid).mkdir(parents=True, exist_ok=True)
                (HIST / cid / f'SHEET-before-fix-{STAMP}.json').write_text(text, encoding='utf-8')
                sheet['answers'][key] = {'answer': r['answer'], 'values': r.get('values') or {}, 'evidence': r.get('evidence') or [],
                                         'located_via': 'full text', 'searched': r.get('searched') or []}
                indent = re.match(r'\{\n( +)"', text)
                sp.write_text(json.dumps(sheet, indent=len(indent.group(1)) if indent else 1, ensure_ascii=False) + ('\n' if text.endswith('\n') else ''), encoding='utf-8')
                e = record.setdefault(cid, {}).setdefault(key, {})
                e.update({'verified': False, 'new_on': e.get('new_on', NOW), 'how': 'reader', 'settled_on': NOW})
                e.pop('quotes', None)
        if not dry:
            with open(LOG, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
    if not dry and n_ok:
        RECORD.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f"{n_ok} {'would be ' if dry else ''}applied, {n_bad} refused")


if __name__ == '__main__':
    main('--dry-run' in sys.argv)
