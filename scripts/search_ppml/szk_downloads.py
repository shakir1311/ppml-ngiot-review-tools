#!/usr/bin/env python3
"""The full texts to download for the S-ZK records the author included at title and abstract.

Reads the author's decisions (search-ppml/evidence/szk-search/AUTHOR-DECISIONS-S-ZK.csv), the records, the PDFs already on file
(SZK-PDFS-<date>.csv, szk_pdfs.py) and the open-access status OpenAlex gives each DOI (claude/OPENALEX-OA-INCLUDED-<date>.json),
and writes a printable list in Docs/, grouped by publisher, with a DOI link for every report and the open copy where OpenAlex
names one. Nothing is downloaded. An existing list is never overwritten.

Usage: python3 scripts/search_ppml/szk_downloads.py <date>
"""
import csv
import html
import json
import pathlib
import sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
SZK = ROOT / 'search-ppml' / 'evidence' / 'szk-search'
PUBLISHER = {'10.1109': 'IEEE', '10.1016': 'Elsevier', '10.1007': 'Springer Nature', '10.1038': 'Springer Nature',
             '10.3390': 'MDPI', '10.1002': 'Wiley', '10.1142': 'World Scientific', '10.1117': 'SPIE', '10.1145': 'ACM',
             '10.23919': 'IEEE', '10.54216': 'American Scientific Publishing Group', '10.22247': 'EverScience Publications'}
e = lambda s: html.escape(str(s or ''))


def publisher(doi, oa):
    return PUBLISHER.get(doi.split('/')[0], oa.get('publisher') or 'Other publishers')


def main(date):
    out = ROOT / 'Docs' / f'PPML-S-ZK-DOWNLOADS-{date}.html'
    if out.exists():
        sys.exit(f'{out.name} exists; never overwritten')
    dec = {r['n']: r for r in csv.DictReader(open(SZK / 'AUTHOR-DECISIONS-S-ZK.csv', encoding='utf-8'))}
    rec = {r['n']: r for r in csv.DictReader(open(sorted(SZK.glob('SZK-RECORDS-*.csv'))[-1], encoding='utf-8'))}
    pdfs = {r['n']: r['pdf'] for r in csv.DictReader(open(sorted(SZK.glob('SZK-PDFS-*.csv'))[-1], encoding='utf-8'))}
    oa = json.loads((SZK / 'claude' / f'OPENALEX-OA-INCLUDED-{date}.json').read_text(encoding='utf-8'))['works']
    inc = sorted(n for n, d in dec.items() if d['decision'] == 'INCLUDE')
    held = [n for n in inc if pdfs.get(n)]
    want = [n for n in inc if not pdfs.get(n)]
    groups = {}
    for n in want:
        groups.setdefault(publisher(rec[n]['doi'], oa.get(n, {})), []).append(n)
    order = sorted(groups, key=lambda g: (-len(groups[g]), g))
    rows = []
    for g in order:
        rows.append(f'<h2>{e(g)} <span class="count">({len(groups[g])})</span></h2><table><thead><tr><th>No.</th><th>Title</th>'
                    '<th>Year</th><th>Venue</th><th>Link</th><th>Open copy</th></tr></thead><tbody>')
        for n in sorted(groups[g], key=lambda n: (rec[n]['year'], n)):
            r, o = rec[n], oa.get(n, {})
            doi = r['doi'].strip()
            link = f'<a href="https://doi.org/{e(doi)}">doi.org/{e(doi)}</a>'
            free = ''
            if o.get('is_oa'):
                url = o.get('pdf_url') or o.get('landing')
                kind = 'published version' if o.get('version') == 'publishedVersion' else (o.get('version') or 'version not stated')
                free = f'<a href="{e(url)}">open ({e(kind)})</a>' if url else f'open ({e(kind)})'
            rows.append(f'<tr><td>{e(n)}</td><td>{e(r["title"])}</td><td>{e(r["year"])}</td><td>{e(r["venue"])}</td>'
                        f'<td class="link">{link}</td><td>{free or "—"}</td></tr>')
        rows.append('</tbody></table>')
    n_oa = sum(1 for n in want if oa.get(n, {}).get('is_oa'))
    held_txt = '; '.join(f'{e(n)} {e(rec[n]["title"])} ({e(pdfs[n].split(":", 1)[-1].strip())})' for n in held)
    page = f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>S-ZK full texts to download</title>
<style>
:root {{ --ink: #1d1d1f; --muted: #5f6368; --rule: #d0d4da; --head: #eef1f5; --accent: #1f4e79; }}
body {{ font: 15px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: var(--ink); background: #fff;
       max-width: 1200px; margin: 0 auto; padding: 24px 16px 48px; }}
h1 {{ font-size: 1.5rem; margin: 0 0 4px; color: var(--accent); }}
h2 {{ font-size: 1.1rem; margin: 28px 0 8px; color: var(--accent); }}
.count {{ color: var(--muted); font-weight: normal; }}
p {{ margin: 8px 0; }}
.note {{ background: #f6f8fa; border-left: 4px solid var(--accent); padding: 10px 14px; margin: 14px 0; }}
.wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
th, td {{ border-bottom: 1px solid var(--rule); padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: var(--head); }}
td.link {{ word-break: break-all; }}
a {{ color: var(--accent); }}
@page {{ size: auto; margin: 14mm; }}
@media print {{
  body {{ max-width: none; padding: 0; font-size: 10.5pt; color: #000; background: #fff; }}
  .wrap {{ overflow-x: visible; }}
  table {{ width: 100%; font-size: 9pt; }}
  tr, .note {{ break-inside: avoid; }}
  thead {{ display: table-header-group; }}
  h2 {{ break-after: avoid; }}
  a {{ color: #000; text-decoration: none; }}
}}
</style></head><body>
<h1>S-ZK: full texts to download</h1>
<p>Supplementary search S-ZK, title-and-abstract screening of 644 records: <b>{len(inc)} included</b> ({sum(1 for n in inc if dec[n]['type'] == 'primary')}
primary studies, {sum(1 for n in inc if dec[n]['type'] == 'secondary')} surveys), {sum(1 for d in dec.values() if d['decision'] == 'EXCLUDE')} excluded.
Each included report needs its full text for the full-text decision.</p>
<div class="note"><b>Already on file ({len(held)}):</b> {held_txt or 'none'}.<br>
<b>To download ({len(want)}):</b> save each PDF into <code>/Volumes/Stuff/Downloads</code>, keeping the publisher's file name or the title.
{n_oa} of them are open access according to OpenAlex (the column "Open copy"); the others need your institutional access at the publisher.
Download the published version, not a preprint.</div>
<div class="wrap">{''.join(rows)}</div>
<p style="color:var(--muted); font-size:0.85rem">Sources: the author's decisions (<code>search-ppml/evidence/szk-search/AUTHOR-DECISIONS-S-ZK.csv</code>),
the records of the searches of 2 October 2026, and OpenAlex (open-access status, by DOI). Made by <code>scripts/search_ppml/szk_downloads.py</code>.</p>
</body></html>
"""
    out.write_text(page, encoding='utf-8')
    print(f'{out.relative_to(ROOT)}: {len(want)} to download ({n_oa} open access), {len(held)} on file; '
          + ', '.join(f'{g} {len(groups[g])}' for g in order))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
