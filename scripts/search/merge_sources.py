#!/usr/bin/env python3
"""Merge the database exports of the search into one list of unique records for screening.

Sources (search/exports/): Scopus S1-S3 (CSV), IEEE Xplore S1 (four year parts), S2, S3 (CSV), ScienceDirect S1
(fallback queries B1-B5), S2, S3 (RIS). Each file is checked by re-applying its search string to the record's title,
abstract and keywords (IEEE also its IEEE Terms and MeSH terms). Records are merged on DOI (case-insensitive); a
record without a DOI joins one with the same title (lower-case letters and digits only). Records with different DOIs
but the same title are kept apart (for example a conference paper and its journal version; EC2 decides at screening).
The known papers (search/KNOWN-PAPERS-2026-10-02.csv) and the corpus (corpus/_extraction/papers.csv) are looked up
in the merged list; the Scopus K1/K2 exports tell whether Scopus holds a known paper at all.

Automated step before screening: IEEE Xplore's "All Metadata" field searches more than the title, abstract and
keywords (on 2 October about half of its records did not satisfy the string there). A record found only by IEEE Xplore
is therefore flagged auto_excluded when its title, abstract, author keywords and IEEE terms satisfy none of S1-S3 --
the same rule that Scopus (TITLE-ABS-KEY) and ScienceDirect (title, abstract, keywords) apply. Records from Scopus or
ScienceDirect are kept as the databases returned them. Nothing is deleted; the flag is a column.

Writes search/MERGED-RECORDS-<date>.csv (one row per unique record, with the sources and strings that found it) and
search/MERGE-CHECK-<date>.json (counts, self-checks, overlaps, known papers).
Usage: python3 scripts/search/merge_sources.py <date> [--out-tag TAG] [--keep-numbers PREVIOUS-MERGED.csv]
  --keep-numbers gives every record found in an earlier merge its earlier number n (matched by DOI, then title), so
  decisions recorded against n stay linked; new records are numbered after the highest earlier n. Outputs are written
  as MERGED-RECORDS-<TAG>.csv and MERGE-CHECK-<TAG>.json (TAG defaults to the date), so earlier outputs stay unchanged.
"""
import csv, json, pathlib, re, sys
from scopus_check import STRINGS, norm_doi, norm_title

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
EXP = ROOT / 'search' / 'exports'


def rec(source, string, title, abstract, keywords, doi, year, venue, doctype, ident, file):
    return {'source': source, 'string': string, 'title': (title or '').strip(), 'abstract': (abstract or '').strip(),
            'keywords': (keywords or '').strip(), 'doi': norm_doi(doi), 'year': (year or '').strip(),
            'venue': (venue or '').strip(), 'type': (doctype or '').strip(), 'id': ident, 'file': file}


def scopus(date):
    out = []
    for s in ('S1', 'S2', 'S3', 'X5'):
        f = EXP / 'scopus' / f'scopus-{s}-{date}.csv'
        if not f.exists():
            continue
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            out.append(rec('Scopus', s, r['Title'], r['Abstract'], '; '.join([r['Author Keywords'], r['Index Keywords']]),
                           r['DOI'], r['Year'], r['Source title'], r['Document Type'], r['EID'], f.name))
    return out


def ieee(date):
    out = []
    for f in sorted((EXP / 'ieee').glob(f'ieee-*-{date}.csv')):
        s = f.name.split('-')[1]
        for r in csv.DictReader(open(f, encoding='utf-8-sig', errors='replace')):
            kw = '; '.join([r['Author Keywords'], r['IEEE Terms'], r.get('Mesh_Terms', '')])
            out.append(rec('IEEE Xplore', s, r['Document Title'], r['Abstract'], kw, r['DOI'], r['Publication Year'],
                           r['Publication Title'], '', r['Document Identifier'] + ':' + r['PDF Link'], f.name))
    return out


