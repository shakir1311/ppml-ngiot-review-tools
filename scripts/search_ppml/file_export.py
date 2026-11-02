#!/usr/bin/env python3
"""File one export of the PPML searches: copy it unchanged and unrenamed into search-ppml/exports/<source>/, count its
records, and append its row (with SHA-256) to search-ppml/exports/PROVENANCE-2026-10-04.tsv. New rows go at the end so
that the record numbers of the merge stay as they are.

Usage: python3 scripts/search_ppml/file_export.py SEARCH SOURCE FILE ["results shown"] ["searched"]
       SOURCE is Scopus, "IEEE Xplore" or ScienceDirect; "results shown" is what the site showed, as the author reported it
"""
import csv, datetime, hashlib, pathlib, re, shutil, sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
EX = ROOT / 'search-ppml' / 'exports'
PROV = EX / 'PROVENANCE-2026-10-04.tsv'
DIRS = {'Scopus': 'scopus', 'IEEE Xplore': 'ieee', 'ScienceDirect': 'sciencedirect'}


def count(path, source):
    if source == 'ScienceDirect':
        return sum(1 for line in open(path, encoding='utf-8-sig', errors='replace') if line.startswith('ER  -'))
    return sum(1 for _ in csv.DictReader(open(path, encoding='utf-8-sig', errors='replace')))


def main():
    search, source, src = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
    shown = sys.argv[4] if len(sys.argv) > 4 else 'count shown not reported by the author'
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    rows = list(csv.DictReader(open(PROV, encoding='utf-8'), delimiter='\t'))
    if any(r['sha256'] == sha for r in rows):
        sys.exit(f'already filed: {src.name}')
    dest = EX / DIRS[source] / src.name
    shutil.copy2(src, dest)
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == sha
    m = re.search(r'T(\d\d)(\d\d)\d\d', src.name)
    searched = sys.argv[5] if len(sys.argv) > 5 else ('2026-10-04' + (f' (export {m.group(1)}:{m.group(2)} UTC)' if m else ''))
    n = count(dest, source)
    with open(PROV, 'a', encoding='utf-8', newline='') as fh:
        csv.writer(fh, delimiter='\t', lineterminator='\n').writerow(
            [search, source, src.name, sha, n, shown, 'the author', searched,
             datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')])
    print(f'{search}: {n} records, sha256 {sha[:16]}…, filed as {dest.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
