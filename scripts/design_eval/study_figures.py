#!/usr/bin/env python3
"""Crops from each of the 54 designs' papers its design figures and algorithm boxes, with their captions, for the author's document of the designs' own diagrams.

For every page of the paper's PDF, figure captions ("Fig. 3.", "Figure 3:", a bold "Fig. 3") and algorithm captions
("Algorithm 1") are found in the text layer. A figure is the artwork above (or below) its caption: the regions the extraction
pipeline recorded (metadata.json figure_inventory) between the previous caption of that column and this one, joined with the
caption itself; with no recorded region, the space above the caption, marked approximate. A figure is classed `design` when
its caption names an architecture, framework, model, workflow, protocol and the like and no result (accuracy, time, cost ...),
`result` when it names a result, `other` otherwise; when a paper has no `design` figure, its first figure is kept. An algorithm
box runs from its caption (or the rule just above it) to the next horizontal rule below the caption's own separator, in the
caption's column; a box with no closing rule on its page is cut at the column's end and the top of the next page is added,
up to its first rule. Crops go to design-evaluation/study/figures/<id>/ with index.json (kind, number, page, class, how it was
found, caption). Claude reads only the counts this prints, never the crops or the captions; the author checks the images.
The author's permission: CLAUDE.md, 26 November 2026.

Usage: python3 scripts/design_eval/study_figures.py [<id> ...]
"""
import json, pathlib, re, sys

import pymupdf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, load_designs, now, save_json   # noqa: E402
from study_packets import resolve   # noqa: E402

OUT = EVAL / 'study' / 'figures'
FIG = re.compile(r'^\s*(fig(?:ure)?)\s*\.?\s*(\d+)\s*([.:|—–-])?', re.I)
ALG = re.compile(r'^\s*(algorithm)\s*(\d+)\s*([.:|—–-])?', re.I)
DESIGN = re.compile(r'architect|framework|system model|overview|work ?flow|flow ?chart|process|scheme|structure|pipeline|design|'
                    r'protocol|interaction|procedure|sequence|layer|component|entit|life ?cycle|topology|consensus|mechanism|'
                    r'illustrat|diagram|steps|phase|model of|network model|threat model|proposed|overall|block ?chain|smart contract|'
                    r'circuit|zero.knowledge|aggregation process|training process|registration|interaction', re.I)
RESULT = re.compile(r'accura|loss|computation time|running time|execution time|time cost|time consumption|proving time|'
                    r'verification time|cost|latency|throughput|overhead|comparison|compared|performance|result|gas|memory|'
                    r'\bf1\b|precision|recall|\broc\b|\bauc\b|\brate\b|\bvs\.?\b|versus|impact|effect of|varying|number of|'
                    r'convergence|epoch|scalab|evaluation|consumption|confusion|distribution of|histogram|curve', re.I)
FIG_DPI, ALG_DPI, NEAR = 170, 160, 60


def is_bold(line):
    spans = line.get('spans') or []
    return bool(spans) and (spans[0].get('flags', 0) & 16 or 'bold' in spans[0].get('font', '').lower())


def blocks_of(page):
    """text blocks as (rect, first line, full text)"""
    out = []
    for b in page.get_text('dict')['blocks']:
        if b.get('type') != 0 or not b.get('lines'):
            continue
        text = ' '.join(''.join(s['text'] for s in ln['spans']) for ln in b['lines']).strip()
        out.append((pymupdf.Rect(b['bbox']), b['lines'][0], text))
    return out


TABLE = re.compile(r'^\s*table\s*([ivxlc]+|\d+)\b', re.I)


def caption_starts_table(page):
    """lines that open a table caption ("Table 3", "TABLE III")"""
    out = []
    for b in page.get_text('dict')['blocks']:
        for ln in b.get('lines') or []:
            t = ''.join(s['text'] for s in ln['spans']).strip()
            if TABLE.match(t):
                out.append((pymupdf.Rect(ln['bbox']), ln, t))
    return out


