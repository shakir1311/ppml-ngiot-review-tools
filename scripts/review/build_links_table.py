#!/usr/bin/env python3
"""Build the table of links between the primary studies and earlier work, from each paper's notes/LINKS.json.

Writes Docs/LINKS-TABLE-<date>.html (printable in portrait and landscape) and Docs/LINKS-TABLE-<date>.csv. An existing
file is never overwritten: the next free -V2, -V3 … name is used.

Usage: scripts/.venv/bin/python scripts/review/build_links_table.py [DATE]      (default: today)
"""
import csv, datetime, html, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
import ref_links as RL          # noqa: E402
import check_links as CL        # noqa: E402

ROOT = RL.ROOT
DOCS = ROOT / 'Docs'
REFS = json.loads((ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'references.json').read_text())['refs']
TYPE_LABEL = {'builds_on': 'builds on', 'measured_against': 'measured against',
              'compared_not_measured': 'compared, not measured', 'critique': 'critique',
              'positions_against': 'positions against'}
TYPE_ORDER = list(TYPE_LABEL)


def free_path(stem, ext):
    p = DOCS / f'{stem}.{ext}'
    k = 2
    while p.exists():
        p = DOCS / f'{stem}-V{k}.{ext}'
        k += 1
    return p


def cite(pid, titles):
    r = REFS.get(pid)
    if r:
        return r['cite']
    t = titles.get(pid, {})
    return f"{t.get('first_author', pid)} et al., {t.get('year', '')}"


def pages_of(link):
    pages = dict.fromkeys(e.get('page', '') for e in link.get('evidence', []))
    return ', '.join(sorted(pages, key=lambda s: int(s[1:]) if s[1:].isdigit() else 0))


def result_of(link):
    if link['type'] in ('measured_against', 'compared_not_measured'):
        bits = [link.get('metric', ''), link.get('result', '')]
        return ': '.join(b for b in bits if b)
    return ''


def setting_of(link):
    if link['type'] == 'measured_against':
        return 'yes — ' + link.get('setting', '')
    if link['type'] == 'compared_not_measured':
        return 'no — ' + link.get('setting', '')
    return ''


def load():
    by = RL.manifest()
    titles = RL.corpus_titles()
    rows, papers = [], {}
    for pid in CL.primary_ids():
        f = RL.CORPUS / by[pid]['folder'] / 'notes' / 'LINKS.json'
        if not f.exists():
            papers[pid] = None
            continue
        d = json.loads(f.read_text(encoding='utf-8'))
        papers[pid] = d
        for l in d['links']:
            rows.append(dict(l, frm=pid))
    return by, titles, rows, papers


def esc(s):
    return html.escape(str(s or ''))


CSS = """
:root { --ink:#1d2327; --muted:#5c6770; --line:#d5dbe0; --head:#eef3f7; --accent:#1f5f8b; --bg:#ffffff;
        --yes:#e7f4ea; --no:#fdf1e3; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --ink:#e6eaee; --muted:#a3adb6; --line:#39424a;
        --head:#232b32; --accent:#7fb6e0; --bg:#15191d; --yes:#1f3326; --no:#3a2d1c; } }
:root[data-theme="dark"] { --ink:#e6eaee; --muted:#a3adb6; --line:#39424a; --head:#232b32; --accent:#7fb6e0;
        --bg:#15191d; --yes:#1f3326; --no:#3a2d1c; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 Georgia, 'Times New Roman', serif; }
main { max-width: 1180px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 1.6rem; margin: 0 0 .3rem; } h2 { font-size: 1.25rem; margin: 2.2rem 0 .6rem; color: var(--accent); }
h3 { font-size: 1.02rem; margin: 1.4rem 0 .4rem; }
p.lede, .note { color: var(--muted); } .note { font-size: .88rem; }
.wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .86rem; margin: .3rem 0 .8rem; table-layout: fixed; }
td { overflow-wrap: anywhere; }
th, td { border: 1px solid var(--line); padding: 5px 7px; vertical-align: top; text-align: left; }
th { background: var(--head); font-weight: bold; }
tr.yes td.st { background: var(--yes); } tr.no td.st { background: var(--no); }
dl.types { display: grid; grid-template-columns: max-content 1fr; gap: 2px 14px; font-size: .92rem; }
dl.types dt { font-weight: bold; } dl.types dd { margin: 0; }
.counts { display: flex; flex-wrap: wrap; gap: 10px; margin: .8rem 0; }
.counts div { border: 1px solid var(--line); border-radius: 6px; padding: 6px 12px; }
.counts b { font-size: 1.15rem; display: block; }
@media print {
  @page { size: auto; margin: 14mm 12mm; }
  :root { --ink:#000; --muted:#333; --line:#999; --head:#eee; --accent:#000; --bg:#fff; --yes:#fff; --no:#fff; }
  body { font-size: 10.5pt; background: #fff; color: #000; }
  main { max-width: none; padding: 0; }
  .wrap { overflow: visible; }
  table { font-size: 8.5pt; width: 100%; }
  tr, .counts, dl.types, .callout { break-inside: avoid; }
  thead { display: table-header-group; }
  h2, h3 { break-after: avoid; }
}
@media (max-width: 640px) { dl.types { grid-template-columns: 1fr; } }
"""


