#!/usr/bin/env python3
"""Which records of the PPML search are papers the author already holds (4 October 2026).

The author asked that every record of the search that is already in the corpus be highlighted, "and by corpus i mean
every piece in corpus (not just secondary studies)". The match is for information while screening: it identifies no
study and decides nothing.

Corpus index (search-ppml/CORPUS-INDEX-2026-10-04.csv), one row per paper:
  corpus/_extraction/papers.csv        the 162 papers of newcorpus, surveycorpus and oldcorpus (id, title, DOI, type)
  corpus/searchcorpus/{papers,surveys,gapcheck}/n####   papers of the ZK review; title and DOI from its search records
                                       (search/MERGED-RECORDS-2026-10-02.csv); a paper that is also a corpus paper keeps
                                       the corpus id and gains the second folder
  corpus/searchcorpus/_published-versions/S033          published DOI of S033 (held in the corpus as a preprint)
  corpus/ppmlcorpus/surveys/p####       the surveys the author included in the PPML review that were new to the corpus
  corpus/_extraction/EXCLUDED.json     papers taken out of the corpus (O055, retracted)
  supervisorcorpus/<name>/*.pdf        the supervisors' review papers (title from the file name; no DOI on record)

Matching against every unique record of the search (search-ppml/MERGED-RECORDS-2026-10-04.csv, set-aside records
included): the same DOI; else, when the two do not carry different DOIs, the same title (letters and digits only); else a near-identical title (similarity of at
least 0.93 on titles of six words or more, or a corpus title cut short in a file name that is the start of the record's
title). Near matches are listed for checking in the output.

Output: search-ppml/CORPUS-MATCHES-2026-10-04.csv (one row per matched record)

Usage: python3 scripts/search_ppml/corpus_match.py
"""
import csv, json, pathlib, re
from difflib import SequenceMatcher

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
C = ROOT / 'corpus'
INDEX = P / 'CORPUS-INDEX-2026-10-04.csv'
MATCHES = P / 'CORPUS-MATCHES-2026-10-04.csv'

flat = lambda t: re.sub(r'[^a-z0-9]', '', (t or '').lower())
words = lambda t: re.sub(r'[^a-z0-9]+', ' ', (t or '').lower()).split()
doi_norm = lambda d: re.sub(r'^https?://(dx\.)?doi\.org/', '', (d or '').strip().lower()) if (d or '').strip().lower() not in ('', 'none') else ''


def kind_of(document_type):
    if document_type in ('survey', 'systematic review'):
        return 'survey'
    if document_type.startswith('primary'):
        return 'primary study'
    return document_type or 'not recorded'