def caption_starts(page):
    """every line that may open a caption, as (rect of it and the rest of its block, the line, the text from it on): a
    caption merged into a larger block (labels of a figure, a running paragraph) is found by its own line"""
    out = []
    for b in page.get_text('dict')['blocks']:
        if b.get('type') != 0:
            continue
        lines = b.get('lines') or []
        for k, ln in enumerate(lines):
            t = ''.join(s['text'] for s in ln['spans']).strip()
            if FIG.match(t) or ALG.match(t):
                rest = lines[k:]
                rect = pymupdf.Rect(ln['bbox'])
                for r in rest[1:]:
                    rect |= pymupdf.Rect(r['bbox'])
                text = ' '.join(''.join(s['text'] for s in r['spans']) for r in rest).strip()
                out.append((rect, ln, text))
    return out


def column_of(page, rect, blocks):
    """the x-range of the column a caption sits in: the full text width, or its half"""
    xs0 = [r.x0 for r, *_ in blocks] or [page.rect.x0 + 40]
    xs1 = [r.x1 for r, *_ in blocks] or [page.rect.x1 - 40]
    left, right = min(xs0), max(xs1)
    mid = (left + right) / 2
    if rect.width > 0.55 * (right - left) or (rect.x0 < mid - 20 and rect.x1 > mid + 20):
        return left, right
    return (left, mid) if rect.x0 < mid else (mid, right)


