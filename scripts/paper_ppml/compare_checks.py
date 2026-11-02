#!/usr/bin/env python3
"""Compare the independent checks with the review's records (5 October 2026).

1. Second screening (search-ppml/evidence/checks/screen-output-{A,B,C}.jsonl, blind, by a separate instance of the AI
   tool) of the 150 sampled exclusions (SCREENING-CHECK-SAMPLE-2026-10-05.csv): how many it would include or leave open,
   split by how the record had been excluded (default exclusion or automated focus rule). Each record it flags is listed
   for the author to adjudicate.
2. Extraction spot-check (spot-output-{1,2}.jsonl) of 6 studies: verdicts per answer (agree / minor / disagree).
Writes search-ppml/evidence/checks/CHECKS-RESULT-2026-10-05.json; prints a summary.

Usage: python3 scripts/paper_ppml/compare_checks.py
"""
import csv, json, pathlib
from collections import Counter

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
C = ROOT / 'search-ppml' / 'evidence' / 'checks'


def jl(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()] if p.exists() else []


def main():
    sample = {r['n']: r for r in csv.DictReader(open(ROOT / 'search-ppml' / 'evidence' / 'SCREENING-CHECK-SAMPLE-2026-10-05.csv', encoding='utf-8'))}
    out = {r['n']: r for k in 'ABC' for r in jl(C / f'screen-output-{k}.jsonl')}
    missing = sorted(set(sample) - set(out))
    by = Counter((sample[n]['excluded_by'], out[n]['decision']) for n in out if n in sample)
    flagged = [{'n': n, 'excluded_by': sample[n]['excluded_by'], 'decision': out[n]['decision'], 'code': out[n].get('code', ''),
                'reason': out[n].get('reason', ''), 'title': sample[n]['title']} for n in sorted(out) if out[n]['decision'] != 'EXCLUDE']
    spot = jl(C / 'spot-output-1.jsonl') + jl(C / 'spot-output-2.jsonl')
    sv = Counter(s['verdict'] for s in spot)
    per = {}
    for s in spot:
        per.setdefault(s['study'], Counter())[s['verdict']] += 1
    res = {'screening': {'sampled': len(sample), 'screened': len(out), 'missing': missing,
                         'by_exclusion_and_decision': {f'{a} | {b}': v for (a, b), v in sorted(by.items())},
                         'flagged': flagged},
           'spot_check': {'answers': len(spot), 'verdicts': dict(sv), 'per_study': {k: dict(v) for k, v in per.items()},
                          'disagree': [s for s in spot if s['verdict'] == 'disagree'], 'minor': [s for s in spot if s['verdict'] == 'minor']}}
    (C / 'CHECKS-RESULT-2026-10-05.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    print('screening:', res['screening']['by_exclusion_and_decision'], '| missing', len(missing))
    for f in flagged:
        print('  flagged', f['n'], f['excluded_by'], f['decision'], f['code'], '|', f['title'][:80])
    print('spot-check:', dict(sv), res['spot_check']['per_study'])


if __name__ == '__main__':
    main()