def ris_records(path):
    recs, cur = [], {}
    for line in open(path, encoding='utf-8-sig', errors='replace'):
        m = re.match(r'^([A-Z][A-Z0-9])  - ?(.*)$', line.rstrip('\n'))
        if not m:
            continue
        tag, val = m.groups()
        if tag == 'ER':
            recs.append(cur)
            cur = {}
        else:
            cur.setdefault(tag, []).append(val.strip())
    return recs


def sciencedirect(date):
    out = []
    for f in sorted((EXP / 'sciencedirect').glob(f'sd-*-{date}.ris')):
        s = f.name.split('-')[1]
        for r in ris_records(f):
            g = lambda *tags: next((r[t][0] for t in tags if r.get(t)), '')
            doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', g('DO'))
            out.append(rec('ScienceDirect', s, g('TI', 'T1'), g('AB'), '; '.join(r.get('KW', [])), doi,
                           g('PY', 'Y1', 'DA')[:4], g('JO', 'T2', 'JF'), g('TY'), g('UR'), f.name))
    return out


def text(r):
    return ' '.join([r['title'], r['abstract'], r['keywords']]).lower()


def main(date, tag=None, keep=None):
    tag = tag or date
    records = scopus(date) + ieee(date) + sciencedirect(date)
    out = {'date': date, 'files': {}, 'self_check': {}}
    for r in records:
        k = f"{r['source']} {r['string']}"
        out['files'].setdefault(k, set()).add(r['file'])
        c = out['self_check'].setdefault(k, {'records': 0, 'match_own_string': 0})
        c['records'] += 1
        c['match_own_string'] += bool(STRINGS[r['string']](text(r)))
    out['files'] = {k: sorted(v) for k, v in out['files'].items()}

    merged, by_doi, by_title = [], {}, {}
    for r in records:
        t = norm_title(r['title'])
        m = by_doi.get(r['doi']) if r['doi'] else None
        if m is None and not r['doi']:
            m = by_title.get(t)
        if m is None and r['doi'] and t in by_title and not by_title[t]['doi']:
            m = by_title[t]
            m['doi'] = r['doi']
        if m is None:
            m = {'doi': r['doi'], 'title': r['title'], 'year': r['year'], 'venue': r['venue'], 'type': r['type'],
                 'abstract': r['abstract'], 'keywords': r['keywords'], 'sources': set(), 'hits': set()}
            merged.append(m)
        m['sources'].add(r['source'])
        m['hits'].add(f"{r['source']}:{r['string']}")
        for f in ('abstract', 'keywords', 'venue', 'type', 'year'):
            if not m[f] and r[f]:
                m[f] = r[f]
        if m['doi']:
            by_doi[m['doi']] = m
        by_title.setdefault(t, m)
    same_title = {}
    for m in merged:
        same_title.setdefault(norm_title(m['title']), []).append(m)
    out['same_title_different_doi'] = sum(1 for v in same_title.values() if len(v) > 1)

    combos = {}
    for m in merged:
        k = ' + '.join(sorted(m['sources']))
        combos[k] = combos.get(k, 0) + 1
    out['unique_records'] = len(merged)
    out['by_sources'] = dict(sorted(combos.items(), key=lambda x: -x[1]))
    out['per_source_unique'] = {s: sum(1 for m in merged if s in m['sources'])
                                for s in ('Scopus', 'IEEE Xplore', 'ScienceDirect')}
    out['not_in_scopus'] = sum(1 for m in merged if 'Scopus' not in m['sources'])

    corpus = list(csv.DictReader(open(ROOT / 'corpus' / '_extraction' / 'papers.csv', encoding='utf-8')))
    cidx = {}
    for p in corpus:
        for key in ({norm_doi(p['doi'])} - {'', 'none'}) | {norm_title(p['title'])}:
            cidx[key] = p['id']
    for m in merged:
        ids = {cidx[k] for k in ({m['doi']} - {''}) | {norm_title(m['title'])} if k in cidx}
        m['corpus_id'] = ', '.join(sorted(ids))
    out['in_corpus'] = sum(1 for m in merged if m['corpus_id'])
    out['new_to_us'] = len(merged) - out['in_corpus']

    held = set()
    for k in ('K1', 'K2'):
        for r in csv.DictReader(open(EXP / 'scopus' / f'scopus-{k}-{date}.csv', encoding='utf-8-sig')):
            held |= {norm_doi(r['DOI'])} - {''} | {norm_title(r['Title'])}
    known = list(csv.DictReader(open(ROOT / 'search' / 'KNOWN-PAPERS-2026-10-02.csv', encoding='utf-8')))
    out['known'] = []
    mi = {}
    for m in merged:
        for key in ({m['doi']} - {''}) | {norm_title(m['title'])}:
            mi[key] = m
    for p in known:
        keys = {norm_doi(p['doi'])} - {''} | {norm_title(p['title'])}
        m = next((mi[k] for k in keys if k in mi), None)
        out['known'].append({'id': p['id'], 'set': p['set'], 'held_by_scopus': bool(keys & held),
                             'found_by': sorted(m['hits']) if m else []})

    for m in merged:
        m['auto_excluded'] = ''
        if m['sources'] == {'IEEE Xplore'} and not any(f(text(m)) for f in STRINGS.values()):
            m['auto_excluded'] = 'IEEE Xplore only; title, abstract and keywords satisfy none of the search strings'
    n_ident = {src: sum(1 for r in records if r['source'] == src) for src in ('Scopus', 'IEEE Xplore', 'ScienceDirect')}
    out['prisma'] = {'identified': n_ident, 'identified_total': len(records),
                     'duplicates_removed': len(records) - len(merged),
                     'auto_excluded': sum(1 for m in merged if m['auto_excluded']),
                     'to_screen': sum(1 for m in merged if not m['auto_excluded'])}
    out['to_screen_not_in_scopus'] = {src: sum(1 for m in merged if not m['auto_excluded'] and m['sources'] == {src})
                                      for src in ('IEEE Xplore', 'ScienceDirect')}
    cols = ['n', 'doi', 'title', 'year', 'venue', 'type', 'sources', 'hits', 'corpus_id', 'auto_excluded', 'abstract',
            'keywords']
    order = sorted(merged, key=lambda m: (m['year'], norm_title(m['title'])))
    if keep:
        prev_doi, prev_title = {}, {}
        for r in csv.DictReader(open(keep, encoding='utf-8')):
            if r['doi']:
                prev_doi[norm_doi(r['doi'])] = int(r['n'])
            prev_title.setdefault(norm_title(r['title']), int(r['n']))
        used, nxt = set(), max(list(prev_doi.values()) + list(prev_title.values())) + 1
        for m in order:
            n = prev_doi.get(m['doi']) if m['doi'] else None
            if n is None:
                n = prev_title.get(norm_title(m['title']))
            if n is not None and n not in used:
                m['n'] = n
                used.add(n)
        for m in order:
            if 'n' not in m:
                m['n'] = nxt
                nxt += 1
        out['numbering'] = {'kept_from': pathlib.Path(keep).name, 'records_kept_number': len(used),
                            'new_records': sum(1 for m in order if m['n'] not in used)}
    else:
        for n, m in enumerate(order, 1):
            m['n'] = n
    with open(ROOT / 'search' / f'MERGED-RECORDS-{tag}.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for m in sorted(order, key=lambda m: m['n']):
            w.writerow({**{c: m.get(c, '') for c in cols}, 'sources': '; '.join(sorted(m['sources'])),
                        'hits': '; '.join(sorted(m['hits']))})
    (ROOT / 'search' / f'MERGE-CHECK-{tag}.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k not in ('known', 'files')}, indent=1))
    for s in ('core', 'survey'):
        ks = [k for k in out['known'] if k['set'] == s]
        print(s, 'found', sum(1 for k in ks if k['found_by']), 'of', len(ks),
              '| not found:', [(k['id'], 'held' if k['held_by_scopus'] else 'not held') for k in ks if not k['found_by']])


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k: a[a.index(k) + 1] if k in a else None
    main(a[0], opt('--out-tag'), opt('--keep-numbers'))
