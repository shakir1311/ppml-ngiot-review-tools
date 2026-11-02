#!/usr/bin/env python3
"""Studies identified via other methods (PRISMA 2020): corpus papers on the review's topic that the database searches did
not return (4 October 2026). The author chose to assess them against the same criteria as known studies from earlier
reading, reported in PRISMA's "identification of studies via other methods" box — not by a search built on their titles
or DOIs.

Input: search-ppml/CORPUS-COVERAGE-2026-10-04.csv (corpus_coverage.py; reason "on the topic, missed: …"); title, abstract
and keywords from OpenAlex (CORPUS-SURVEYS-METADATA, CORPUS-PRIMARY-METADATA) or the ZK review's search records; venue
from corpus/_extraction/papers.csv or those records.
Output: search-ppml/OTHER-METHODS-2026-10-04.csv, one row per study, numbered from 100001 so that the numbers never meet
those of the merged records.

Usage: python3 scripts/search_ppml/other_methods.py
"""
import csv, json, pathlib, sys

csv.field_size_limit(10 ** 9)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402

P = M.P
OUT = P / 'OTHER-METHODS-2026-10-04.csv'
FIRST = 100001


def main():
    cov = [r for r in csv.DictReader(open(P / 'CORPUS-COVERAGE-2026-10-04.csv', encoding='utf-8')) if r['reason'].startswith('on the topic')]
    papers = {r['id']: r for r in csv.DictReader(open(M.ROOT / 'corpus' / '_extraction' / 'papers.csv', encoding='utf-8'))}
    idx = {r['id']: r for r in csv.DictReader(open(P / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))}
    surveys = json.loads((P / 'CORPUS-SURVEYS-METADATA-2026-10-04.json').read_text())
    prim = json.loads((P / 'CORPUS-PRIMARY-METADATA-2026-10-04.json').read_text())
    zk = {}
    for f in ('MERGED-RECORDS-2026-10-02.csv', 'MERGED-RECORDS-2026-10-02-X5.csv'):
        for x in csv.DictReader(open(M.ROOT / 'search' / f, encoding='utf-8')):
            if x['doi'] and x['abstract']:
                zk[x['doi'].lower()] = x
    rows = []
    for i, c in enumerate(sorted(cov, key=lambda r: r['id']), FIRST):
        meta, src = surveys.get(c['id']), 'OpenAlex'
        if not meta:
            meta = prim.get(c['doi'])
        if not meta or not meta.get('abstract'):
            meta, src = zk.get(c['doi']), "the ZK review's search records (Scopus or IEEE Xplore)"
        venue = papers[c['id']]['venue'] if c['id'] in papers else (zk.get(c['doi'], {}).get('venue', ''))
        rows.append({'n': i, 'corpus_id': c['id'], 'kind': c['kind'], 'year': c['year'], 'title': c['title'], 'doi': c['doi'],
                     'venue': venue.split(';')[0].strip(), 'why_missed': c['reason'].replace('on the topic, missed: ', ''),
                     'abstract': (meta or {}).get('abstract', ''), 'keywords': (meta or {}).get('keywords', ''),
                     'metadata_from': src, 'pdf': idx[c['id']]['pdf']})
    with open(OUT, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r['n'], r['corpus_id'], r['kind'], '| abstract', len(r['abstract']), '|', r['metadata_from'][:20], '|', r['title'][:60])


if __name__ == '__main__':
    main()