def overlap_x(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def hrules(page, x0, x1):
    """y positions of horizontal rules spanning most of [x0, x1]"""
    ys = []
    for d in page.get_drawings():
        for it in d.get('items', []):
            if it[0] == 'l':
                p, q = it[1], it[2]
                if abs(p.y - q.y) < 1.5 and overlap_x(min(p.x, q.x), max(p.x, q.x), x0, x1) > 0.6 * (x1 - x0):
                    ys.append((p.y + q.y) / 2)
            elif it[0] == 're':
                r = pymupdf.Rect(it[1])
                if r.height < 2.5 and overlap_x(r.x0, r.x1, x0, x1) > 0.6 * (x1 - x0):
                    ys.append((r.y0 + r.y1) / 2)
    return sorted(set(round(y, 1) for y in ys))


def save(page, clip, dpi, dest):
    clip = (clip + (-4, -4, 4, 4)) & page.rect
    page.get_pixmap(dpi=dpi, clip=clip).save(str(dest))
    return [round(v, 1) for v in clip]


def table_pages(i):
    """pages where the design's study reader records a result in a table (uncaptioned artwork there is that table)"""
    f = resolve(i)['folder'] / 'study' / 'reader.json'
    if not f.exists():
        return set()
    return {e.get('page') for e in json.load(open(f)).get('experiments', []) if 'table' in str(e.get('reported_in', '')).lower()}


def figures_and_algorithms(pdf, inventory, outdir, relaxed=False, skip_pages=frozenset()):
    doc = pymupdf.open(str(pdf))
    regions = {}
    for f in inventory:
        if 'bbox' in f:
            regions.setdefault(f['page'], []).append(pymupdf.Rect(f['bbox']))
    found, seen = [], set()
    for pno in range(len(doc)):
        page = doc[pno]
        n = pno + 1
        blocks = blocks_of(page)
        caps = []
        for rect, first, text in caption_starts(page):
            m, a = FIG.match(text), ALG.match(text)
            if m and (relaxed or m.group(3) or is_bold(first) or any(r.y1 <= rect.y0 + 8 and rect.y0 - r.y1 < NEAR for r in regions.get(n, []))):
                caps.append(('figure', int(m.group(2)), rect, text))
            elif a and (a.group(3) or is_bold(first) or hrules(page, *column_of(page, rect, blocks))):
                caps.append(('algorithm', int(a.group(2)), rect, text))
        for kind, num, rect, text in caps:
            if (kind, num) in seen:            # "Fig. 3" again on a later page is a reference or a continuation
                continue
            seen.add((kind, num))
            x0, x1 = column_of(page, rect, blocks)
            rec = {'kind': kind, 'number': num, 'page': n, 'caption': text[:600]}
            if kind == 'figure':
                above = [c[2] for c in caps if c[2].y1 <= rect.y0 and overlap_x(c[2].x0, c[2].x1, x0, x1) > 0]
                top = max([r.y1 for r in above], default=page.rect.y0)
                mine = [r for r in regions.get(n, []) if overlap_x(r.x0, r.x1, x0, x1) > 0.3 * min(r.width, x1 - x0)
                        and r.y0 >= top - 2 and r.y1 <= rect.y0 + 8]
                if not mine:                   # caption above its figure
                    nxt = min([c[2].y0 for c in caps if c[2].y0 > rect.y1], default=page.rect.y1)
                    mine = [r for r in regions.get(n, []) if overlap_x(r.x0, r.x1, x0, x1) > 0.3 * min(r.width, x1 - x0)
                            and r.y0 >= rect.y1 - 2 and r.y1 <= nxt and r.y0 - rect.y1 < NEAR]
                if mine:
                    clip = rect
                    for r in mine:
                        clip = clip | r
                    rec['found'] = 'region'
                else:
                    clip = pymupdf.Rect(x0, max(top, rect.y0 - 0.45 * page.rect.height), x1, rect.y1)
                    rec['found'] = 'approximate (no recorded artwork)'
                cls = 'result' if RESULT.search(text) else ('design' if DESIGN.search(text) else 'other')
                rec['class'] = cls
                rec['file'] = f'fig{num:02d}_p{n:02d}.png'
                rec['bbox'] = save(page, clip, FIG_DPI, outdir / rec['file'])
            else:
                rules = hrules(page, x0, x1)
                frame = [pymupdf.Rect(it[1]) for d in page.get_drawings() for it in d.get('items', []) if it[0] == 're'
                         and pymupdf.Rect(it[1]).contains(rect) and pymupdf.Rect(it[1]).height > 40]
                if frame:
                    clip, rec['found'] = min(frame, key=lambda r: r.get_area()), 'frame'
                else:
                    top = max([y for y in rules if rect.y0 - 22 <= y <= rect.y0 + 2], default=rect.y0 - 2)
                    below = [y for y in rules if y > rect.y1 + 14]
                    if below:
                        clip, rec['found'] = pymupdf.Rect(x0, top, x1, below[0]), 'rules'
                    else:
                        clip, rec['found'] = pymupdf.Rect(x0, top, x1, page.rect.y1 - 36), 'to the column end; continues'
                rec['file'] = f'alg{num:02d}_p{n:02d}.png'
                rec['bbox'] = save(page, clip, ALG_DPI, outdir / rec['file'])
                if rec['found'].endswith('continues') and pno + 1 < len(doc):
                    nxt = doc[pno + 1]
                    nr = [y for y in hrules(nxt, x0, x1) if y < 0.7 * nxt.rect.height]
                    if nr:
                        rec['continuation'] = f'alg{num:02d}_p{n + 1:02d}_cont.png'
                        save(nxt, pymupdf.Rect(x0, nxt.rect.y0 + 30, x1, nr[0]), ALG_DPI, outdir / rec['continuation'])
            found.append(rec)
    figs = [f for f in found if f['kind'] == 'figure']
    if not figs and not relaxed:               # no caption passed the checks: try again accepting any line that opens "Fig. N"
        for x in found:
            (outdir / x['file']).unlink(missing_ok=True)
            if x.get('continuation'):
                (outdir / x['continuation']).unlink(missing_ok=True)
        return figures_and_algorithms(pdf, inventory, outdir, relaxed=True, skip_pages=skip_pages)
    mentioned = {int(x) for pg in doc for x in re.findall(r'\bfig(?:ure)?\.?\s*(\d+)', pg.get_text(), re.I)}
    if not figs or len({f['number'] for f in figs}) < len(mentioned) / 2:
        # captions not found for most figures (an unreadable text layer, captions the text layer splits): the large artwork the
        # pipeline recorded, except what a crop already holds and what sits next to a "Table N" caption
        k, taken = 0, [(f['page'], pymupdf.Rect(f['bbox'])) for f in found]
        for pg, rs in sorted(regions.items()):
            if pg in skip_pages:
                continue
            tables = [r for r, ln, t in caption_starts_table(doc[pg - 1])]
            for r in rs:
                if r.get_area() >= 20000 and not any(q == pg and (t & r).get_area() > 0.3 * r.get_area() for q, t in taken) \
                        and not any(abs(t.y1 - r.y0) < NEAR or abs(r.y1 - t.y0) < NEAR for t in tables):
                    k += 1
                    rec = {'kind': 'figure', 'number': 900 + k, 'page': pg, 'caption': '', 'class': 'unknown (caption not found in the text layer)',
                           'found': 'artwork region only', 'file': f'art{k:02d}_p{pg:02d}.png'}
                    rec['bbox'] = save(doc[pg - 1], r, FIG_DPI, outdir / rec['file'])
                    found.append(rec)
        figs = [f for f in found if f['kind'] == 'figure']
    if figs and not any(f['class'].startswith(('design', 'unknown')) for f in figs):
        min(figs, key=lambda f: f['number'])['class'] = 'design (first figure; no caption names the design)'
    return found, len(doc)


def image_algorithm_pages(i, pdf, found, outdir):
    """where a reader's notes name algorithms that no caption gave (algorithm boxes printed as images), the pages the reader read
    as images, rendered whole"""
    d = resolve(i)['folder']
    notes, img_pages = '', []
    for f in (d / 'algorithm' / 'reader.json', d / 'study' / 'reader.json'):
        if f.exists():
            notes += f.read_text()
            img_pages += json.load(open(f)).get('pages_read_as_images', [])
    named = set(re.findall(r'Algorithms?\s*(\d+)', notes))
    if not named or len([x for x in found if x['kind'] == 'algorithm']) >= len(named):
        return []
    doc, out = pymupdf.open(str(pdf)), []
    for pg in sorted(set(img_pages)):
        rec = {'kind': 'algorithm', 'number': 0, 'page': pg, 'caption': '', 'found': 'whole page the reader read as an image',
               'file': f'algpage_p{pg:02d}.png'}
        rec['bbox'] = save(doc[pg - 1], doc[pg - 1].rect, ALG_DPI, outdir / rec['file'])
        out.append(rec)
    return out


def ids():
    return sorted(d['id'] for d in load_designs()) + [f'Z0{n}' for n in range(1, 10)]


def main():
    rows = []
    for i in sys.argv[1:] or ids():
        d = resolve(i)
        pf = ROOT / d['paper_folder']
        pdf = next(pf.glob('*.pdf'))
        inv = json.load(open(pf / 'metadata.json')).get('figure_inventory', [])
        outdir = OUT / i
        outdir.mkdir(parents=True, exist_ok=True)
        for old in outdir.glob('*.png'):
            old.unlink()
        found, pages = figures_and_algorithms(pdf, inv, outdir, skip_pages=table_pages(i))
        found += image_algorithm_pages(i, pdf, found, outdir)
        save_json(outdir / 'index.json', {'design': i, 'pdf': str(pdf.relative_to(ROOT)), 'pages': pages, 'made': now(), 'items': found})
        f = [x for x in found if x['kind'] == 'figure']
        a = [x for x in found if x['kind'] == 'algorithm']
        rows.append((i, len(f), sum(x['class'].startswith('design') for x in f), sum(x['found'].startswith('approx') for x in f),
                     len(a), sum('continues' in x['found'] for x in a)))
        print(f'{i}: {len(f)} figures ({rows[-1][2]} design, {rows[-1][3]} approximate), {len(a)} algorithms ({rows[-1][5]} continue)')
    print('designs:', len(rows), '| with no figure caption found:', [r[0] for r in rows if r[1] == 0],
          '| with no algorithm found:', sum(1 for r in rows if r[4] == 0))


if __name__ == '__main__':
    main()
