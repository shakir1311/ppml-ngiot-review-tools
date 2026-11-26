#!/usr/bin/env python3
"""The response document of a review round: every point the supervisory committee made, the decision and the action taken, and the
before and after of every revised paragraph of the paper, section by section, with the changed words marked (the author, 26 November
2026: "keep a tracking file where you track each and every section and the changes required for that section and also keep a before
and after version of every revised section, sentence, paragraph").

Reads myliteraturereviewpaper/ppml2026/review-v<n>/RESPONSE.json (the points, written by hand: id, source, where, request, decision,
action, status) and the builds build/paper-V<prev>.md and build/paper-V<n>.md. Paragraphs are paired within each top-level section
by text similarity; a pair with any difference is shown before/after with deletions struck through and insertions underlined; a
paragraph with no partner is shown as removed or new. Tables are compared by their caption and header row; figures by their caption.
Writes Docs/SUPERVISOR-REVIEW-RESPONSE-V<n>-<date>.html, printable in portrait and landscape.

Usage: python3 scripts/paper_ppml/review_response.py <version>
"""
import datetime, difflib, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
BUILD = P / 'build'


def plain(s):
    """a paragraph of the build as a reader sees it: markers out, citation keys as [key], emphasis marks out"""
    s = re.sub(r'⟦[^⟧]*⟧', '', s)
    s = re.sub(r'\[@(\w+)\]', r'[\1]', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
    s = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'\1', s)
    return re.sub(r'\s+', ' ', s).strip()


def sections(md):
    """[(heading, [(kind, text)])] per top-level section; kinds: para, table (caption + header), figure (caption), takeaways"""
    out, head, items = [], 'Front', []
    lines = md.splitlines(); i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('# '):
            out.append((head, items)); head, items = ln[2:].strip(), []; i += 1; continue
        if ln.startswith('## '):
            items.append(('heading', ln[3:].strip())); i += 1; continue
        if ln.startswith('```{=openxml}'):
            j = i + 1
            while j < len(lines) and not lines[j].startswith('```'): j += 1
            texts = [html.unescape(t) for t in re.findall(r'<w:t(?: [^>]*)?>([^<]*)</w:t>', '\n'.join(lines[i + 1:j]))]
            texts = [t for t in texts if t.strip() not in ('', '•', 'Key Takeaways')]
            if texts: items.append(('takeaways', ' • '.join(texts)))
            i = j + 1; continue
        if ln.startswith('Table: '):
            cap = ln[7:].strip(); j = i + 1
            while j < len(lines) and not lines[j].strip(): j += 1
            header = lines[j].strip() if j < len(lines) and lines[j].startswith('|') else ''
            items.append(('table', cap + ' — columns: ' + ' | '.join(c.strip() for c in header.strip('|').split('|')) if header else cap))
            i = j + 1
            while i < len(lines) and (lines[i].startswith('|') or not lines[i].strip()): i += 1
            continue
        m = re.match(r'^!\[(.*)\]\(.*\)', ln)
        if m:
            items.append(('figure', m.group(1).strip())); i += 1; continue
        if ln.startswith('|') or ln.startswith('---') or ln.startswith('title:') or ln.startswith('author:'):
            i += 1; continue
        if ln.strip():
            buf = [ln]; i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(('#', '```', 'Table: ', '![', '|', '- ', '1. ', '2. ', '3. ', '4. ', '5. ')):
                buf.append(lines[i]); i += 1
            items.append(('para', ' '.join(buf)))
            continue
        i += 1
    out.append((head, items))
    return out


def word_diff(a, b):
    """a and b with deletions struck through and insertions underlined, word by word"""
    wa, wb = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, wa, wb)
    before, after = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            before.append(html.escape(' '.join(wa[i1:i2]))); after.append(html.escape(' '.join(wb[j1:j2])))
        else:
            if i2 > i1: before.append('<del>' + html.escape(' '.join(wa[i1:i2])) + '</del>')
            if j2 > j1: after.append('<ins>' + html.escape(' '.join(wb[j1:j2])) + '</ins>')
    return ' '.join(before), ' '.join(after)


def pair(old_items, new_items):
    """pairs of (old, new) by best similarity within a section, in the order of the new text; unpaired old items follow as removed"""
    old = [(k, plain(t)) for k, t in old_items if k != 'heading']
    new = [(k, plain(t)) for k, t in new_items if k != 'heading']
    used, pairs = set(), []
    for nk, nt in new:
        best, br = None, 0.0
        for j, (ok, ot) in enumerate(old):
            if j in used or ok != nk: continue
            r = difflib.SequenceMatcher(None, ot, nt).ratio()
            if r > br: best, br = j, r
        if best is not None and br >= 0.3:
            used.add(best); pairs.append((nk, old[best][1], nt, br))
        else:
            pairs.append((nk, None, nt, 0.0))
    for j, (ok, ot) in enumerate(old):
        if j not in used: pairs.append((ok, ot, None, 0.0))
    return pairs


