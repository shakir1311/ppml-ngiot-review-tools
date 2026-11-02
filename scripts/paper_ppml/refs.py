#!/usr/bin/env python3
"""Reference data of the PPML review (paper V29 onwards), built from the database export records, not typed by hand.

Cited works: the included studies (search-ppml/FINAL-STUDIES-2026-10-05.csv; those of the supplementary search R-S1 matched in
its export, search-ppml/evidence/regulation-search/exports) and the three agreed outside sources
(PRISMA 2020, GDPR, EDPB guidelines 02/2025), whose entries are the verified ones of the earlier review
(scripts/paper/refs.py FOUNDATIONS). Each study is matched by DOI in the exports of this review's searches
(search-ppml/exports: Scopus first, then IEEE Xplore, then ScienceDirect); a study identified via other methods is matched
in the exports of the earlier systematic search (search/exports) or, failing that, in the review's own record of it
(search-ppml/OTHER-METHODS-2026-10-04.csv: venue string as recorded) with the authors from the PDF metadata. IEEE style:
initials and surname; more than six authors -> first author et al. Keys are the corpus ids.

Usage: python3 scripts/paper_ppml/refs.py   -> myliteraturereviewpaper/ppml2026/refs.json
"""
import csv, glob, json, pathlib, re, sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'paper'))
import refs as R0                                    # noqa: E402  (helpers and the foundations of the earlier review)

OUT = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json'


def index(base, scopus_files=None):
    idx = {}
    for f in (scopus_files if scopus_files is not None else sorted(glob.glob(str(base / 'scopus' / '*.csv')))):
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            d = r.get('DOI', '').lower()
            if d and d not in idx:
                pg = f"pp. {r['Page start']}–{r['Page end']}" if r.get('Page start') and r.get('Page end') else (f"Art. no. {r['Art. No.']}" if r.get('Art. No.') else '')
                idx[d] = ('Scopus', R0.names_scopus(r.get('Author full names') or r.get('Authors', '')), r['Title'], r['Source title'],
                          r['Volume'], r['Issue'], pg, r['Year'], r['DOI'])
    for f in sorted(glob.glob(str(base / 'ieee' / '*.csv'))):
        for r in csv.DictReader(open(f, encoding='utf-8-sig', errors='replace')):
            d = r.get('DOI', '').lower()
            if d and d not in idx:
                pg = f"pp. {r['Start Page']}–{r['End Page']}" if r['Start Page'] and r['End Page'] else ''
                idx[d] = ('IEEE Xplore', [a.strip() for a in r['Authors'].split(';') if a.strip()], r['Document Title'],
                          r['Publication Title'], r['Volume'], r['Issue'], pg, r['Publication Year'], r['DOI'])
    for f in sorted(glob.glob(str(base / 'sciencedirect' / '*.ris'))):
        cur = {}
        for line in open(f, encoding='utf-8-sig', errors='replace'):
            m = re.match(r'^([A-Z][A-Z0-9])  - ?(.*)$', line.rstrip('\n'))
            if not m:
                continue
            t, v = m.groups()
            if t == 'ER':
                d = re.sub(r'^https?://(dx\.)?doi\.org/', '', (cur.get('DO') or [''])[0]).lower()
                if d and d not in idx:
                    sp, ep = (cur.get('SP') or [''])[0], (cur.get('EP') or [''])[0]
                    pg = f'pp. {sp}–{ep}' if sp and ep else (f'Art. no. {sp}' if sp else '')
                    idx[d] = ('ScienceDirect', R0.names_ris(cur.get('AU', [])), (cur.get('TI') or cur.get('T1') or [''])[0],
                              (cur.get('JO') or cur.get('T2') or [''])[0], (cur.get('VL') or [''])[0], (cur.get('IS') or [''])[0],
                              pg, (cur.get('PY') or [''])[0][:4], d)
                cur = {}
            else:
                cur.setdefault(t, []).append(v.strip())
    return idx


