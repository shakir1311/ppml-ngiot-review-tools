#!/usr/bin/env python3
"""Check the related-survey comparison sheets (search/surveys/sheets/<id>.json) and build the comparison table.

Checks, per sheet: the required fields and allowed marks are present; every SQ marked full or partial has evidence;
every quotation is found on the page it cites (full-text sheets: text/pages/page_NNNN.txt of the survey's folder, as
listed in search/surveys/SURVEYS.json; abstract sheets: the abstract in SURVEYS.json, page 0). Matching ignores case,
whitespace, line-break hyphenation, ligatures and quote/dash variants (as check_sheets.py).

Table: one row per survey. Abstract-based rows cannot show whether a topic has a section of its own, so their marks
are reported only as "named in abstract" or "absent".

Usage: python3 scripts/search/check_survey_sheets.py      -> search/surveys/CHECK.json, search/surveys/COMPARISON-2026-10-02.csv
"""
import csv, json, pathlib, sys
from check_sheets import found

ROOT = pathlib.Path(__file__).resolve().parents[2]
S = ROOT / 'search' / 'surveys'
MARKS = {'full', 'partial', 'absent'}
SQS = ('SQ1', 'SQ2', 'SQ3', 'SQ4')


def main():
    meta = json.load(open(S / 'SURVEYS.json'))
    folders = {x['id']: ROOT / x['folder'] for x in meta['full_text']}
    abstracts = {x['id']: x['abstract'] + ' ' + x.get('keywords', '') for x in meta['abstract_only']}
    ids = list(folders) + list(abstracts)
    res, rows = [], []
    for i in ids:
        f = S / 'sheets' / f'{i}.json'
        if not f.exists():
            res.append({'id': i, 'problems': ['sheet missing']})
            continue
        s = json.loads(f.read_text(encoding='utf-8'))
        probs, n = [], 0

        def ev(where, evs):
            nonlocal n
            for e in evs:
                n += 1
                if i in abstracts:
                    text = abstracts[i]
                else:
                    p = folders[i] / 'text' / 'pages' / f"page_{int(e['page']):04d}.txt"
                    if not p.exists():
                        probs.append(f"{where}: page {e['page']} missing")
                        continue
                    text = p.read_text(encoding='utf-8', errors='ignore')
                if not found(e['quote'], text):
                    probs.append(f"{where}: quote not found on p{e['page']}: \"{e['quote'][:60]}\"")
        for q in SQS:
            a = s.get(q, {})
            if a.get('mark') not in MARKS:
                probs.append(f'{q}: mark missing or invalid')
            if a.get('mark') in ('full', 'partial') and not a.get('evidence'):
                probs.append(f'{q}: {a.get("mark")} without evidence')
            ev(q, a.get('evidence', []))
        ev('open_issues', s.get('open_issues_evidence', []))
        if s.get('zero_knowledge') not in MARKS:
            probs.append('zero_knowledge mark missing or invalid')
        res.append({'id': i, 'basis': s.get('basis'), 'quotes': n, 'problems': probs})
        abstract_basis = i in abstracts
        show = (lambda m: 'named in abstract' if m in ('full', 'partial') else 'absent') if abstract_basis else (lambda m: m)
        rows.append({'id': i, 'basis': 'abstract' if abstract_basis else 'full text', 'title': s.get('title', ''),
                     'year': s.get('year', ''), 'venue': s.get('venue', ''), 'method': s.get('method', ''),
                     'studies': s.get('studies', ''), 'iot_edge_focus': s.get('iot_edge_focus', ''),
                     **{q: show(s[q]['mark']) for q in SQS}, 'zero_knowledge': show(s.get('zero_knowledge', 'absent')),
                     'open_issues': s.get('open_issues', '')})
    (S / 'CHECK.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    with open(S / 'COMPARISON-2026-10-02.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    bad = [r for r in res if r['problems']]
    for r in res:
        print(f"{r['id']:6} {r.get('basis', ''):10} quotes {r.get('quotes', 0):3}  {'PASS' if not r['problems'] else 'FAIL ' + str(len(r['problems']))}")
        for p in r['problems'][:6]:
            print('    -', p)
    print(f'{len(res) - len(bad)}/{len(res)} survey sheets pass')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    sys.exit(main())
