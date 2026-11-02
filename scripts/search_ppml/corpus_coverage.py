#!/usr/bin/env python3
"""Every corpus paper (the supervisors' papers left out): is it in the Scopus and IEEE Xplore results of the PPML review,
and if not, why not (4 October 2026, asked by the author).

Reasons, in this order: retracted; a preprint (no DOI, or the corpus copy is an arXiv or other preprint); published
before 2020; no indexed abstract to test; outside the topic by its own title, abstract and keywords (no NG-IoT setting,
no privacy, no learning); on the topic but not matched by the search (survey arm: no survey word in the title and not
typed Review; primary arm: privacy not in the title and no threat term). Title, abstract and keywords come from OpenAlex
(CORPUS-SURVEYS-METADATA, CORPUS-PRIMARY-METADATA) or the ZK review's search records; terms are matched as in merge.py.

Output: search-ppml/CORPUS-COVERAGE-2026-10-04.csv

Usage: python3 scripts/search_ppml/corpus_coverage.py
"""
import csv, json, pathlib, sys
from collections import Counter

csv.field_size_limit(10 ** 9)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402

P = M.P
OUT = P / 'CORPUS-COVERAGE-2026-10-04.csv'


def main():
    idx = [r for r in csv.DictReader(open(P / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8')) if r['collection'] != 'supervisorcorpus']
    papers = {r['id']: r for r in csv.DictReader(open(M.ROOT / 'corpus' / '_extraction' / 'papers.csv', encoding='utf-8'))}
    rec = {r['n']: r for r in csv.DictReader(open(P / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8'))}
    found = {}
    for m in csv.DictReader(open(P / 'CORPUS-MATCHES-2026-10-04.csv', encoding='utf-8')):
        if {'Scopus', 'IEEE Xplore'} & set(rec[m['n']]['sources'].split('; ')):
            found[m['corpus_id']] = m['n']
    surveys = json.loads((P / 'CORPUS-SURVEYS-METADATA-2026-10-04.json').read_text())
    prim = json.loads((P / 'CORPUS-PRIMARY-METADATA-2026-10-04.json').read_text())
    zk = {}
    for f in ('MERGED-RECORDS-2026-10-02.csv', 'MERGED-RECORDS-2026-10-02-X5.csv'):
        for x in csv.DictReader(open(M.ROOT / 'search' / f, encoding='utf-8')):
            if x['doi'] and x['abstract']:
                zk[x['doi'].lower()] = {'title': x['title'], 'abstract': x['abstract'], 'keywords': x['keywords']}
    rows = []
    for c in idx:
        venue = papers.get(c['id'], {}).get('venue', '')
        meta = surveys.get(c['id']) or prim.get(c['doi']) or {}
        if not meta.get('abstract'):
            meta = zk.get(c['doi'], meta)
        ti = M.norm(meta.get('title') or c['title'])
        tak = M.norm(' '.join([meta.get('title') or c['title'], meta.get('abstract', ''), meta.get('keywords', '')]))
        lacks = [g for g, k in (('NG-IoT setting', 'NGIOT'), ('privacy', 'PPML'), ('learning', 'ML')) if not M.has(tak, k)]
        survey = c['kind'] == 'survey'
        if c['id'] in found:
            reason = 'in the results'
        elif c['kind'] == 'excluded from the corpus':
            reason = 'retracted'
        elif not c['doi'] or 'arxiv' in venue.lower() or 'preprint' in venue.lower() or (meta.get('type') == 'preprint'):
            reason = 'preprint'
        elif c['year'] and c['year'][:4] < '2020':
            reason = 'before 2020'
        elif not meta.get('abstract'):
            reason = 'no indexed abstract to test'
        elif lacks:
            reason = 'outside the topic: no ' + ' / no '.join(lacks)
        elif survey and not M.has(ti, 'SUR') and meta.get('type') != 'review':
            reason = 'on the topic, missed: no survey word in the title'
        elif not survey and not (M.has(ti, 'PPML') or M.has(tak, 'THREAT')):
            reason = 'on the topic, missed: privacy not in the title and no threat term'
        else:
            reason = 'on the topic, missed: not returned by the databases (indexing or wording)'
        rows.append({'id': c['id'], 'collection': c['collection'].split(' ')[0], 'kind': c['kind'], 'year': c['year'],
                     'title': c['title'], 'doi': c['doi'], 'reason': reason, 'record': found.get(c['id'], '')})
    with open(OUT, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), 'corpus papers;', sum(r['reason'] == 'in the results' for r in rows), 'in the results')
    for k, v in sorted(Counter(r['reason'].split(':')[0] if r['reason'].startswith('outside') else r['reason'] for r in rows).items(), key=lambda x: -x[1]):
        print(f'  {v:4}  {k}')
    print('by collection (in results / all):')
    for col in sorted({r['collection'] for r in rows}):
        rr = [r for r in rows if r['collection'] == col]
        print(f"  {col}: {sum(r['reason'] == 'in the results' for r in rr)} / {len(rr)}")
    print('outside the topic, detail:', Counter(r['reason'] for r in rows if r['reason'].startswith('outside')).most_common())


if __name__ == '__main__':
    main()
