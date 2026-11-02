#!/usr/bin/env python3
"""Build the record ledger: one row per unique record, from identification to its current status, with the reason
recorded at each stage. This is the audit trail behind the PRISMA flow.

Inputs (all under search/): MERGED-RECORDS-<date>.csv (unique records, sources, the automated IEEE rule),
SCREENING-TA-<date>.csv (first screening, approved criteria), SCREENING-A-<date>.csv (second screening, scope A).
Writes search/RECORD-LEDGER-<date>.csv and prints the counts per status.

Status at this point (full-text decisions are added later):
  auto-excluded           found only by IEEE Xplore; title, abstract and keywords satisfy none of the strings
  excluded R1 (<code>)    excluded in the first screening and not screened again
  excluded R2 (<code>)    excluded in the second screening (scope A)
  survey (related work)   included as a survey in the second screening
  scope A, primary        included or unsure in the second screening: in the map; in-depth if the in-depth rule holds

Usage: python3 scripts/search/build_ledger.py <date> [--merged-tag TAG]
  With --merged-tag, the unique records are read from MERGED-RECORDS-<TAG>.csv and the ledger is written as
  RECORD-LEDGER-<TAG>.csv (earlier ledgers stay unchanged). Second-screening decisions are read from
  SCREENING-A-<date>.csv and, if present, SCREENING-X5-<date>.csv (records first screened after the X5 search, which
  were screened against scope A only).
"""
import collections, csv, json, pathlib, sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
S = ROOT / 'search'


def main(date, tag=None):
    tag = tag or date
    merged = {r['n']: r for r in csv.DictReader(open(S / f'MERGED-RECORDS-{tag}.csv', encoding='utf-8'))}
    r1 = {r['n']: r for r in csv.DictReader(open(S / f'SCREENING-TA-{date}.csv', encoding='utf-8'))}
    r2 = {r['n']: r for r in csv.DictReader(open(S / f'SCREENING-A-{date}.csv', encoding='utf-8'))}
    x5 = S / f'SCREENING-X5-{date}.csv'
    if x5.exists():
        r2.update({r['n']: r for r in csv.DictReader(open(x5, encoding='utf-8'))})
    cols = ['n', 'title', 'year', 'venue', 'type', 'doi', 'sources', 'hits', 'corpus_id', 'auto_excluded',
            'r1_decision', 'r1_code', 'r1_reason', 'r2_decision', 'r2_code', 'r2_iot', 'r2_check', 'r2_reason', 'status',
            'indepth_candidate', 'sjr2025', 'sjr2024', 'ft_decision', 'ft_code', 'ft_reason', 'ft_sheet']
    # in-depth stage (if recorded): candidates (ZK + journal), venue quartiles (IC7), full-text decisions
    cands, quart, ft = set(), {}, {}
    for f in ('INDEPTH-CANDIDATES-PART1', 'INDEPTH-CANDIDATES-PART2'):
        fp = S / f'{f}-{date}.json'
        if fp.exists():
            cands |= {str(c['n']) for c in json.loads(fp.read_text(encoding='utf-8'))}
    qp = S / 'quality' / f'CANDIDATE-QUARTILES-{date}.json'
    if qp.exists():
        quart = {str(r['n']): r for r in json.loads(qp.read_text(encoding='utf-8'))}
    fp = S / f'FULLTEXT-DECISIONS-{date}.csv'
    if fp.exists():
        ft = {r['id'].lstrip('n').lstrip('0'): r for r in csv.DictReader(open(fp, encoding='utf-8'))}
    counts = collections.Counter()
    with open(S / f'RECORD-LEDGER-{tag}.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for n in sorted(merged, key=int):
            m, a, b = merged[n], r1.get(n), r2.get(n)
            row = {c: m.get(c, '') for c in ('n', 'title', 'year', 'venue', 'type', 'doi', 'sources', 'hits', 'corpus_id',
                                             'auto_excluded')}
            if a:
                row.update(r1_decision=a['decision'], r1_code=a['code'], r1_reason=a['reason'])
            if b:
                row.update(r2_decision=b['decision'], r2_code=b['code'], r2_iot=b['iot'], r2_check=b['check'],
                           r2_reason=b['reason'])
            if m['auto_excluded']:
                status = 'auto-excluded'
            elif b:
                status = {'EXCLUDE': f"excluded R2 ({b['code']})", 'INCLUDE-SURVEY': 'survey (related work)'}.get(
                    b['decision'], 'scope A, primary')
            elif a and a['decision'] == 'EXCLUDE':
                status = f"excluded R1 ({a['code']})"
            else:
                status = 'NOT SCREENED'          # must never occur
            if n in cands:
                q = quart.get(n, {})
                row.update(indepth_candidate='yes', sjr2025=q.get('q2025', ''), sjr2024=q.get('q2024', ''))
                if q.get('q2025') != 'Q1':
                    status = f"excluded IC7 (SJR 2025 {q.get('q2025', '')})"
                elif n in ft:
                    d = ft[n]
                    row.update(ft_decision=d['recommended'], ft_code=d['recommended_code'], ft_reason=d['reason'],
                               ft_sheet=f"search/fulltext/sheets/{d['id']}.json")
                    status = 'included in depth' if d['recommended'] == 'INCLUDE' else f"excluded full text ({d['recommended_code']})"
            row['status'] = status
            counts[status] += 1
            w.writerow(row)
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'{v:5}  {k}')
    print(f'{sum(counts.values()):5}  unique records')
    if counts['NOT SCREENED']:
        raise SystemExit('some records have no decision')


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[a.index('--merged-tag') + 1] if '--merged-tag' in a else None)
