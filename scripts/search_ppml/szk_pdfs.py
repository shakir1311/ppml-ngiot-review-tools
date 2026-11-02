#!/usr/bin/env python3
"""Which S-ZK candidates already have a PDF in the workspace or in the author's download folder.

Matches by DOI and by normalised title only, from records and file names: the corpus index
(search-ppml/CORPUS-INDEX-2026-10-04.csv), the corpus id that the record ledger of 2 October gives a record, the names of
the PDFs and paper folders under corpus/, search/ and search-ppml/ (titles, and the record numbers of 2 October under which
that review filed its PDFs), and the names of the PDFs in /Volumes/Stuff/Downloads.
No PDF is opened.

Output (never overwritten): search-ppml/evidence/szk-search/SZK-PDFS-<date>.csv, one row per candidate: the S-ZK number,
the title, the DOI, how the review of 2 October had classified it, and where a PDF was found (or nothing).

Usage: python3 scripts/search_ppml/szk_pdfs.py <date>
"""
import csv
import pathlib
import re
import sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'search-ppml' / 'evidence' / 'szk-search'
INDEX = ROOT / 'search-ppml' / 'CORPUS-INDEX-2026-10-04.csv'
LEDGER = ROOT / 'search' / 'RECORD-LEDGER-2026-10-02-X5.csv'
DOWNLOADS = pathlib.Path('/Volumes/Stuff/Downloads')
flat = lambda t: re.sub(r'[^a-z0-9]', '', (t or '').lower())
low = lambda d: (d or '').strip().lower()


def name_title(path):
    """the title a paper's file or folder name carries: '2023 - Title (Author).pdf' -> 'Title'"""
    stem = re.sub(r'\.pdf$', '', path.name, flags=re.I)
    stem = re.sub(r'^\d{4}\s*-\s*', '', stem)
    return re.sub(r'\s*\([^)]*\)\s*$', '', stem)


def workspace_pdfs():
    """normalised title (from file and folder names) -> path, and record number of 2 October (files and folders named
    n0606 and so on, as the review of 2 October filed them) -> path, for every PDF under the paper folders"""
    found, by_n = {}, {}
    for top in ('corpus', 'search', 'search-ppml'):
        for p in (ROOT / top).rglob('*.pdf'):
            for t in (name_title(p), name_title(p.parent)):
                if len(flat(t)) >= 25:
                    found.setdefault(flat(t), str(p.relative_to(ROOT)))
                m = re.fullmatch(r'n(\d{4})(?:-published)?', t)
                if m:
                    by_n.setdefault(str(int(m.group(1))), str(p.relative_to(ROOT)))
    return found, by_n


def main(date):
    out = OUT / f'SZK-PDFS-{date}.csv'
    if out.exists():
        sys.exit(f'{out.name} exists; never overwritten')
    cand = list(csv.DictReader(open(sorted(OUT.glob('SZK-RECORDS-*.csv'))[-1], encoding='utf-8')))
    index = list(csv.DictReader(open(INDEX, encoding='utf-8')))
    by_doi = {low(r['doi']): r for r in index if r['doi']}
    by_doi.update({low(r['doi_alias']): r for r in index if r.get('doi_alias')})
    by_title = {flat(r['title']): r for r in index if r['title']}
    by_id = {r['id']: r for r in index}
    ledger = {r['n']: r for r in csv.DictReader(open(LEDGER, encoding='utf-8'))}
    files, by_n = workspace_pdfs()
    downloads = {flat(name_title(p)): p.name for p in DOWNLOADS.glob('*.pdf')} if DOWNLOADS.exists() else {}
    rows = []
    for c in cand:
        led = ledger.get(c['n_2oct'], {})
        hit, where = None, ''
        for how, r in (('corpus id of 2 October', by_id.get(led.get('corpus_id', ''))), ('DOI', by_doi.get(low(c['doi']))),
                       ('title', by_title.get(flat(c['title'])))):
            if r and r.get('pdf'):
                hit, where = r, f"corpus {r['id']} ({how}): {r['pdf']}"
                break
        if not hit and c['n_2oct'] in by_n:
            where = f"workspace (record number of 2 October): {by_n[c['n_2oct']]}"
        if not where and flat(c['title']) in files:
            where = f"workspace (file name): {files[flat(c['title'])]}"
        if not where and flat(c['title']) in downloads:
            where = f"Downloads (file name): {downloads[flat(c['title'])]}"
        rows.append({'n': c['n'], 'title': c['title'], 'year': c['year'], 'doi': c['doi'],
                     'status_2oct': led.get('status', ''), 'pdf': where})
    with open(out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    have = [r for r in rows if r['pdf']]
    print(f'{len(have)} of {len(rows)} candidates have a PDF '
          f"(corpus {sum(r['pdf'].startswith('corpus') for r in have)}, other workspace folders "
          f"{sum(r['pdf'].startswith('workspace') for r in have)}, Downloads {sum(r['pdf'].startswith('Downloads') for r in have)}) "
          f'-> {out.relative_to(ROOT)}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
