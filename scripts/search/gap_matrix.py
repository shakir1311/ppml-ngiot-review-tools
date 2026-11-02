#!/usr/bin/env python3
"""The gap matrix: every paper checked against the conditions of the research gap (search/gapcheck/GAPCHECK-GUIDE-2026-10-03.md).

The 19 in-depth designs are judged from their categories (search/fulltext/INDEPTH-CATEGORIES-2026-10-02.json), each
traced to a sheet answer with its page: C1 similarity proved; C2 verified by a smart contract or the ledger's nodes;
C3 nobody alone reads an update; C4 proving timed on device-class hardware (`device_proving`); C5 poisoning and fake
participants both tested; C6 no updates on-chain and data-protection law discussed. The papers of the gap check are
taken from their checked sheets (search/gapcheck/sheets/, verified by check_gap_sheets.py). Papers not retrieved are
listed with their abstract-only assessment (search/gapcheck/NOT-RETRIEVED-2026-10-03.json).

Writes search/gapcheck/GAP-MATRIX-2026-10-03.csv and prints the papers that meet most conditions.
Usage: python3 scripts/search/gap_matrix.py
"""
import csv, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
G = ROOT / 'search' / 'gapcheck'
CAT = json.loads((ROOT / 'search' / 'fulltext' / 'INDEPTH-CATEGORIES-2026-10-02.json').read_text(encoding='utf-8'))
C = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6']


def indepth():
    St, dev = CAT['studies'], set(CAT.get('device_proving', []))
    for k, x in sorted(St.items()):
        m = {'C1': 'similarity' in x['proved'], 'C2': x['verifier'] in ('smart contract', 'ledger nodes'),
             'C3': x['sees_update'] == 'nobody alone', 'C4': k in dev,
             'C5': 'poisoning' in x['tested'] and 'sybil' in x['tested'],
             'C6': (not x['updates_onchain']) and bool(x['regulation'])}
        yield {'id': k, 'set': 'in-depth (Q1 journal, read in full)', 'basis': 'full text (evidence sheet)',
               **{c: 'yes' if m[c] else 'no' for c in C}, 'closes_gap': all(m[c] for c in C[:5]),
               'bound': 'yes' if 'bound' in x['proved'] else 'no'}


def gapcheck():
    for f in sorted((G / 'sheets').glob('*.json')):
        s = json.loads(f.read_text(encoding='utf-8'))
        sid = s['id']
        kind = 'outside the search (no ledger)' if sid in ('S033', 'O096') else 'gap check (read in full)'
        yield {'id': sid, 'set': kind, 'basis': 'full text (gap sheet)', **{c: s[c]['answer'] for c in C},
               'closes_gap': s['closes_gap'], 'bound': s['C1'].get('bound', '')}


def not_retrieved():
    f = G / 'NOT-RETRIEVED-2026-10-03.json'
    for r in (json.loads(f.read_text(encoding='utf-8'))['papers'] if f.exists() else []):
        yield {'id': r['id'], 'set': 'not retrieved', 'basis': 'abstract only', **{c: r.get(c, 'unknown') for c in C},
               'closes_gap': False, 'bound': r.get('bound', 'unknown')}


def main():
    rows = list(indepth()) + list(gapcheck()) + list(not_retrieved())
    out = G / 'GAP-MATRIX-2026-10-03.csv'
    with open(out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['id', 'set', 'basis', 'bound'] + C + ['closes_gap'])
        w.writeheader()
        w.writerows(rows)
    best = sorted(rows, key=lambda r: -sum(r[c] == 'yes' for c in C[:5]))
    print(f'{out.name}: {len(rows)} papers; close the gap: {[r["id"] for r in rows if r["closes_gap"]] or "none"}')
    for r in best[:8]:
        print(f"  {r['id']:6} {r['set'][:34]:34} " + ' '.join(f"{c}={r[c]}" for c in C))


if __name__ == '__main__':
    main()
