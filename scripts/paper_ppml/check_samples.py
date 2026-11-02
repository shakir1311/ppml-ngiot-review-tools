#!/usr/bin/env python3
"""Two random samples for the author's own checks, drawn with a fixed seed so that they can be drawn again.

1. SCREENING-CHECK-SAMPLE: 100 records excluded at screening by a default (not overridden) and 50 set aside by the
   automated focus rule, for the author to re-screen blind (decide include/exclude without the pre-fill); the share the
   author would include estimates what the defaults and the rule may have lost.
2. SPOT-CHECK-SAMPLE: every answer, with its page and quotation, of 6 included studies (4 primary, 2 secondary), for the
   author to verify against the PDFs (column author_agrees: yes / no, with a note).

Outputs: search-ppml/evidence/SCREENING-CHECK-SAMPLE-2026-10-05.csv, SPOT-CHECK-SAMPLE-2026-10-05.csv
Usage: python3 scripts/paper_ppml/check_samples.py
"""
import csv, json, pathlib, random

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
SEED = 20261005


def main():
    rnd = random.Random(SEED)
    R = {r['n']: r for r in csv.DictReader(open(P / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8'))}
    D = {d['n']: d for d in csv.DictReader(open(P / 'AUTHOR-DECISIONS-2026-10-04.csv', encoding='utf-8'))}
    default = sorted(n for n, r in R.items() if not r['auto_excluded'] and not D.get(n, {}).get('decision'))
    rule = sorted(n for n, r in R.items() if r['auto_excluded'].startswith('outside the PhD focus'))
    sample = [('default exclusion', n) for n in rnd.sample(default, 100)] + [('automated focus rule', n) for n in rnd.sample(rule, 50)]
    rnd.shuffle(sample)
    with open(P / 'evidence' / 'SCREENING-CHECK-SAMPLE-2026-10-05.csv', 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['n', 'excluded_by', 'title', 'year', 'abstract', 'author_decision', 'note'])
        for why, n in sample:
            r = R[n]
            w.writerow([n, why, r['title'], r['year'], r['abstract'], '', ''])
    fin = list(csv.DictReader(open(P / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')))
    prim = sorted(r['corpus_id'] for r in fin if r['kind'] == 'primary')
    sec = sorted(r['corpus_id'] for r in fin if r['kind'] == 'secondary')
    picks = rnd.sample(prim, 4) + rnd.sample(sec, 2)
    with open(P / 'evidence' / 'SPOT-CHECK-SAMPLE-2026-10-05.csv', 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['study', 'item', 'answer', 'pages', 'quotation', 'author_agrees', 'note'])
        for cid in picks:
            s = json.loads((P / 'evidence' / 'sheets' / f'{cid}.json').read_text(encoding='utf-8'))
            for k, a in s['answers'].items():
                ev = a.get('evidence', [])
                w.writerow([cid, k, a.get('answer', ''), ', '.join(str(e.get('page')) for e in ev[:3]),
                            ' | '.join(e.get('quote', '') for e in ev[:2]), '', ''])
    print('screening check:', len(sample), 'records | spot check:', picks)


if __name__ == '__main__':
    main()
