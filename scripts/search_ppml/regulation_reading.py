#!/usr/bin/env python3
"""Reading file for the author's screening of a supplementary regulation search (8 October 2026).

Takes a Scopus export of strings_regulation.py (e.g. R-S1), drops the records the PPML review's search already returned
(search-ppml/MERGED-RECORDS-2026-10-04.csv, by DOI, else by title), and writes the rest for the author to read, in groups
sorted by cue words (a script, not a screening decision):
  A  federated or collaborative learning, a named privacy mechanism, and data-protection law in the title or abstract
  B  other records that name a privacy mechanism in the title or abstract
  C  surveys (document type Review, or a survey word in the title)
  D  the rest: data-protection terms with no privacy mechanism named (in some, the law appears only in Scopus's index keywords)
Records already in the corpus are marked.

Usage: python3 scripts/search_ppml/regulation_reading.py <export.csv> <out.md>
"""
import csv, datetime, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import strings_regulation as SR                                    # noqa: E402

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
MECH = re.compile(r'differential(ly)? privacy|homomorphic|multi-?party computation|\bSMPC\b|\bMPC\b|secure aggregation|secret[- ]sharing|'
                  r'zero[- ]knowledge|\bZKPs?\b|zk-?SNARK|trusted execution|\bTEE\b|\bSGX\b|functional encryption|privacy[- ]preserving|'
                  r'anonymi[sz]|pseudonym', re.I)
FL = re.compile(r'federated learning|split learning|swarm learning|distributed learning|collaborative learning', re.I)
norm = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())


def main(export, out):
    rows = list(csv.DictReader(open(export, encoding='utf-8-sig')))
    P = list(csv.DictReader(open(ROOT / 'search-ppml' / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8', errors='ignore')))
    pdoi = {r['doi'].lower() for r in P if r.get('doi')}
    ptit = {norm(r['title']) for r in P}
    ix = {r['doi'].lower(): r['id'] for r in csv.DictReader(open(ROOT / 'search-ppml' / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))
          if r.get('doi')}
    new = [r for r in rows if not (r['DOI'].lower() in pdoi or norm(r['Title']) in ptit)]
    ta = lambda r: r['Title'] + ' ' + r.get('Abstract', '')
    def group(r):
        if FL.search(ta(r)) and MECH.search(ta(r)) and SR.hit(SR.REG, ta(r)):
            return 'A'
        if MECH.search(ta(r)):
            return 'B'
        if r['Document Type'] == 'Review' or SR.hit(SR.SUR, r['Title']):
            return 'C'
        return 'D'
    names = {'A': 'Federated or collaborative learning, a privacy mechanism and data-protection law in the title or abstract',
             'B': 'A privacy mechanism named in the title or abstract', 'C': 'Surveys',
             'D': 'Data-protection terms, no privacy mechanism named'}
    G = {g: sorted([r for r in new if group(r) == g], key=lambda r: (-int(r['Year'] or 0), r['Title'])) for g in 'ABCD'}
    md = [f'# {pathlib.Path(export).name.split("-export")[0]}: records new to the PPML search, for screening\n\n',
          f'{datetime.date.today().isoformat()}. {len(rows)} records in the export; {len(rows) - len(new)} were already returned by the PPML '
          f'review\'s search; {len(new)} are new and listed here. The groups come from cue words (a script, not a screening decision): '
          + '; '.join(f'{g} {names[g].lower()} ({len(G[g])})' for g in 'ABCD') + '. The PPML review\'s criteria ask, for a primary study, its '
          'own privacy contribution, learning and an NG-IoT setting; for a survey, privacy treated and an NG-IoT focus.\n\n']
    n = 0
    for g in 'ABCD':
        md.append(f'## {g}. {names[g]} ({len(G[g])})\n\n')
        for r in G[g]:
            n += 1
            held = f' **In the corpus: {ix[r["DOI"].lower()]}.**' if r['DOI'].lower() in ix else ''
            law = 'data-protection law in the title or abstract' if SR.hit(SR.REG, ta(r)) else 'data-protection term only in the keywords'
            md.append(f'### {n}. {r["Title"]}\n\n{r["Year"]} · {r["Document Type"]} · {r["Source title"]} · DOI {r["DOI"] or "none"} · '
                      f'{r.get("Open Access", "") or "not open access"}{held}\n\n*Cues:* {law}; '
                      f'{"names a privacy mechanism" if MECH.search(ta(r)) else "no privacy mechanism named"}; '
                      f'{"federated or collaborative learning" if FL.search(ta(r)) else "other learning"}.\n\n'
                      f'{r.get("Abstract", "").strip()}\n\n*Keywords:* {r.get("Author Keywords", "")}\n\n')
    pathlib.Path(out).write_text(''.join(md), encoding='utf-8')
    print(f'{out}: {n} records (' + ', '.join(f'{g} {len(G[g])}' for g in 'ABCD') + ')')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
