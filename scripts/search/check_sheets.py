#!/usr/bin/env python3
"""Check the full-text evidence sheets (search/fulltext/sheets/<id>.json) against the papers' extracted pages.

For every sheet: the JSON has the required fields; the decision is consistent with the conditions (INCLUDE only when
all five are true, with evidence); an included paper answers Q1-Q8; and every quotation is found on the page it cites
(text/pages/page_NNNN.txt; quotations marked "source": "table" or "image" are listed for a manual look instead).
Matching ignores case, whitespace, line-break hyphenation, ligatures and quote/dash variants.

Usage: python3 scripts/search/check_sheets.py [id ...]       (default: every sheet)
Writes search/fulltext/CHECK-SHEETS.json and prints one line per sheet.
"""
import csv, json, pathlib, re, sys, unicodedata

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
SHEETS = ROOT / 'search' / 'fulltext' / 'sheets'
COND = ('ledger', 'private_updates', 'check_or_zk', 'primary', 'evaluated')
QS = [f'Q{i}' for i in range(1, 9)]


def folder_of(sid, corpus_id):
    p = ROOT / 'corpus' / 'searchcorpus' / 'papers' / sid
    if p.exists():
        return p
    rows = {r['id']: r for r in csv.DictReader(open(ROOT / 'corpus' / '_extraction' / 'papers.csv', encoding='utf-8'))}
    return ROOT / 'corpus' / rows[corpus_id]['folder']


def norm(s):
    s = unicodedata.normalize('NFKC', s)
    s = s.replace('­', '')
    s = re.sub(r'[‘’‚′`´]', "'", s)
    s = re.sub(r'[“”„″]', '"', s)
    s = re.sub(r'[‐-―−]', '-', s)
    s = re.sub(r'-\s*\n\s*', '', s)            # line-break hyphenation
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()


def squash(s):
    return re.sub(r'[^a-z0-9]', '', norm(s))


def found(quote, page_text):
    q, t = norm(quote), norm(page_text)
    return q in t or squash(quote) in squash(page_text)


def check(path):
    s = json.loads(path.read_text(encoding='utf-8'))
    problems, manual, n_quotes = [], [], 0
    folder = folder_of(s['id'], s.get('corpus_id', ''))
    pages = folder / 'text' / 'pages'

    def ev_check(where, evs):
        nonlocal n_quotes
        for e in evs:
            n_quotes += 1
            if e.get('source') in ('table', 'image'):
                manual.append(f"{where} p{e.get('page')}: {e.get('quote', '')[:60]}")
                continue
            f = pages / f"page_{int(e['page']):04d}.txt"
            if not f.exists():
                problems.append(f'{where}: page {e["page"]} does not exist')
            elif not found(e['quote'], f.read_text(encoding='utf-8', errors='ignore')):
                problems.append(f'{where}: quote not on p{e["page"]}: "{e["quote"][:70]}"')
            if len(e['quote'].split()) > 45:
                problems.append(f'{where}: quote longer than 40 words')

    el = s['eligibility']
    conds = el.get('conditions', {})
    for c in COND:
        if c not in conds:
            problems.append(f'condition {c} missing')
            continue
        ev_check(c, conds[c].get('evidence', []))
        if conds[c].get('met') is True and not conds[c].get('evidence'):
            problems.append(f'condition {c} met without evidence')
    all_met = all(conds.get(c, {}).get('met') is True for c in COND)
    if el['decision'] == 'INCLUDE' and not all_met:
        problems.append('INCLUDE but not every condition is met')
    if el['decision'] == 'EXCLUDE' and (all_met or not el.get('code')):
        problems.append('EXCLUDE without a failing condition or code')
    if el['decision'] == 'INCLUDE':
        for q in QS:
            a = s.get('answers', {}).get(q)
            if not a:
                problems.append(f'{q} missing')
                continue
            ev_check(q, a.get('evidence', []))
            if a.get('answer', '').strip().lower() != 'not stated' and not a.get('evidence'):
                problems.append(f'{q} answered without evidence')
    return {'id': s['id'], 'decision': el['decision'], 'code': el.get('code', ''), 'quotes': n_quotes,
            'problems': problems, 'manual': manual}


def main(ids):
    files = [SHEETS / f'{i}.json' for i in ids] if ids else sorted(SHEETS.glob('*.json'))
    res = [check(f) for f in files]
    (ROOT / 'search' / 'fulltext' / 'CHECK-SHEETS.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    for r in res:
        print(f"{r['id']}: {r['decision']} {r['code']} | {r['quotes']} quotes | "
              f"{'PASS' if not r['problems'] else 'FAIL ' + str(len(r['problems']))} | manual {len(r['manual'])}")
        for p in r['problems'][:8]:
            print('   -', p)
    bad = [r for r in res if r['problems']]
    print(f'{len(res) - len(bad)}/{len(res)} sheets pass')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
