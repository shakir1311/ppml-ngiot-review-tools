#!/usr/bin/env python3
"""Claude's suggestions for the S-ZK records, made ready for the screening app — the author verifies every one.

The author, 12 October 2026: "please select the default for include/exclude/unsure based on your judgement. and i will verify
that". Six runs of Claude (Sonnet), each given the guide (search-ppml/evidence/szk-search/claude/GUIDE.md, prompt PROMPT.md)
and one batch of records (title, year, venue, document type, keywords and abstract from the records of 2 October; no paper),
wrote one line per record to claude/results/RESULT-<batch>.jsonl. This script checks them and writes the file the app loads.

Checks: every candidate has exactly one suggestion; every value is one the app allows; the decision follows from the answers by
the criteria (the order of GUIDE.md: not a study; the date rule for surveys; the first No; a primary study without a ledger in
its design; any Can't tell → Unsure). A decision that does not follow is listed, never changed silently.

Adjustments: claude/ADJUSTMENTS-<date>.json, Claude's own second reading of the runs' output (each with its reason and why),
applied after the checks; the runs' result files stay as written, and every adjustment is listed in the check file.

Outputs (search-ppml/evidence/szk-search/, never overwritten):
  SUGGESTIONS-S-ZK-CLAUDE-<date>.csv   what the app shows, pre-selected with a dashed border (screening_app.py --szk)
  claude/CHECK-<date>.json             the counts and every suggestion whose decision does not follow from its answers

Usage: python3 scripts/search_ppml/szk_suggestions.py <date> [--accept-listed]
       --accept-listed writes the file even when some decisions do not follow (they are listed in the check file)
"""
import collections
import csv
import json
import pathlib
import sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
SZK = ROOT / 'search-ppml' / 'evidence' / 'szk-search'
RESULTS = SZK / 'claude' / 'results'
TYPES = {'primary', 'secondary', 'neither', 'unsure'}
YES3 = {'yes', 'no', 'unsure'}
PARTS = ['poisoning', 'malicious or fake participants', 'free riding', 'verification', 'zero-knowledge proofs', 'blockchain',
         'ZK on blockchain']
PROVES = ['training', 'bounded', 'similarity', 'aggregation', 'identity', 'inference', 'other']
DECISIONS = {'INCLUDE', 'UNSURE', 'EXCLUDE'}
CODES = {'NOT-A-STUDY', 'NOT-FULL-PAPER', 'PRIVACY-INCIDENTAL', 'OFF-FOCUS', 'NO-LEARNING', 'NO-NGIOT', 'SURVEY-BEFORE-2024',
         'NO-BLOCKCHAIN', 'OTHER'}
OUTSIDE_THE_QUESTIONS = {'NOT-FULL-PAPER', 'NO-LEARNING', 'OTHER'}      # codes that no answer to the four questions gives


def follows(r, year):
    """the decisions the answers allow, by the order of GUIDE.md"""
    if r['type'] == 'neither':
        return {('EXCLUDE', 'NOT-A-STUDY')}
    if r['decision'] == 'EXCLUDE' and r['code'] in OUTSIDE_THE_QUESTIONS:
        return {('EXCLUDE', r['code'])}
    if r['type'] == 'secondary' and year and year < 2024:
        return {('EXCLUDE', 'SURVEY-BEFORE-2024')}
    for key, code in (('privacy', 'PRIVACY-INCIDENTAL'), ('focus', 'OFF-FOCUS'), ('ngiot', 'NO-NGIOT')):
        if r[key] == 'no':
            return {('EXCLUDE', code)}
    if r['type'] == 'primary' and 'blockchain' not in r['parts']:
        return {('EXCLUDE', 'NO-BLOCKCHAIN'), ('UNSURE', '')}              # Unsure when the ledger's role is unclear
    if 'unsure' in (r['type'], r['privacy'], r['focus'], r['ngiot']):
        return {('UNSURE', '')}
    return {('INCLUDE', ''), ('UNSURE', '')}                               # Unsure where the run states a doubt in its reason


