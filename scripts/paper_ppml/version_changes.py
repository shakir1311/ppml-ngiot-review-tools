#!/usr/bin/env python3
"""A readable record of what changed in one or more versions of the paper: a summary per version, every table compared cell by
cell, every figure that changed shown before and after with its smallest printed text size, and every revised paragraph before
and after, section by section, with the changed words marked (the author, 26 November 2026: "give me an overview of v90 and v91 -
what have we changed. or better prepare a file where i can read the changes myself").

Reads the hand-written summary myliteraturereviewpaper/ppml2026/changes/CHANGES-V<first>-V<last>.json (title, intro, per version
the reason and the groups of changes, and what did not change), the built texts build/paper-V<n>.md of every version involved, and
the figures of each version from its release package (release/ppml-ngiot-review-tools-v<n>/…/build/figures/, the current build
for the latest). Figures are compared by their bytes and shown as reduced JPEG copies embedded in the page; the smallest text of
each is measured from its SVG at the printed width (two columns, about 7 in). Paragraph pairing and word marking come from
review_response.py. Writes Docs/PAPER-CHANGES-V<first>-V<last>-<date>.html (never over an existing file), printable in portrait and
landscape.

Usage: python3 scripts/paper_ppml/version_changes.py <first> <last>     e.g. 90 91 (each version against the one before it)
"""
import base64, difflib, hashlib, html, json, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
BUILD = P / 'build'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import review_response as RR                                              # noqa: E402  (sections, pair, word_diff, plain)


def figdir(v, latest):
    if v == latest:
        return BUILD / 'figures'
    return ROOT / 'release' / f'ppml-ngiot-review-tools-v{v}' / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / 'figures'


def placed_figures(md):
    """[(number, caption, file stem)] in order"""
    return [(int(n), cap.strip(), pathlib.Path(path).stem) for n, cap, path in re.findall(r'^!\[Fig\. (\d+)\. (.*?)\]\(([^)]+)\)', md, re.M)]


def tables(md):
    """{label: (caption, header, rows)} for every table of a build"""
    out, lines = {}, md.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r'^Table: (Table [IVXL]+)\. (.*)$', ln)
        if not m:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        rows = []
        while j < len(lines) and lines[j].startswith('|'):
            if not re.match(r'^\|[\s:|-]+\|$', lines[j].strip()):
                rows.append([c.strip() for c in lines[j].strip().strip('|').split('|')])
            j += 1
        out[m.group(1)] = (m.group(2).strip(), rows[0] if rows else [], rows[1:])
    return out


def smallest_pt(svg):
    if not svg.exists():
        return None
    s = svg.read_text(encoding='utf-8')
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', s)
    W = int(m.group(1)) if m else int(re.search(r'<svg[^>]*\bwidth="(\d+)', s).group(1))
    sizes = [float(x) for x in re.findall(r'font-size="?([\d.]+)', s)]
    return round(504 * min(sizes) / W, 1) if sizes else None