WIDTHS = {'Later study': 14, 'Earlier work': 14, 'Link': 10, 'What the later study says': 34, 'What the study says': 34,
          'Metric and result': 22, 'Same setting?': 13, 'Pages': 7}          # per cent of the page width


def table(rows, cols):
    widths = ''.join(f'<col style="width:{WIDTHS.get(c, 10)}%">' for c, _ in cols)
    head = ''.join(f'<th>{esc(c)}</th>' for c, _ in cols)
    body = []
    for r in rows:
        cls = 'yes' if r.get('type') == 'measured_against' else ('no' if r.get('type') == 'compared_not_measured' else '')
        cells = ''.join(f'<td class="{_cls(c)}">{esc(fn(r))}</td>' for c, fn in cols)
        body.append(f'<tr class="{cls}">{cells}</tr>')
    return (f'<div class="wrap"><table><colgroup>{widths}</colgroup><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def _cls(col):
    return {'Pages': 'pg', 'Same setting?': 'st'}.get(col, '')


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    by, titles, rows, papers = load()
    done = [p for p, d in papers.items() if d is not None]
    missing = [p for p, d in papers.items() if d is None]
    name = lambda pid: f"{cite(pid, titles)} ({pid})"
    to_label = lambda r: name(r['to']) if r.get('to') else f"{r.get('to_name', '')} (outside the corpus)"
    by_type = {t: sum(r['type'] == t for r in rows) for t in TYPE_ORDER}
    corpus_links = [r for r in rows if r.get('to')]
    no_measured = [p for p in done if not any(l['type'] == 'measured_against' for l in papers[p]['links'])]

    out = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
           f'<title>Links Between Studies</title><style>{CSS}</style></head><body><main>',
           '<h1>Links between the primary studies and earlier work</h1>',
           f'<p class="lede">What each of the {len(done)} primary studies of the review says about earlier work: whom it builds '
           'on, whom it measures itself against and with what result, whom it compares itself with without measuring, whom '
           f'it criticises, and from whom it sets itself apart. Built {esc(date)} from the notes/LINKS.json of each study; '
           'every entry gives the pages of the study where the information stands.</p>',
           '<div class="counts">',
           f'<div><b>{len(rows)}</b>links</div>', f'<div><b>{len(corpus_links)}</b>to corpus papers</div>',
           f'<div><b>{by_type["measured_against"]}</b>measured in the same setting</div>',
           f'<div><b>{by_type["compared_not_measured"]}</b>compared, not measured</div>',
           f'<div><b>{by_type["critique"]}</b>critiques</div>', f'<div><b>{by_type["builds_on"]}</b>builds on</div>',
           f'<div><b>{by_type["positions_against"]}</b>positions against</div>',
           f'<div><b>{len(no_measured)}</b>studies with no measured comparison</div></div>',
           '<h2>How to read it</h2><dl class="types">',
           '<dt>builds on</dt><dd>the study adopts or extends the earlier work\'s method, definition, threat model or setup.</dd>',
           '<dt>measured against</dt><dd>the study\'s own experiments ran the earlier scheme or baseline in the same setting: '
           'a difference can be stated, as the study reports it.</dd>',
           '<dt>compared, not measured</dt><dd>asymptotic costs, figures taken from the other paper, or a comparison made '
           'in words only: the results can only be set side by side, each with its setting.</dd>',
           '<dt>critique</dt><dd>the study states a limitation or cost of the earlier work (its claim, not the review\'s).</dd>',
           '<dt>positions against</dt><dd>the study says how it differs from the earlier work, without judging it.</dd></dl>',
           '<p class="note">Every entry records what the study says in its own words, quoted with its page; values are '
           'not read from tables or figures, and the statements are not checked against the studies\' data. Works outside '
           'the corpus appear only as measured baselines. Plain citations are not listed as links; they are named under '
           'each study as “also cited”. Pages refer to the page of the study\'s PDF.</p>']

    # view 1: by earlier work
    out.append('<h2>By earlier work: what later studies say about each corpus paper</h2>')
    targets = sorted({r['to'] for r in corpus_links}, key=lambda i: cite(i, titles))
    for t in targets:
        rs = sorted([r for r in corpus_links if r['to'] == t], key=lambda r: (TYPE_ORDER.index(r['type']), r['frm']))
        out.append(f'<h3>{esc(name(t))} — {esc(titles[t]["title"])}</h3>')
        out.append(table(rs, [('Later study', lambda r: name(r['frm'])), ('Link', lambda r: TYPE_LABEL[r['type']]),
                              ('What the later study says', lambda r: r.get('says', '')),
                              ('Metric and result', result_of), ('Same setting?', setting_of), ('Pages', pages_of)]))

    # view 2: by citing study
    out.append('<h2>By study: the links each primary study records</h2>')
    for p in sorted(done, key=lambda i: cite(i, titles)):
        d = papers[p]
        out.append(f'<h3>{esc(name(p))} — {esc(titles[p]["title"])}</h3>')
        if d['links']:
            rs = sorted(d['links'], key=lambda r: (TYPE_ORDER.index(r['type']), r.get('to') or 'zz'))
            out.append(table(rs, [('Earlier work', to_label), ('Link', lambda r: TYPE_LABEL[r['type']]),
                                  ('What the study says', lambda r: r.get('says', '')),
                                  ('Metric and result', result_of), ('Same setting?', setting_of), ('Pages', pages_of)]))
        else:
            out.append('<p class="note">No links recorded.</p>')
        extra = []
        if d.get('cited_only'):
            extra.append('Also cited: ' + '; '.join(name(c) for c in d['cited_only']) + '.')
        if p in no_measured:
            extra.append('No measured comparison with another scheme or baseline.')
        if extra:
            out.append(f'<p class="note">{esc(" ".join(extra))}</p>')
    if missing:
        out.append(f'<p class="note">No link record yet: {esc(", ".join(missing))}.</p>')
    out.append('</main></body></html>')

    DOCS.mkdir(exist_ok=True)
    stem = f'LINKS-TABLE-{date}'
    hp, cp = free_path(stem, 'html'), free_path(stem, 'csv')
    hp.write_text('\n'.join(out), encoding='utf-8')
    with cp.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['from_id', 'from', 'to_id', 'to', 'in_corpus', 'ref', 'link', 'says', 'metric', 'result',
                    'same_setting', 'setting', 'pages', 'quotations'])
        for r in sorted(rows, key=lambda r: (r['frm'], TYPE_ORDER.index(r['type']))):
            quotes = ' | '.join(f"[{e.get('page')}] {e.get('quote') or e.get('what', '')}" for e in r.get('evidence', []))
            w.writerow([r['frm'], cite(r['frm'], titles), r.get('to') or '', to_label(r), 'yes' if r.get('to') else 'no',
                        r.get('ref') or '', TYPE_LABEL[r['type']], r.get('says', ''), r.get('metric', ''),
                        r.get('result', ''), {True: 'yes', False: 'no'}.get(r.get('same_setting'), ''),
                        r.get('setting', ''), pages_of(r), quotes])
    rel = lambda q: q.relative_to(ROOT) if q.is_relative_to(ROOT) else q
    print(f'{rel(hp)}\n{rel(cp)}\n{len(done)} studies, {len(rows)} links, missing: {missing}')


if __name__ == '__main__':
    main()