def main(date, accept):
    out = SZK / f'SUGGESTIONS-S-ZK-CLAUDE-{date}.csv'
    check = SZK / 'claude' / f'CHECK-{date}.json'
    if out.exists() or check.exists():
        sys.exit('the suggestions of this date exist; never overwritten')
    cand = {int(r['n']): r for r in csv.DictReader(open(sorted(SZK.glob('SZK-RECORDS-*.csv'))[-1], encoding='utf-8'))}
    got, problems = {}, []
    for f in sorted(RESULTS.glob('RESULT-*.jsonl')):
        for i, line in enumerate(open(f, encoding='utf-8'), 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                problems.append(f'{f.name}:{i}: not JSON ({e})')
                continue
            n = int(r.get('n', 0))
            if n not in cand:
                problems.append(f'{f.name}:{i}: {n} is not a candidate')
            elif n in got:
                problems.append(f'{f.name}:{i}: {n} twice')
            else:
                got[n] = r
    missing = sorted(set(cand) - set(got))
    rows, odd = [], []
    for n in sorted(got):
        r = got[n]
        r['parts'] = [p for p in PARTS if p in (r.get('parts') or [])]
        bad = [k for k, ok in (('type', r.get('type') in TYPES), ('privacy', r.get('privacy') in YES3), ('focus', r.get('focus') in YES3),
                               ('ngiot', r.get('ngiot') in YES3), ('decision', r.get('decision') in DECISIONS),
                               ('code', (r.get('code') or '') in (CODES if r.get('decision') == 'EXCLUDE' else {''})),
                               ('parts', set(r.get('parts') or []) <= set(PARTS)),
                               ('zk_proves', set(r.get('zk_proves') or []) <= set(PROVES))) if not ok]
        if r.get('focus') == 'yes' and not r['parts'] or r.get('focus') == 'no' and r['parts']:
            bad.append('focus and parts disagree')
        if bad:
            problems.append(f'{n}: {", ".join(bad)}')
            continue
        year = int(cand[n]['year']) if cand[n]['year'].isdigit() else None
        if (r['decision'], r.get('code') or '') not in follows(r, year):
            odd.append({'n': n, 'title': cand[n]['title'], 'decision': r['decision'], 'code': r.get('code') or '',
                        'answers': {k: r[k] for k in ('type', 'privacy', 'focus', 'ngiot')}, 'parts': r['parts'],
                        'follows': sorted(f'{d} {c}'.strip() for d, c in follows(r, year)), 'reason': r.get('reason', '')})
        rows.append({'n': n, 'type': r['type'], 'privacy': r['privacy'], 'focus': r['focus'], 'focus_parts': '; '.join(r['parts']),
                     'zk_proves': '; '.join(p for p in PROVES if p in (r.get('zk_proves') or [])) if 'zero-knowledge proofs' in r['parts'] else '',
                     'ngiot': r['ngiot'], 'decision': r['decision'], 'code': r.get('code') or '',
                     'reason': ' '.join(str(r.get('reason', '')).split())})
    adjusted = []
    adj_file = SZK / 'claude' / f'ADJUSTMENTS-{date}.json'
    if adj_file.exists():
        by_n = {r['n']: r for r in rows}
        for a in json.loads(adj_file.read_text(encoding='utf-8'))['adjustments']:
            r = by_n[a['n']]
            before = {k: r[k] for k in a['set']}
            r.update(a['set'])
            if r['decision'] != 'EXCLUDE':
                r['code'] = ''
            r['reason'] = a['reason']
            assert r['decision'] in DECISIONS and (r['code'] in CODES if r['decision'] == 'EXCLUDE' else r['code'] == ''), a['n']
            adjusted.append({'n': a['n'], 'before': before, 'after': a['set'], 'why': a['why']})
    counts = {'records': len(cand), 'suggested': len(rows), 'missing': len(missing), 'adjusted': len(adjusted),
              'decisions': dict(collections.Counter(r['decision'] for r in rows)),
              'exclusion_codes': dict(collections.Counter(r['code'] for r in rows if r['decision'] == 'EXCLUDE').most_common()),
              'included_by_type': dict(collections.Counter(r['type'] for r in rows if r['decision'] == 'INCLUDE')),
              'not_following': len(odd)}
    check.write_text(json.dumps({'date': date, 'counts': counts, 'problems': problems, 'missing': missing, 'not_following': odd,
                                 'adjusted': adjusted},
                                indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(counts, ensure_ascii=False))
    if problems or missing or (odd and not accept):
        print(f'not written: {len(problems)} problems, {len(missing)} missing, {len(odd)} decisions that do not follow '
              f'(see {check.relative_to(ROOT)})')
        check.rename(check.with_name(check.stem + '-draft.json'))         # a draft check may be redone; the real one is never overwritten
        return
    with open(out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'written {out.relative_to(ROOT)} and {check.relative_to(ROOT)}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], '--accept-listed' in sys.argv)