def corpus_index():
    man = {p['id']: p for p in json.load(open(C / '_extraction' / 'MANIFEST.json'))['papers']}
    rows = {}
    for r in csv.DictReader(open(C / '_extraction' / 'papers.csv', encoding='utf-8')):
        m = man.get(r['id'], {})
        rows[r['id']] = {'id': r['id'], 'collection': f"{r['corpus']}" + (f" ({r['group']})" if r['group'] and r['group'] != 'papers' else ''),
                         'kind': kind_of(r['document_type']), 'title': r['title'], 'year': r['year'], 'doi': doi_norm(r['doi']),
                         'doi_alias': '', 'pdf': f"corpus/{m['folder']}/{m['pdf']}" if m else '', 'also': ''}
    rows['S033']['doi_alias'] = '10.1109/mcom.001.2500141'           # published version, searchcorpus/_published-versions
    rows['S033']['also'] = 'corpus/searchcorpus/_published-versions/S033/S033-published.pdf'
    recs = {f"n{int(r['n']):04d}": r for r in csv.DictReader(open(ROOT / 'search' / 'MERGED-RECORDS-2026-10-02.csv', encoding='utf-8'))}
    for group, kind in (('papers', 'primary study'), ('surveys', 'survey'), ('gapcheck', 'primary study')):
        for d in sorted((C / 'searchcorpus' / group).iterdir()):
            if not d.is_dir() or d.name not in recs:
                continue
            r = recs[d.name]
            pdf = f"corpus/searchcorpus/{group}/{d.name}/{d.name}.pdf"
            if r['corpus_id'] and r['corpus_id'] in rows:
                rows[r['corpus_id']]['also'] = '; '.join(x for x in (rows[r['corpus_id']]['also'], pdf) if x)
                continue
            rows[d.name] = {'id': d.name, 'collection': f'searchcorpus ({group})', 'kind': kind, 'title': r['title'],
                            'year': r['year'], 'doi': doi_norm(r['doi']), 'doi_alias': '',
                            'pdf': pdf if (ROOT / pdf).exists() else '', 'also': ''}
    for d in sorted((C / 'ppmlcorpus' / 'surveys').glob('p*')) if (C / 'ppmlcorpus').exists() else []:   # PPML review, 4 Oct 2026
        prov = json.loads((d / 'PROVENANCE.json').read_text())
        rows[d.name] = {'id': d.name, 'collection': 'ppmlcorpus (surveys)', 'kind': 'survey', 'title': prov['title'],
                        'year': '', 'doi': doi_norm(prov['doi']), 'doi_alias': '', 'pdf': f"corpus/ppmlcorpus/surveys/{d.name}/{d.name}.pdf", 'also': ''}
    for d in sorted((C / 'ppmlcorpus' / 'check').glob('p*')) if (C / 'ppmlcorpus' / 'check').exists() else []:   # full texts after the second screening, 5 Oct 2026
        prov = json.loads((d / 'PROVENANCE.json').read_text())
        rows[d.name] = {'id': d.name, 'collection': 'ppmlcorpus (check)', 'kind': '', 'title': prov['title'],
                        'year': '', 'doi': doi_norm(prov['doi']), 'doi_alias': '', 'pdf': f"corpus/ppmlcorpus/check/{d.name}/{d.name}.pdf", 'also': ''}
    for d in sorted((C / 'ppmlcorpus' / 'check-rs1').glob('RS1-*')) if (C / 'ppmlcorpus' / 'check-rs1').exists() else []:   # R-S1 candidates, 8 Oct 2026
        prov = json.loads((d / 'PROVENANCE.json').read_text())
        rid = f"r{int(d.name.split('-')[1]):04d}"                    # corpus id of an R-S1 record (r + row of the export), as n####/p####
        rows[rid] = {'id': rid, 'collection': 'ppmlcorpus (check-rs1)', 'kind': '', 'title': prov['title'],
                        'year': prov.get('year', ''), 'doi': doi_norm(prov['doi']), 'doi_alias': '', 'pdf': f"corpus/ppmlcorpus/check-rs1/{d.name}/{d.name}.pdf", 'also': ''}
    for x in json.load(open(C / '_extraction' / 'EXCLUDED.json'))['papers']:
        rows[x['id']] = {'id': x['id'], 'collection': f"_excluded ({x['reason']})", 'kind': 'excluded from the corpus',
                         'title': x['title'], 'year': '', 'doi': '', 'doi_alias': '', 'pdf': f"corpus/{x['moved_to']}/{x['pdf']}", 'also': ''}
    for f in sorted((ROOT / 'supervisorcorpus').glob('*/*.pdf')):
        m = re.match(r'(\d{4}) - (.*) \(([^)]*)\)$', f.stem)
        if m:
            rows[f'SUP:{f.stem}'] = {'id': f'supervisor: {f.parent.name}', 'collection': 'supervisorcorpus', 'kind': 'survey (supervisor)',
                                     'title': m.group(2), 'year': m.group(1), 'doi': '', 'doi_alias': '',
                                     'pdf': str(f.relative_to(ROOT)), 'also': ''}
    with open(INDEX, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['id', 'collection', 'kind', 'year', 'title', 'doi', 'doi_alias', 'pdf', 'also'])
        w.writeheader()
        w.writerows(rows.values())
    return list(rows.values())


def match(c, r):
    """how record r matches corpus paper c, or None"""
    d = r['doi']
    if d and d in (c['doi'], c['doi_alias']):
        return 'same DOI', 1.0
    if d and c['doi'] and d not in (c['doi'], c['doi_alias']):
        return None                                   # both carry a DOI and they differ: different works with similar titles
    a, b = flat(c['title']), flat(r['title'])
    if a and a == b:
        return 'same title (the corpus copy has no DOI, e.g. a preprint)', 1.0
    if c['collection'] == 'supervisorcorpus' and len(a) > 30 and b.startswith(a):
        return 'title from the file name is the start of the record title', 1.0
    if min(len(words(c['title'])), len(words(r['title']))) >= 6 and abs(len(a) - len(b)) < 0.2 * max(len(a), len(b)):
        s = SequenceMatcher(None, a, b).ratio()
        if s >= 0.93:
            return 'near-identical title (the corpus copy has no DOI, e.g. a preprint)', round(s, 3)
    return None


def main():
    corpus = corpus_index()
    records = list(csv.DictReader(open(P / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8')))
    out = []
    for r in records:
        hits = [(c, *m) for c in corpus if (m := match(c, r))]
        for c, how, score in hits:
            out.append({'n': r['n'], 'set_aside': 'yes' if r['auto_excluded'] else '', 'corpus_id': c['id'], 'collection': c['collection'],
                        'kind': c['kind'], 'how': how, 'score': score, 'corpus_title': c['title'], 'record_title': r['title'],
                        'record_doi': r['doi'], 'pdf': c['pdf'], 'also': c['also']})
    with open(MATCHES, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]) if out else ['n'])
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    recs = {o['n'] for o in out}
    print(f'corpus index {len(corpus)} papers | matched records {len(recs)} (to screen {len({o["n"] for o in out if not o["set_aside"]})}, '
          f'set aside {len({o["n"] for o in out if o["set_aside"]})}) | corpus papers found {len({o["corpus_id"] for o in out})}')
    print(Counter(o['how'] for o in out), Counter(o['kind'] for o in out))
    for o in out:
        if o['how'] != 'same DOI':
            print(f"  check: n{o['n']} {o['how']} {o['score']} | {o['corpus_id']}: {o['corpus_title'][:70]} | record: {o['record_title'][:70]}")


if __name__ == '__main__':
    main()
