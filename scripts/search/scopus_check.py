#!/usr/bin/env python3
"""Check the Scopus exports of 2 October 2026 against the known papers and the review corpus.

Reads the latest search/exports/scopus/scopus-{S1,S2,S3,K1,K2}-<date>.csv of each search (S1 as in the V3 protocol,
with B5G and "next generation") and search/KNOWN-PAPERS-2026-10-02.csv, and records:
- for each export, how many rows satisfy its own string when re-applied to title, abstract and keywords (a check that
  each file is the search it is named after);
- for each known paper: held by Scopus (found by K1/K2 or by any string), and which strings retrieve it;
- the union of S1-S3 (by Scopus EID), the overlaps, and how many records are already in the corpus.
Matching: DOI (case-insensitive), else title reduced to lower-case letters and digits.

Usage: python3 scripts/search/scopus_check.py <date written into the output name>
"""
import csv, json, pathlib, re, sys
csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
EXP = ROOT / 'search' / 'exports' / 'scopus'


def has(text, term):
    term = term.strip('"').lower()
    t = re.escape(term).replace(r'\-', r'[-\s]?').replace(r'\ ', r'[-\s]+')
    return re.search(rf'(?<![a-z0-9]){t}(?:s|es)?(?![a-z0-9])', text) is not None


def anyof(x, terms):
    return any(has(x, t) for t in terms)


LED = ['blockchain', 'distributed ledger', 'smart contract']
PRIV = ['privacy', 'homomorphic encryption', 'secure aggregation', 'zero knowledge']
IOT = ['Internet of Things', 'iot', 'iiot', 'iov', 'edge', '5g', '6g', 'b5g', 'next generation', 'vehicular', 'industrial']
STRINGS = {
    'S1': lambda x: has(x, 'federated') and anyof(x, LED) and anyof(x, PRIV) and anyof(x, IOT),
    'S2': lambda x: anyof(x, ['federated', 'secure aggregation', 'machine learning']) and
                    anyof(x, ['zero knowledge', 'zk-SNARK', 'zksnark', 'input validation']),
    'S3': lambda x: has(x, 'federated') and has(x, 'secure aggregation') and anyof(x, ['poisoning', 'byzantine', 'malicious']),
    # X5, the scope-A search of the V5 protocol (2 October 2026)
    'X5': lambda x: anyof(x, ['federated', 'swarm learning', 'decentralized learning', 'decentralised learning',
                              'collaborative learning', 'collaborative machine learning', 'distributed learning']) and
                    anyof(x, LED + ['block chain']) and anyof(x, PRIV) and
                    anyof(x, ['poisoning', 'byzantine', 'malicious', 'free riding', 'free rider', 'sybil', 'backdoor',
                              'verifiable', 'zero knowledge', 'input validation']),
}


def norm_title(t):
    return re.sub(r'[^a-z0-9]', '', (t or '').lower())


def norm_doi(d):
    return (d or '').strip().lower()


def main(date):
    files = {k: sorted(EXP.glob(f'scopus-{k}-*.csv'))[-1] for k in ('S1', 'S2', 'S3', 'K1', 'K2')}
    ex = {k: list(csv.DictReader(open(f, encoding='utf-8-sig'))) for k, f in files.items()}
    out = {'date': date, 'files': {k: f.name for k, f in files.items()}, 'rows': {k: len(v) for k, v in ex.items()},
           'self_check': {}}
    for k, f in STRINGS.items():
        n = sum(1 for r in ex[k] if f(' '.join([r['Title'], r['Abstract'], r['Author Keywords'], r['Index Keywords']]).lower()))
        out['self_check'][k] = {'rows': len(ex[k]), 'match_own_string': n}

    def keys(r):
        return {norm_doi(r['DOI'])} - {''} | {norm_title(r['Title'])}
    idx = {k: set().union(*(keys(r) for r in v)) for k, v in ex.items()}
    known = list(csv.DictReader(open(ROOT / 'search' / 'KNOWN-PAPERS-2026-10-02.csv', encoding='utf-8')))
    out['known'] = []
    for p in known:
        kk = {norm_doi(p['doi'])} - {''} | {norm_title(p['title'])}
        held_by = [k for k in ('K1', 'K2', 'S1', 'S2', 'S3') if kk & idx[k]]
        found = [k for k in ('S1', 'S2', 'S3') if k in held_by]
        status = 'found' if found else ('held, not found' if held_by else 'not held')
        out['known'].append({'id': p['id'], 'set': p['set'], 'year': p['year'], 'title': p['title'],
                             'status': status, 'strings': found})
    union = {}
    for k in ('S1', 'S2', 'S3'):
        for r in ex[k]:
            union.setdefault(r['EID'], {'row': r, 'strings': []})['strings'].append(k)
    corpus = list(csv.DictReader(open(ROOT / 'corpus' / '_extraction' / 'papers.csv', encoding='utf-8')))
    cidx = {}
    for p in corpus:
        for key in ({norm_doi(p['doi'])} - {'', 'none'}) | {norm_title(p['title'])}:
            cidx[key] = p['id']
    in_corpus = sorted({cidx[k] for u in union.values() for k in keys(u['row']) if k in cidx})
    combos = {}
    for u in union.values():
        c = '+'.join(u['strings'])
        combos[c] = combos.get(c, 0) + 1
    out['union'] = {'records': len(union), 'by_strings': dict(sorted(combos.items())),
                    'corpus_papers_retrieved': in_corpus, 'n_corpus_papers_retrieved': len(in_corpus),
                    'new_to_us': len(union) - sum(1 for u in union.values() if keys(u['row']) & set(cidx)),
                    'by_type': {}, 'by_year': {}}
    for u in union.values():
        t, y = u['row']['Document Type'], u['row']['Year']
        out['union']['by_type'][t] = out['union']['by_type'].get(t, 0) + 1
        out['union']['by_year'][y] = out['union']['by_year'].get(y, 0) + 1
    out['union']['by_year'] = dict(sorted(out['union']['by_year'].items()))
    (ROOT / 'search' / f'SCOPUS-CHECK-{date}.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k != 'known'}, indent=1))
    for s in ('found', 'held, not found', 'not held'):
        ids = [k['id'] for k in out['known'] if k['status'] == s]
        print(f'{s}: {len(ids)} {ids}')


if __name__ == '__main__':
    main(sys.argv[1])