CSS = '''
body{font-family:Georgia,"Times New Roman",serif;color:#111;background:#fff;margin:0 auto;max-width:1100px;padding:24px;line-height:1.45}
h1{font-size:1.6em;margin:0 0 4px}h2{font-size:1.25em;margin:28px 0 8px;border-bottom:1px solid #999;padding-bottom:3px}
h3{font-size:1.05em;margin:18px 0 6px}.meta{color:#444;margin-bottom:16px}
table{border-collapse:collapse;width:100%;margin:10px 0 18px;font-size:0.92em}th,td{border:1px solid #bbb;padding:6px 8px;vertical-align:top;text-align:left}
th{background:#eee}.pt td:first-child{white-space:nowrap;font-weight:bold}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:8px 0 14px;break-inside:avoid}
.pair>div{border:1px solid #ccc;padding:8px 10px;font-size:0.92em}.pair .lab{font-weight:bold;color:#444;font-size:0.85em;margin-bottom:4px}
del{color:#a00;text-decoration:line-through}ins{color:#060;text-decoration:underline}
.kind{font-size:0.8em;color:#555;text-transform:uppercase;letter-spacing:.04em}.unchanged{color:#666;font-style:italic}
@media print{@page{size:auto;margin:15mm}body{max-width:none;padding:0}.pair{grid-template-columns:1fr 1fr}table,.pair,h2,h3{break-inside:avoid}a{color:#111;text-decoration:none}}
@media (max-width:700px){.pair{grid-template-columns:1fr}}
'''


def main(version):
    cfg = json.loads((P / f'review-v{version}' / 'RESPONSE.json').read_text(encoding='utf-8'))
    prev = cfg['previous']
    old, new = sections((BUILD / f'paper-V{prev}.md').read_text(encoding='utf-8')), sections((BUILD / f'paper-V{version}.md').read_text(encoding='utf-8'))
    srcs = {s['id']: s['label'] for s in cfg['sources']}
    h = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(cfg["title"])} (V{version})</title><style>{CSS}</style></head><body>']
    h.append(f'<h1>{html.escape(cfg["title"])}</h1><div class="meta">Version V{version} against V{prev} · {cfg["date"]} · every point of the committee, the decision and the action, then the before and after of every revised paragraph, section by section (deletions struck through, insertions underlined).</div>')
    h.append('<h2>1. The review inputs</h2><ul>' + ''.join(f'<li>{html.escape(l)}</li>' for l in srcs.values()) + '</ul>')
    h.append('<h2>2. Every point, with the decision and the action</h2><table class="pt"><tr><th>Point</th><th>Source</th><th>Where</th><th>What was asked</th><th>Decision</th><th>Action in V' + str(version) + '</th><th>Status</th></tr>')
    for p in cfg['points']:
        h.append('<tr>' + ''.join(f'<td>{html.escape(str(p[k]))}</td>' for k in ('id', 'source', 'where', 'request', 'decision', 'action', 'status')) + '</tr>')
    h.append('</table>')
    h.append('<h2>3. Before and after, section by section</h2>')
    n_changed = n_new = n_removed = n_same = 0
    old_map = {head: items for head, items in old}
    for head, items in new:
        pairs = pair(old_map.get(head, []), items)
        rows = []
        for kind, a, b, r in pairs:
            if a is not None and b is not None and a == b:
                n_same += 1; continue
            if a is None:
                n_new += 1; rows.append(f'<div class="pair"><div><div class="lab">V{prev}</div><span class="unchanged">(no paragraph of this kind here)</span></div><div><div class="lab">V{version} · new</div><span class="kind">{kind}</span><br>{html.escape(b)}</div></div>')
            elif b is None:
                n_removed += 1; rows.append(f'<div class="pair"><div><div class="lab">V{prev} · removed</div><span class="kind">{kind}</span><br>{html.escape(a)}</div><div><div class="lab">V{version}</div><span class="unchanged">(removed)</span></div></div>')
            else:
                n_changed += 1; da, db = word_diff(a, b)
                rows.append(f'<div class="pair"><div><div class="lab">V{prev}</div><span class="kind">{kind}</span><br>{da}</div><div><div class="lab">V{version}</div><span class="kind">{kind}</span><br>{db}</div></div>')
        if rows:
            h.append(f'<h3>{html.escape(head)}</h3>' + ''.join(rows))
    for head, items in old:
        if head not in {hh for hh, _ in new}:
            h.append(f'<h3>{html.escape(head)} (section removed)</h3>')
    h.append(f'<p class="meta">{n_changed} paragraphs, captions or table heads revised, {n_new} new, {n_removed} removed, {n_same} unchanged.</p></body></html>')
    out = ROOT / 'Docs' / f'SUPERVISOR-REVIEW-RESPONSE-V{version}-{cfg["date"]}.html'
    n = 2
    while out.exists():
        out = ROOT / 'Docs' / f'SUPERVISOR-REVIEW-RESPONSE-V{version}-V{n}-{cfg["date"]}.html'; n += 1
    out.write_text('\n'.join(h), encoding='utf-8')
    print(f'{out.relative_to(ROOT)}: {len(cfg["points"])} points; {n_changed} revised, {n_new} new, {n_removed} removed, {n_same} unchanged paragraphs')


if __name__ == '__main__':
    main(int(sys.argv[1]))