def from_record(k, cid):
    """A study via other methods that no export holds: venue as the review recorded it, authors from the PDF metadata."""
    idx = {r['id']: r for r in csv.DictReader(open(ROOT / 'search-ppml' / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))}
    meta = json.loads((ROOT / pathlib.Path(idx[cid]['pdf']).parent / 'metadata.json').read_text(encoding='utf-8'))
    au = [a.strip() for a in re.split(r';|,| and ', meta.get('pdf_metadata', {}).get('author', '')) if a.strip()]
    names = [f"{R0.initials(' '.join(a.split()[:-1]))} {a.split()[-1]}".strip() for a in au]
    return R0.authors(names), meta


def main():
    own, earlier = index(ROOT / 'search-ppml' / 'exports'), index(ROOT / 'search' / 'exports')
    supp = index(ROOT / 'search-ppml' / 'evidence' / 'regulation-search' / 'exports',     # the supplementary search R-S1 (recorded since 8 Oct 2026)
                 sorted(glob.glob(str(ROOT / 'search-ppml' / 'evidence' / 'regulation-search' / 'exports' / 'scopus-R-S1-export_*.csv'))))
    F = list(csv.DictReader(open(ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')))
    K = {r['corpus_id']: r for r in csv.DictReader(open(ROOT / 'search-ppml' / 'OTHER-METHODS-2026-10-04.csv', encoding='utf-8'))}
    refs, problems = {}, []
    for r in F:
        cid, doi = r['corpus_id'], r['doi'].lower()
        h, where = own.get(doi), 'this review\'s search exports'
        if not h and r['via'].startswith('supplementary search (R-S1)'):
            h, where = supp.get(doi), 'the export of the supplementary search R-S1'
        if not h:
            h, where = earlier.get(doi), 'exports of the earlier systematic search'
        role = 'included study (' + r['kind'] + ')'
        if h:
            src, a, title, venue, vol, iss, pg, year, d = h
            refs[cid] = {'role': role, 'corpus_id': cid, 'doi': r['doi'], 'year': year, 'source_record': f'{src}, {where}',
                         'first_author_surname': (a[0].split()[-1] if a else ''), 'ieee': R0.ieee(a, title, venue, vol, iss, pg, year, d.lower())}
            if not a:
                problems.append(f'{cid}: no authors in the record')
        elif cid in K:
            au, meta = from_record(cid, cid)
            k = K[cid]
            refs[cid] = {'role': role, 'corpus_id': cid, 'doi': r['doi'], 'year': k['year'],
                         'source_record': 'OTHER-METHODS-2026-10-04.csv (venue) and the PDF metadata (authors)',
                         'first_author_surname': au.split(',')[0].split()[-1] if au else '',
                         'ieee': f"{au}, “{k['title'].rstrip('.')},” {k['venue']}" + (f", doi: {k['doi'].lower()}." if k['doi'] else '.')}
            problems.append(f'{cid}: entry from the review record and PDF metadata — check authors and venue')
        else:
            problems.append(f'{cid}: DOI {doi} not found')
    for k, v in R0.FOUNDATIONS.items():
        refs[k] = {'role': 'foundation', **v}
    # the reference corrections of the claims audits ("ref" actions of search-ppml/evidence/claims-audit-V*/DECISIONS-V*.json, applied
    # by apply_audit.py), replayed in version order so that rebuilding the list keeps them
    for f in sorted(glob.glob(str(ROOT / 'search-ppml' / 'evidence' / 'claims-audit-V*' / 'DECISIONS-V*.json')),
                    key=lambda f: int(re.search(r'DECISIONS-V(\d+)', f).group(1))):
        j = json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
        for d in (j if isinstance(j, list) else j.get('decisions') or j.get('actions') or []):
            if isinstance(d, dict) and d.get('action') == 'ref' and d.get('key') in refs:
                refs[d['key']][d['field']] = d['new']
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(refs, indent=1, ensure_ascii=False), encoding='utf-8')
    print(len(refs), 'references ->', OUT.relative_to(ROOT))
    for p in problems:
        print('  -', p)


if __name__ == '__main__':
    main()
