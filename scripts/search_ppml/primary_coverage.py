#!/usr/bin/env python3
"""How many of the corpus's primary studies each candidate primary-study search would retrieve (4 October 2026).

The same offline check as for the surveys (search-ppml/COVERAGE-2026-10-04.md): the corpus is not searched for and
identifies nothing; it only measures whether a candidate string reaches the kind of study the author has collected.
Title, abstract and keywords of each corpus primary study with a DOI are read from OpenAlex (no e-mail address sent)
and kept in search-ppml/CORPUS-PRIMARY-METADATA-2026-10-04.json, or, where OpenAlex has no abstract (e.g. Elsevier),
from the ZK review's search records (search/MERGED-RECORDS-2026-10-02*.csv); each candidate of size_probe.py is then applied to
them with the review's own term matching (merge.term_re).

Output: search-ppml/PRIMARY-COVERAGE-2026-10-04.json

Usage: python3 scripts/search_ppml/primary_coverage.py
"""
import csv, json, pathlib, sys, time, urllib.parse, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402
import strings as S                                   # noqa: E402
from size_probe import THREAT                         # noqa: E402

P = M.P
META = P / 'CORPUS-PRIMARY-METADATA-2026-10-04.json'


def fetch(dois):
    out = {}
    for i in range(0, len(dois), 40):
        chunk = dois[i:i + 40]
        url = 'https://api.openalex.org/works?' + urllib.parse.urlencode(
            {'filter': 'doi:' + '|'.join(chunk), 'per-page': 50, 'select': 'doi,title,abstract_inverted_index,keywords,type'})
        req = urllib.request.Request(url, headers={'User-Agent': 'slr-size-probe/1.0'})
        with urllib.request.urlopen(req, timeout=60) as r:
            for w in json.load(r)['results']:
                inv = w.get('abstract_inverted_index') or {}
                words = sorted((p, t) for t, ps in inv.items() for p in ps)
                out[w['doi'].replace('https://doi.org/', '').lower()] = {
                    'title': w.get('title') or '', 'abstract': ' '.join(t for _, t in words),
                    'keywords': '; '.join(k.get('display_name', '') for k in (w.get('keywords') or []))}
        time.sleep(0.5)
    return out


def main():
    index = [r for r in csv.DictReader(open(P / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))
             if r['kind'] in ('primary study', 'position or magazine article')]
    meta = json.loads(META.read_text()) if META.exists() else {}
    want = [r['doi'] for r in index if r['doi'] and r['doi'] not in meta]
    if want:
        meta.update(fetch(want))
        META.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding='utf-8')
    zk = {}                                           # second source: the ZK review's search records (Scopus abstracts)
    for f in ('MERGED-RECORDS-2026-10-02.csv', 'MERGED-RECORDS-2026-10-02-X5.csv'):
        for x in csv.DictReader(open(M.ROOT / 'search' / f, encoding='utf-8')):
            if x['doi'] and x['abstract']:
                zk[x['doi'].lower()] = {'title': x['title'], 'abstract': x['abstract'], 'keywords': x['keywords']}
    rx = lambda g: [M.term_re(t) for t in g]
    G = {'PPML': rx(S.PPML), 'ML': rx(S.ML), 'NGIOT': rx(S.NGIOT), 'THREAT': rx(THREAT)}
    has = lambda text, g: any(p.search(text) for p in G[g])
    options = {
        'A': lambda ti, tak: has(ti, 'PPML') and has(tak, 'ML') and has(tak, 'NGIOT'),
        'B': lambda ti, tak: has(ti, 'PPML') and has(tak, 'ML') and has(tak, 'NGIOT') and has(tak, 'THREAT'),
        'C': lambda ti, tak: has(tak, 'PPML') and has(tak, 'ML') and has(tak, 'NGIOT') and has(tak, 'THREAT'),
        'D': lambda ti, tak: has(tak, 'PPML') and has(tak, 'ML') and has(tak, 'NGIOT'),
    }
    rows, nodoi, missing = [], [], []
    for r in index:
        if not r['doi']:
            nodoi.append(r['id'])
            continue
        m = meta.get(r['doi'])
        if not m or not m['abstract']:
            m = zk.get(r['doi'])
        if not m or not m['abstract']:
            missing.append(r['id'])
            continue
        ti = M.norm(m['title'] or r['title'])
        tak = M.norm(' '.join([m['title'] or r['title'], m['abstract'], m['keywords']]))
        rows.append({'id': r['id'], 'title': r['title'], **{k: f(ti, tak) for k, f in options.items()},
                     'privacy': has(tak, 'PPML'), 'learning': has(tak, 'ML'), 'ngiot': has(tak, 'NGIOT'), 'threat': has(tak, 'THREAT')})
    res = {'date': '2026-10-04', 'corpus_primary': len(index), 'tested': len(rows), 'no_doi': nodoi, 'no_abstract': missing,
           'retrieved': {k: sum(r[k] for r in rows) for k in options},
           'A_or_C': sum(r['A'] or r['C'] for r in rows), 'in_scope_D': sum(r['D'] for r in rows),
           'in_scope_D_not_A': [r['id'] for r in rows if r['D'] and not r['A']],
           'lacking': {'privacy': sum(not r['privacy'] for r in rows), 'learning': sum(not r['learning'] for r in rows),
                       'ngiot': sum(not r['ngiot'] for r in rows), 'threat': sum(not r['threat'] for r in rows)},
           'rows': rows}
    (P / 'PRIMARY-COVERAGE-2026-10-04.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in res.items() if k != 'rows'}, indent=1))


if __name__ == '__main__':
    main()