def thumb(png, tmp):
    """a reduced JPEG copy of a figure, as a data URI"""
    out = pathlib.Path(tmp) / (hashlib.sha1(str(png).encode()).hexdigest() + '.jpg')
    subprocess.run(['sips', '-Z', '1400', '-s', 'format', 'jpeg', '-s', 'formatOptions', '80', str(png), '--out', str(out)], check=True, capture_output=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(out.read_bytes()).decode()


CSS = RR.CSS + '''
.lead{font-size:1.02em}.why{background:#f4f6fa;border-left:4px solid #3c6fb0;padding:8px 12px;margin:8px 0 12px}
.toc a{color:#1d4f8f}.toc li{margin:2px 0}
.figpair{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:8px 0 18px;break-inside:avoid}
.figpair figure{margin:0;border:1px solid #ccc;padding:6px}.figpair img{width:100%;height:auto;display:block}
.figpair figcaption{font-size:0.85em;color:#333;margin-top:4px}
td.chg{background:#fff6d6}.small{font-size:0.86em}.ok{color:#2e6b2e}
@media print{.figpair{grid-template-columns:1fr 1fr}.figpair,figure,table{break-inside:avoid}}
@media (max-width:700px){.figpair{grid-template-columns:1fr}}
'''


def table_section(v, prev, old_md, new_md):
    """the tables of version v against prev: a status list, then every changed table in full (changed cells marked)"""
    ot, nt = tables(old_md), tables(new_md)
    h = ['<table class="small"><tr><th>Table</th><th>Caption in V' + str(v) + '</th><th>What changed</th></tr>']
    full = []
    for lab, (cap, head, rows) in nt.items():
        ocap, ohead, orows = ot.get(lab, ('', [], []))
        what = []
        if cap != ocap: what.append('caption reworded')
        if head != ohead: what.append('column headings')
        if len(rows) != len(orows): what.append(f'rows {len(orows)} → {len(rows)}')
        changed = sum(1 for a, b in zip(orows, rows) for x, y in zip(a, b) if x != y) + abs(len(rows) - len(orows)) * max(len(head), 1)
        if changed: what.append(f'{changed} cell(s)')
        h.append(f'<tr><td>{lab}</td><td>{html.escape(cap)}</td><td>{html.escape(", ".join(what)) if what else "<span class=ok>unchanged</span>"}</td></tr>')
        if head != ohead or (changed and len(rows) <= 20):
            def render(c, hd, rs, other):
                t = [f'<p class="small"><b>{lab}. {html.escape(c)}</b></p><table class="small"><tr>' + ''.join(f'<th>{html.escape(x)}</th>' for x in hd) + '</tr>']
                for i, r in enumerate(rs):
                    o = other[i] if i < len(other) else []
                    t.append('<tr>' + ''.join(f'<td class="{"chg" if j >= len(o) or o[j] != x else ""}">{html.escape(x)}</td>' for j, x in enumerate(r)) + '</tr>')
                return ''.join(t) + '</table>'
            full.append(f'<h4>{lab}: before (V{prev}) and after (V{v})</h4>' + render(ocap, ohead, orows, rows) + render(cap, head, rows, orows))
        elif changed:
            diffs = [(i, a, b) for i, (a, b) in enumerate(zip(orows, rows)) if a != b]
            full.append(f'<h4>{lab}: the {len(diffs)} changed row(s)</h4><table class="small"><tr><th>Row</th><th>V{prev}</th><th>V{v}</th></tr>' +
                        ''.join(f'<tr><td>{i + 1}</td><td>{html.escape(" | ".join(a))}</td><td>{html.escape(" | ".join(b))}</td></tr>' for i, a, b in diffs) + '</table>')
    h.append('</table>')
    return ''.join(h) + ''.join(full)


def figure_section(v, prev, old_md, new_md, latest, tmp):
    of, nf = {n: (c, s) for n, c, s in placed_figures(old_md)}, placed_figures(new_md)
    od, nd = figdir(prev, latest), figdir(v, latest)
    h = ['<table class="small"><tr><th>Figure</th><th>Caption in V' + str(v) + f'</th><th>Image</th><th>Smallest text V{prev} → V{v}</th></tr>']
    pairs = []
    for n, cap, stem in nf:
        ocap, ostem = of.get(n, ('', stem))
        a, b = od / f'{ostem}.png', nd / f'{stem}.png'
        same = a.exists() and b.exists() and a.read_bytes() == b.read_bytes()
        pa, pb = smallest_pt(od / f'{ostem}.svg'), smallest_pt(nd / f'{stem}.svg')
        cap_note = '' if cap == ocap else ' (caption reworded)'
        h.append(f'<tr><td>Fig. {n}</td><td>{html.escape(cap)}{cap_note}</td><td>{"<span class=ok>unchanged</span>" if same else "redrawn"}</td><td>{pa} pt → {pb} pt</td></tr>')
        if not same and a.exists() and b.exists():
            pairs.append(f'<h4>Fig. {n}</h4><div class="figpair"><figure><img src="{thumb(a, tmp)}" alt="Fig. {n}, V{prev}"><figcaption>V{prev}: smallest text {pa} pt at print width</figcaption></figure>'
                         f'<figure><img src="{thumb(b, tmp)}" alt="Fig. {n}, V{v}"><figcaption>V{v}: smallest text {pb} pt at print width</figcaption></figure></div>')
    h.append('</table>')
    return ''.join(h) + ''.join(pairs)


def paragraph_section(v, prev, old_md, new_md):
    old, new = RR.sections(old_md), RR.sections(new_md)
    old_map = {head: items for head, items in old}
    out, counts = [], {'revised': 0, 'new': 0, 'removed': 0, 'same': 0}
    for head, items in new:
        rows = []
        for kind, a, b, r in RR.pair(old_map.get(head, []), items):
            if kind == 'table' or kind == 'figure':
                continue                                           # tables and figures have their own sections above
            if a is not None and b is not None and a == b:
                counts['same'] += 1; continue
            if a is None:
                counts['new'] += 1
                rows.append(f'<div class="pair"><div><div class="lab">V{prev}</div><span class="unchanged">(nothing here)</span></div><div><div class="lab">V{v} · new</div><ins>{html.escape(b)}</ins></div></div>')
            elif b is None:
                counts['removed'] += 1
                rows.append(f'<div class="pair"><div><div class="lab">V{prev} · removed</div><del>{html.escape(a)}</del></div><div><div class="lab">V{v}</div><span class="unchanged">(removed)</span></div></div>')
            else:
                counts['revised'] += 1
                da, db = RR.word_diff(a, b)
                rows.append(f'<div class="pair"><div><div class="lab">V{prev}</div>{da}</div><div><div class="lab">V{v}</div>{db}</div></div>')
        if rows:
            out.append(f'<h4>{html.escape(head)}</h4>' + ''.join(rows))
    return ''.join(out), counts


def main(first, last):
    cfg = json.loads((P / 'changes' / f'CHANGES-V{first}-V{last}.json').read_text(encoding='utf-8'))
    md = {v: (BUILD / f'paper-V{v}.md').read_text(encoding='utf-8') for v in range(first - 1, last + 1)}
    h = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(cfg["title"])}</title><style>{CSS}</style></head><body>',
         f'<h1>{html.escape(cfg["title"])}</h1><div class="meta">{cfg["date"]} · versions V{first} to V{last}, each against the one before it</div>',
         f'<p class="lead">{html.escape(cfg["intro"])}</p>']
    toc = ['<h2>Contents</h2><ol class="toc">']
    for ver in cfg['versions']:
        toc.append(f'<li><a href="#v{ver["v"]}">V{ver["v"]} ({html.escape(ver["date"])}): summary, tables, figures, every revised paragraph</a></li>')
    toc.append('<li><a href="#unchanged">What did not change</a></li></ol>')
    h += toc
    body = []
    with tempfile.TemporaryDirectory() as tmp:
        for ver in cfg['versions']:
            v, prev = ver['v'], ver['prev']
            paras, counts = paragraph_section(v, prev, md[prev], md[v])
            body.append(f'<h2 id="v{v}">V{v} ({html.escape(ver["date"])}), against V{prev}</h2><div class="why">{html.escape(ver["why"])}</div>')
            body.append(f'<p class="small">In numbers: {counts["revised"]} paragraphs revised, {counts["new"]} new, {counts["removed"]} removed, {counts["same"]} unchanged (headings, tables and figures counted separately below).</p>')
            body.append(f'<h3>V{v} in brief</h3>')
            for g in ver['groups']:
                body.append(f'<p><b>{html.escape(g["title"])}</b></p><ul>' + ''.join(f'<li>{html.escape(x)}</li>' for x in g['items']) + '</ul>')
            body.append(f'<h3>V{v}: tables</h3>' + table_section(v, prev, md[prev], md[v]))
            body.append(f'<h3>V{v}: figures</h3>' + figure_section(v, prev, md[prev], md[v], last, tmp))
            body.append(f'<h3>V{v}: every revised paragraph, before and after</h3>' + (paras or '<p class="unchanged">No paragraph changed.</p>'))
    h += body
    h.append('<h2 id="unchanged">What did not change</h2><ul>' + ''.join(f'<li>{html.escape(x)}</li>' for x in cfg['unchanged']) + '</ul></body></html>')
    out = ROOT / 'Docs' / f'PAPER-CHANGES-V{first}-V{last}-{cfg["date"]}.html'
    n = 2
    while out.exists():
        out = ROOT / 'Docs' / f'PAPER-CHANGES-V{first}-V{last}-V{n}-{cfg["date"]}.html'; n += 1
    out.write_text('\n'.join(h), encoding='utf-8')
    print(f'{out.relative_to(ROOT)}: {out.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main(int(sys.argv[1]), int(sys.argv[2]))
