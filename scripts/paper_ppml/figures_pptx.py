#!/usr/bin/env python3
"""The figures and tables of the PPML review as an editable PowerPoint file, for the author to take apart and redraw
(the author, 5 October 2026: "can they be in any format which i can edit … i will use your diagrams just for inspiration
and will make my own"; chose PowerPoint; 12 October 2026: "make sure the pptx has all updated figures, tables, diagrams").

Part 1 — every figure as drawn: each SVG of build/figures/ (written by figures.py) becomes native PowerPoint shapes at
its true size (1 SVG pixel = 0.75 pt). A box keeps its text inside it; a box with several labels is grouped with them;
an arrow is one connector with an arrowhead, attached to the boxes it starts or ends on, so it follows them when they move.
Part 2 — every table of the paper as a native PowerPoint table, taken from the paper as built (build/paper-V<n>.md), so
that numbers, citations and captions are those of that version; a long table continues on the next slide with its
header row repeated.
Part 3 — the charts with their data: years, mechanisms, checks and threats as native PowerPoint charts (the numbers sit in
the chart's own data sheet: right-click > Edit Data), the heat map and the coverage grids as tables. The numbers come
from the <name>.data.json files that figures.py writes beside each chart.

Each slide is titled with the number and caption of the figure or table in the paper version given, as built. The slide
is made large enough for the largest figure at its true size. The python-pptx library builds the file; this script only
maps the drawing onto it. An existing file is never overwritten.

Usage: scripts/.venv/bin/python scripts/paper_ppml/figures_pptx.py <version> [--out <folder>]      e.g. 56
"""
import ast, json, math, pathlib, re, sys
import xml.etree.ElementTree as ET

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
FIG = B / 'build' / 'figures'
OUT_DIR = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
NS = '{http://www.w3.org/2000/svg}'
PX = 9525                                  # EMU per SVG pixel (1/96 inch)
SLIDE_W, SLIDE_H, TOP, MARGIN = Inches(13.6), Inches(11.5), Inches(0.85), Inches(0.3)   # the slide grows in main()
SUPP_FIGS, FIGCAP_ALL = [], {}
FONT = 'Helvetica Neue'
TABLE_PT = 10                              # body text of the paper's tables (9 pt for tables of seven or more columns)
CHARTS = {'threats', 'years'}
TABLES = {'trends', 'survey_coverage', 'prim_coverage'}


def rgb(c):
    c = (c or '').strip().lstrip('#')
    if len(c) == 3:
        c = ''.join(ch * 2 for ch in c)
    return RGBColor.from_string(c.upper()) if re.fullmatch(r'[0-9a-fA-F]{6}', c) else None


def num(e, k, d=0.0):
    v = e.get(k)
    return float(v) if v not in (None, '') else d


# ------------------------------------------------------------------ the paper's figure numbers and captions
def captions():
    src = (ROOT / 'scripts' / 'paper_ppml' / 'build.py').read_text(encoding='utf-8')
    cap = next(ast.literal_eval(n.value) for n in ast.walk(ast.parse(src))
               if isinstance(n, ast.Assign) and any(getattr(t, 'id', '') == 'FIGCAP' for t in n.targets))
    import os
    parts = pathlib.Path(os.environ.get('PPML_PARTS') or B / 'parts')          # the parts of the frame being built (V68: parts-v68)
    order = []
    for part in sorted(parts.glob('*.md')):
        for line in part.read_text(encoding='utf-8').splitlines():
            m = re.fullmatch(r'\{\{FIG:(\w+)\}\}', line.strip())
            if m and m.group(1) not in order:
                order.append(m.group(1))
    return order, cap


# ------------------------------------------------------------------ SVG elements as plain records
def text_record(e):
    spans = e.findall(f'{NS}tspan')
    lines = [s.text or '' for s in spans] if spans else [e.text or '']
    size = num(e, 'font-size', 13)
    dy = num(spans[1], 'dy', size * 1.25) if len(spans) > 1 else size * 1.25
    r = {'tag': 'text', 'lines': lines, 'size': size, 'dy': dy, 'anchor': e.get('text-anchor', 'start'),
         'bold': e.get('font-weight') == 'bold', 'italic': e.get('font-style') == 'italic', 'fill': e.get('fill', '#000000'),
         'rot': 0.0}
    tf = e.get('transform')
    if tf:
        tr = re.search(r'translate\(([-\d.]+)[ ,]+([-\d.]+)\)', tf)
        ro = re.search(r'rotate\(([-\d.]+)\)', tf)
        r['x'], r['y'] = (float(tr.group(1)), float(tr.group(2))) if tr else (0.0, 0.0)
        r['rot'] = float(ro.group(1)) if ro else 0.0
    else:
        r['x'], r['y'] = num(e, 'x'), num(e, 'y')
    r['w'] = max(len(l) for l in lines) * size * 0.56 + 6
    r['h'] = (len(lines) - 1) * dy + size * 1.3
    # the visual centre: F.text puts the first baseline at centre - (n-1)*dy/2 + 0.35*size
    lx = {'start': r['w'] / 2, 'end': -r['w'] / 2}.get(r['anchor'], 0.0)
    ly = -0.35 * size + (len(lines) - 1) * dy / 2
    a = math.radians(r['rot'])
    r['cx'] = r['x'] + lx * math.cos(a) - ly * math.sin(a)
    r['cy'] = r['y'] + lx * math.sin(a) + ly * math.cos(a)
    return r


def records(svg):
    root = ET.parse(svg).getroot()
    out = []
    for e in root:
        tag = e.tag.replace(NS, '')
        if tag == 'rect':
            if e.get('x') is None and e.get('y') is None:          # the white canvas
                continue
            out.append({'tag': 'rect', 'x': num(e, 'x'), 'y': num(e, 'y'), 'w': num(e, 'width'), 'h': num(e, 'height'),
                        'rx': num(e, 'rx'), 'fill': e.get('fill'), 'stroke': e.get('stroke'), 'sw': num(e, 'stroke-width', 1.0),
                        'dash': e.get('stroke-dasharray')})
        elif tag == 'text':
            out.append(text_record(e))
        elif tag == 'line':
            out.append({'tag': 'line', 'pts': [(num(e, 'x1'), num(e, 'y1')), (num(e, 'x2'), num(e, 'y2'))],
                        'stroke': e.get('stroke'), 'sw': num(e, 'stroke-width', 1.0), 'dash': e.get('stroke-dasharray'), 'arrow': False})
        elif tag == 'polygon':
            p = [tuple(map(float, xy.split(','))) for xy in e.get('points').split()]
            out.append({'tag': 'polygon', 'pts': p, 'fill': e.get('fill')})
        elif tag == 'path':
            out.append({'tag': 'path', 'pts': path_points(e.get('d')), 'stroke': e.get('stroke'), 'sw': num(e, 'stroke-width', 1.0)})
    return merge_arrows(out)


def path_points(d):
    """M/L/C paths as a polyline; a cubic curve is sampled in 16 steps"""
    tok = re.findall(r'[MLC]|-?[\d.]+', d)
    pts, i, cmd = [], 0, None
    while i < len(tok):
        if tok[i] in 'MLC':
            cmd = tok[i]
            i += 1
            continue
        if cmd in 'ML':
            pts.append((float(tok[i]), float(tok[i + 1])))
            i += 2
        else:
            (x1, y1, x2, y2, x3, y3), x0, y0 = map(float, tok[i:i + 6]), *pts[-1]
            for k in range(1, 17):
                t = k / 16
                pts.append(((1 - t) ** 3 * x0 + 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3 * x3,
                            (1 - t) ** 3 * y0 + 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3 * y3))
            i += 6
    return pts


def merge_arrows(recs):
    """F.arrow draws a line shortened by 0.8 × head and a triangle whose first point is the tip: make them one arrow"""
    out = []
    for r in recs:
        if r['tag'] == 'polygon' and len(r['pts']) == 3 and out:
            tip = r['pts'][0]
            for prev in reversed(out[-3:]):
                if prev['tag'] == 'line' and not prev['arrow'] and math.dist(prev['pts'][1], tip) < 9:
                    prev['pts'][1], prev['arrow'], prev['head'] = tip, True, r['fill']
                    break
            else:
                out.append(r)
            continue
        out.append(r)
    return out


# ------------------------------------------------------------------ drawing the records as PowerPoint shapes
class Canvas:
    def __init__(self, slide, w, h, top=None):
        top = TOP if top is None else top
        self.slide = slide
        self.ox = (SLIDE_W - w * PX) // 2
        self.oy = top + max(0, (SLIDE_H - top - MARGIN - h * PX) // 2)
        self.boxes = []                                            # (shape, x, y, w, h) for attaching connectors

    def X(self, x):
        return Emu(int(self.ox + x * PX))

    def Y(self, y):
        return Emu(int(self.oy + y * PX))


def style_line(line, color, sw, dash=None):
    c = rgb(color)
    if c is None:
        line.fill.background()
        return
    line.color.rgb = c
    line.width = Pt(sw * 0.75)
    if dash:
        ln = line._get_or_add_ln()
        for old in ln.findall(qn('a:prstDash')):
            ln.remove(old)
        el = ln.makeelement(qn('a:prstDash'), {'val': 'dash'})
        ln.append(el)


def fill_text(tf, t, left_inset=0):
    tf.word_wrap = False
    tf.auto_size = None
    tf.margin_left = Emu(int(left_inset * PX))
    tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, line in enumerate(t['lines']):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {'middle': PP_ALIGN.CENTER, 'end': PP_ALIGN.RIGHT}.get(t['anchor'], PP_ALIGN.LEFT)
        p.line_spacing = Pt(t['dy'] * 0.75)
        run = p.add_run()
        run.text = line
        f = run.font
        f.name, f.size, f.bold, f.italic = FONT, Pt(t['size'] * 0.75), t['bold'], t['italic']
        f.color.rgb = rgb(t['fill']) or RGBColor(0, 0, 0)


def add_rect(shapes, cv, r, t=None, left_inset=0):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if r['rx'] > 0 else MSO_SHAPE.RECTANGLE
    sh = shapes.add_shape(kind, cv.X(r['x']), cv.Y(r['y']), Emu(int(max(r['w'], 0.5) * PX)), Emu(int(max(r['h'], 0.5) * PX)))
    if r['rx'] > 0:
        sh.adjustments[0] = min(0.5, r['rx'] / max(1.0, min(r['w'], r['h'])))
    if rgb(r['fill']) is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(r['fill'])
    style_line(sh.line, r['stroke'], r['sw'], r['dash'])
    sh.shadow.inherit = False
    if t:
        fill_text(sh.text_frame, t, left_inset)
    else:
        sh.text_frame.text = ''
    cv.boxes.append((sh, r['x'], r['y'], r['w'], r['h']))
    return sh


def add_text(shapes, cv, t):
    w, h = t['w'], t['h']
    sh = shapes.add_textbox(cv.X(t['cx'] - w / 2), cv.Y(t['cy'] - h / 2), Emu(int(w * PX)), Emu(int(h * PX)))
    fill_text(sh.text_frame, t)
    if t['rot']:
        sh.rotation = t['rot'] % 360
    return sh


def attach(cv, conn, end, x, y):
    """connect an arrow end to the box whose edge midpoint it touches"""
    for sh, bx, by, bw, bh in cv.boxes:
        for idx, (px, py) in enumerate(((bx + bw / 2, by), (bx, by + bh / 2), (bx + bw / 2, by + bh), (bx + bw, by + bh / 2))):
            if math.dist((x, y), (px, py)) < 3.5:
                (conn.begin_connect if end == 'begin' else conn.end_connect)(sh, idx)
                return


def add_line(shapes, cv, r):
    (x1, y1), (x2, y2) = r['pts']
    conn = shapes.add_connector(MSO_CONNECTOR.STRAIGHT, cv.X(x1), cv.Y(y1), cv.X(x2), cv.Y(y2))
    style_line(conn.line, r['stroke'] or '#000000', r['sw'], r['dash'])
    if r['arrow']:
        ln = conn.line._get_or_add_ln()
        ln.append(ln.makeelement(qn('a:tailEnd'), {'type': 'triangle', 'w': 'med', 'len': 'med'}))
        attach(cv, conn, 'begin', x1, y1)
        attach(cv, conn, 'end', x2, y2)
    return conn


def add_poly(shapes, cv, pts, fill=None, stroke=None, sw=1.0, closed=True):
    fb = shapes.build_freeform(cv.X(pts[0][0]), cv.Y(pts[0][1]), scale=1.0)
    fb.add_line_segments([(cv.X(x), cv.Y(y)) for x, y in pts[1:]], close=closed)
    sh = fb.convert_to_shape()
    if fill and rgb(fill):
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(fill)
    else:
        sh.fill.background()
    style_line(sh.line, stroke, sw)
    sh.shadow.inherit = False
    return sh


def inside(t, r, pad=2):
    return r['x'] - pad <= t['cx'] <= r['x'] + r['w'] + pad and r['y'] - pad <= t['cy'] <= r['y'] + r['h'] + pad


def svg_size(svg):
    """the drawing's width and height in SVG pixels"""
    return tuple(float(v) for v in re.search(r'width="([\d.]+)" height="([\d.]+)"', svg.read_text(encoding='utf-8')[:400]).groups())


def draw(slide, svg, top=None):
    recs = records(svg)
    w, h = svg_size(svg)
    cv = Canvas(slide, w, h, top)
    i = 0
    while i < len(recs):
        r = recs[i]
        if r['tag'] == 'rect':
            nxt = recs[i + 1] if i + 1 < len(recs) else None
            own = None
            if nxt and nxt['tag'] == 'text' and not nxt['rot']:          # F.box: the text centred in its box (or set in by 12 px)
                if nxt['anchor'] == 'middle' and abs(nxt['x'] - (r['x'] + r['w'] / 2)) < 2 and abs(nxt['cy'] - (r['y'] + r['h'] / 2)) < 6:
                    own = (nxt, 0)
                elif nxt['anchor'] == 'start' and abs(nxt['x'] - (r['x'] + 12)) < 2 and abs(nxt['cy'] - (r['y'] + r['h'] / 2)) < 6:
                    own = (nxt, 12)
            if own:
                add_rect(slide.shapes, cv, r, *own)
                i += 2
                continue
            labels = []                                           # a box with several labels: one group
            j = i + 1
            while j < len(recs) and recs[j]['tag'] == 'text' and not recs[j]['rot'] and inside(recs[j], r):
                labels.append(recs[j])
                j += 1
            if labels:
                g = slide.shapes.add_group_shape()
                add_rect(g.shapes, cv, r)
                for t in labels:
                    add_text(g.shapes, cv, t)
                i = j
                continue
            add_rect(slide.shapes, cv, r)
        elif r['tag'] == 'text':
            add_text(slide.shapes, cv, r)
        elif r['tag'] == 'line':
            add_line(slide.shapes, cv, r)
        elif r['tag'] == 'polygon':
            add_poly(slide.shapes, cv, r['pts'], fill=r['fill'])
        elif r['tag'] == 'path':
            if len(r['pts']) == 2:
                add_line(slide.shapes, cv, {'pts': r['pts'], 'stroke': r['stroke'], 'sw': r['sw'], 'dash': None, 'arrow': False})
            else:
                add_poly(slide.shapes, cv, r['pts'], stroke=r['stroke'], sw=r['sw'], closed=False)
        i += 1


# ------------------------------------------------------------------ part 2: native charts and tables
def chart_slide(slide, d, name=None, top=None):
    cd = CategoryChartData()
    cd.categories = d['categories']
    for name, _, vals in d['series']:
        cd.add_series(name, vals)
    kind = {'column_stacked': XL_CHART_TYPE.COLUMN_STACKED, 'bar_stacked': XL_CHART_TYPE.BAR_STACKED,
            'bar_clustered': XL_CHART_TYPE.BAR_CLUSTERED}[d['kind']]
    gf = slide.shapes.add_chart(kind, MARGIN * 2, (TOP if top is None else top) + Inches(0.1), SLIDE_W - MARGIN * 4, Inches(6.5), cd)
    ch = gf.chart
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.TOP
    ch.legend.include_in_layout = False
    ch.legend.font.size, ch.legend.font.name = Pt(12), FONT
    ch.font.name, ch.font.size = FONT, Pt(12)
    for s, (_, col, _) in zip(ch.plots[0].series, d['series']):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = rgb(col)
        if d['kind'] == 'bar_clustered':
            s.format.line.color.rgb = rgb('#B85450')                 # the red outline of the drawn threats figure
    pl = ch.plots[0]
    pl.gap_width = 60
    if d['kind'] == 'bar_clustered':
        pl.overlap = 0
    pl.has_data_labels = True
    dl = pl.data_labels
    dl.font.size, dl.font.name, dl.font.bold = Pt(11), FONT, True
    dl.number_format, dl.number_format_is_linked = ('0' if d['kind'] == 'bar_clustered' else '0;-0;;'), False   # no '0' inside stacks
    dl.position = XL_LABEL_POSITION.OUTSIDE_END if d['kind'] == 'bar_clustered' else XL_LABEL_POSITION.CENTER
    for s, (_, col, _) in zip(pl.series, d['series']):           # labels light on dark bars, dark on light ones
        c = rgb(col)
        dark = d['kind'] != 'bar_clustered' and (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) < 150
        sl = s.data_labels
        sl.show_value = True
        sl.number_format, sl.number_format_is_linked = dl.number_format, False
        sl.position = dl.position
        sl.font.size, sl.font.name, sl.font.bold = Pt(11), FONT, True
        sl.font.color.rgb = RGBColor(255, 255, 255) if dark else RGBColor(0x0b, 0x0b, 0x0b)
    if d['kind'].startswith('bar'):
        ch.category_axis.reverse_order = True                     # first category on top, as drawn
    ch.value_axis.has_major_gridlines = False
    ch.value_axis.visible = d['kind'] == 'column_stacked'


def set_border(c, color='B4BCC8', width=9525):
    """thin visible lines round a table cell (the default table style draws white ones)"""
    tcPr = c._tc.get_or_add_tcPr()
    for k, tag in enumerate(('a:lnL', 'a:lnR', 'a:lnT', 'a:lnB')):    # the schema wants the lines before the fill
        for old in tcPr.findall(qn(tag)):
            tcPr.remove(old)
        ln = tcPr.makeelement(qn(tag), {'w': str(width), 'cap': 'flat', 'cmpd': 'sng', 'algn': 'ctr'})
        sf = ln.makeelement(qn('a:solidFill'), {})
        sf.append(sf.makeelement(qn('a:srgbClr'), {'val': color}))
        ln.append(sf)
        ln.append(ln.makeelement(qn('a:prstDash'), {'val': 'solid'}))
        tcPr.insert(k, ln)


def table_slide(slide, d, name, top):
    sys.path.insert(0, str(ROOT / 'scripts' / 'paper_ppml'))
    import figures as FG                                          # the shades the heat map uses
    groups = []
    if d['kind'] == 'heat':
        body = []
        for title, rs in d['panels']:
            mx = max([n for _, v in rs for n in v] or [1])
            body.append(('panel', title, None))
            body += [('row', lab, [(n, FG.shade(n, mx)) for n in v]) for lab, v in rs]
        cols, head = d['columns'], ['']
    else:                                                         # a coverage grid: the grade in words, in its colour
        body = [('row', lab, [(v, d['colors'].get(v, '#ffffff')) for v in vals]) for lab, vals in d['rows']]
        cols, head = d['columns'], ['Primary study' if name == 'prim_coverage' else 'Survey']
        groups = d.get('groups') or []
    n_head = 2 if groups else 1
    n_rows, n_cols = len(body) + n_head, len(cols) + 1
    lw = Inches(3.2)
    cw = int((SLIDE_W - MARGIN * 4 - lw) / len(cols))
    rh = min(Inches(0.32), int((SLIDE_H - top - MARGIN * 2) / n_rows))
    gt = slide.shapes.add_table(n_rows, n_cols, MARGIN * 2, top, lw + cw * len(cols), rh * n_rows)
    tb = gt.table
    tb.first_row = tb.horz_banding = False
    tb.columns[0].width = lw
    for j in range(1, n_cols):
        tb.columns[j].width = cw

    def cell(i, j, text, fill='#ffffff', bold=False, color='#0b0b0b', align=PP_ALIGN.CENTER, size=10.5):
        c = tb.cell(i, j)
        c.fill.solid()
        c.fill.fore_color.rgb = rgb(fill)
        set_border(c)
        c.margin_left = c.margin_right = Inches(0.04)
        c.margin_top = c.margin_bottom = 0
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = c.text_frame.paragraphs[0]
        p.alignment = align
        r = p.add_run()
        r.text = text
        r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
        r.font.color.rgb = rgb(color)

    if groups:                                                    # the layers above their columns: SQ1, SQ2, SQ3 (3), ...
        cell(0, 0, '', fill='#eef2f8')
        j = 1
        for g, span in groups:
            for k in range(span):
                cell(0, j + k, g if k == 0 else '', fill='#eef2f8', bold=True, size=9.5)
            if span > 1:
                tb.cell(0, j).merge(tb.cell(0, j + span - 1))
            j += span
    hr = n_head - 1
    cell(hr, 0, head[0], bold=True, align=PP_ALIGN.LEFT, fill='#eef2f8' if groups else '#ffffff')
    for j, c in enumerate(cols, 1):
        cell(hr, j, c, bold=True, size=9.5 if len(c) > 9 else 10.5, fill='#eef2f8' if groups else '#ffffff')
    for i, (kind, lab, vals) in enumerate(body, n_head):
        tb.rows[i].height = rh
        if kind == 'panel':
            cell(i, 0, lab, bold=True, align=PP_ALIGN.LEFT)
            for j in range(1, n_cols):
                cell(i, j, '')
            continue
        cell(i, 0, lab, align=PP_ALIGN.LEFT)
        for j, (n, fill) in enumerate(vals, 1):
            if isinstance(n, str):                                # Yes / Partial / No
                dark = (0.299 * rgb(fill)[0] + 0.587 * rgb(fill)[1] + 0.114 * rgb(fill)[2]) < 150
                cell(i, j, n, fill=fill, size=9.5, color='#ffffff' if dark else '#0b0b0b')
                continue
            dark = fill in FG.SHADE[4:] or fill.lower() == '#256abf'
            cell(i, j, '' if n is None else (str(n) if n else '–'), fill=fill, bold=bool(n), color='#ffffff' if dark else '#0b0b0b')


# ------------------------------------------------------------------ the paper's own tables, as built
def split_row(line):
    return [c.strip().replace('\\|', '|') for c in re.split(r'(?<!\\)\|', line.strip()[1:-1])]


def built_paper(version):
    return (B / 'build' / f'paper-V{version}.md').read_text(encoding='utf-8')


def paper_tables(md):
    """every table of the built paper, in order: (label, caption, header, rows, relative column widths)"""
    lines, out = md.split('\n'), []
    for i, line in enumerate(lines):
        m = re.match(r'^Table: (Table (?:[IVXLC]+|S\d+))\. (.*)$', line)
        if not m:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].startswith('|'):
            j += 1
        block = []
        while j < len(lines) and lines[j].startswith('|'):
            block.append(lines[j])
            j += 1
        widths = [max(1, len(c.strip())) for c in block[1].strip()[1:-1].split('|')]
        while j < len(lines) and not lines[j].strip():
            j += 1
        note = lines[j].strip()[1:-1] if j < len(lines) and re.fullmatch(r'\*[^*].*[^*]\*', lines[j].strip()) else ''
        out.append((m.group(1), m.group(2), split_row(block[0]), [split_row(r) for r in block[2:]], widths, note))
    return out


def figure_captions(md):
    """figure name (its image file) -> (label, caption) as built"""
    out = {}
    for m in re.finditer(r'^!\[(Fig\. \d+)\. (.*?)\]\(([^)]*)\)', md, re.M):
        out[pathlib.Path(m.group(3)).stem] = (m.group(1), m.group(2))
    return out


def text_lines(text, width, size):
    """lines a cell's text takes at this width (EMU) and size (pt): words wrapped at about half an em per character"""
    cpl = max(4, int((width - Inches(0.1)) / 12700 / (size * 0.52)))
    n = 0
    for para in text.split('\n'):
        k, cur = 1, 0
        for w in para.split():
            if cur and cur + 1 + len(w) > cpl:
                k, cur = k + 1, len(w)
            else:
                cur += (1 if cur else 0) + len(w)
            while cur > cpl:
                k, cur = k + 1, cur - cpl
        n += k
    return n


def row_height(cells, widths, size, bold=False):
    lines = max(text_lines(c, w, size * (1.06 if bold else 1)) for c, w in zip(cells, widths))
    return int(lines * Pt(size) * 1.22 + Inches(0.08))


def caption_box(slide, label, text, size=13, sub=None):
    """the number and caption above a figure or table (and a note in italics); returns where the space below starts"""
    w = SLIDE_W - MARGIN * 2
    n = text_lines(f'{label} {text}', w, size)
    h = n * Pt(size) * 1.25 + (text_lines(sub, w, 11) * Pt(11) * 1.25 if sub else 0) + Inches(0.1)
    tb = slide.shapes.add_textbox(MARGIN, Inches(0.2), w, int(h))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    for t, bold in ((label + ' ', True), (text, False)):
        r = p.add_run()
        r.text = t
        r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
    if sub:
        r = tf.add_paragraph().add_run()
        r.text = sub
        r.font.name, r.font.size, r.font.italic = FONT, Pt(11), True
        r.font.color.rgb = rgb('#52514e')
    return Emu(int(Inches(0.2) + h + Inches(0.1)))


def draw_table(slide, top, header, rows, widths, heights, size):
    gt = slide.shapes.add_table(len(rows) + 1, len(header), MARGIN, top, sum(widths), sum(heights))
    tb = gt.table
    tb.first_row = tb.horz_banding = False
    for j, w in enumerate(widths):
        tb.columns[j].width = Emu(w)
    for i, (cells, h) in enumerate(zip([header] + rows, heights)):
        tb.rows[i].height = Emu(h)
        for j, text in enumerate(cells):
            c = tb.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = rgb('#eef2f8' if i == 0 else '#ffffff')
            set_border(c)
            c.margin_left = c.margin_right = Inches(0.05)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.TOP
            tf = c.text_frame
            tf.word_wrap = True
            for k, para in enumerate(text.split('\n')):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                r = p.add_run()
                r.text = para
                r.font.name, r.font.size, r.font.bold = FONT, Pt(size), i == 0
                r.font.color.rgb = rgb('#0b0b0b')


def table_slides(prs, blank, md):
    """Part 2: every table of the paper, continued on further slides with its header repeated where it is long"""
    made = []
    for label, caption, header, rows, rel, note in paper_tables(md):
        total = SLIDE_W - MARGIN * 2
        widths = [int(total * r / sum(rel)) for r in rel]
        size = TABLE_PT if len(header) < 7 else TABLE_PT - 1
        hh = row_height(header, widths, size, True)
        heights = [row_height(r, widths, size) for r in rows]
        start, part = 0, 0
        while start < len(rows) or part == 0:
            s = prs.slides.add_slide(blank)
            top = caption_box(s, label + ('.' if part == 0 else ' (continued).'), caption if part == 0 else '',
                              sub=note if part == 0 and note else None)      # the table's note (its legend) under the caption
            avail, used, end = SLIDE_H - top - MARGIN, hh, start
            while end < len(rows) and used + heights[end] <= avail:
                used, end = used + heights[end], end + 1
            if end == start and start < len(rows):                 # one row taller than the slide: alone on its slide
                end = start + 1
            draw_table(s, top, header, rows[start:end], widths, [hh] + heights[start:end], size)
            s.notes_slide.notes_text_frame.text = (f'{label}, rows {start + 1}–{end} of {len(rows)}; taken from the paper '
                                                   f'as built (build/paper-V<n>.md).')
            start, part = end, part + 1
        made.append((label, part))
    return made


# ------------------------------------------------------------------ the deck
def title(slide, text, sub=None):
    tb = slide.shapes.add_textbox(MARGIN, Inches(0.2), SLIDE_W - MARGIN * 2, Inches(0.55))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = text
    r.font.name, r.font.size, r.font.bold = FONT, Pt(16), True
    if sub:
        r2 = tf.add_paragraph().add_run()
        r2.text = sub
        r2.font.name, r2.font.size, r2.font.italic = FONT, Pt(11), True
        r2.font.color.rgb = rgb('#52514e')


def main(version, out_dir=OUT_DIR):
    global SLIDE_W, SLIDE_H
    out = out_dir / f'Privacy Preserving Machine Learning in NextGeneration IoT - V{version} figures and tables.pptx'
    if out.exists():
        sys.exit(f'{out.name} exists; versions are never overwritten')
    order, cap = captions()
    md = built_paper(version)
    built = figure_captions(md)
    missing = [n for n in order if n not in built]
    if missing:
        sys.exit(f'figures placed in the parts but not in build/paper-V{version}.md: {missing} (build that version first)')
    import build as BLD
    import build_supplement as SUP
    global SUPP_FIGS, FIGCAP_ALL
    SUPP_FIGS, FIGCAP_ALL = SUP.FIGURES, BLD.FIGCAP
    if not (B / 'build' / f'supplement-V{version}.md').exists():     # a version without supplementary material (V68)
        SUPP_FIGS = []
    sizes = {n: svg_size(FIG / f'{n}.svg') for n in order + [k for k, _ in SUPP_FIGS]}   # the slide grows to the largest figure
    SLIDE_W = Emu(max(Inches(13.6), int(max(w for w, _ in sizes.values()) * PX + MARGIN * 2)))
    SLIDE_H = Emu(max(Inches(11.5), int(max(h for _, h in sizes.values()) * PX + Inches(1.6))))
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    blank = prs.slide_layouts[6]
    s = prs.slides.add_slide(blank)
    title(s, f'Figures and tables of the PPML review, version {version} — editable copies',
          'Part 1: every figure as drawn, as PowerPoint shapes (boxes keep their text; arrows stay attached to boxes). '
          'Part 2: every table of the paper as a PowerPoint table, as built in this version (a long table continues on '
          'the next slide), then the figures and tables of the supplementary material. Part 3: the charts with their data '
          '(right-click a chart > Edit Data), and the heat map and '
          f'coverage grids as tables. Slides are {SLIDE_W / 914400:.1f} × {SLIDE_H / 914400:.1f} in so that every figure '
          'keeps its true size; copy any shape onto your own slides.')
    for name in order:
        label, caption = built[name]
        s = prs.slides.add_slide(blank)
        top = caption_box(s, label + '.', caption)
        if top + sizes[name][1] * PX > SLIDE_H - MARGIN:          # a long caption over a tall figure: smaller caption
            for sh in list(s.shapes):
                sh._element.getparent().remove(sh._element)
            top = caption_box(s, label + '.', caption, size=10)
        draw(s, FIG / f'{name}.svg', top)
        s.notes_slide.notes_text_frame.text = f'Drawn by scripts/paper_ppml/figures.py ({name}); converted from build/figures/{name}.svg.'
    tables = table_slides(prs, blank, md)
    supp = B / 'build' / f'supplement-V{version}.md'                # Part 2b: the supplementary material (build_supplement.py)
    for name, n in SUPP_FIGS:
        s = prs.slides.add_slide(blank)
        top = caption_box(s, f'Fig. {n}.', FIGCAP_ALL[name])
        if top + sizes[name][1] * PX > SLIDE_H - MARGIN:
            for sh in list(s.shapes):
                sh._element.getparent().remove(sh._element)
            top = caption_box(s, f'Fig. {n}.', FIGCAP_ALL[name], size=10)
        draw(s, FIG / f'{name}.svg', top)
        s.notes_slide.notes_text_frame.text = f'Supplementary figure; drawn by scripts/paper_ppml/figures.py ({name}).'
    supp_tables = table_slides(prs, blank, supp.read_text(encoding='utf-8')) if supp.exists() else []
    for name in order + [k for k, _ in SUPP_FIGS]:
        if name in CHARTS | TABLES:
            label, caption = built.get(name) or (f'Fig. {dict(SUPP_FIGS)[name]}', FIGCAP_ALL[name])
            d = json.loads((FIG / f'{name}.data.json').read_text(encoding='utf-8'))
            s = prs.slides.add_slide(blank)
            sub = ('A native PowerPoint chart: right-click > Edit Data to change the numbers.' if name in CHARTS
                   else 'A table: each cell keeps the colour of the figure (darker: more studies).' if name == 'trends'
                   else 'A table: each cell gives the grade in the colour of the figure; the columns are grouped as in the figure.')
            top = caption_box(s, f'{label} with its data —', caption, size=12, sub=sub)
            (chart_slide if name in CHARTS else table_slide)(s, d, name, top)
    prs.save(out)
    print(f'written {out}: {len(prs.slides)} slides — {len(order)} figures as drawn; {len(tables)} tables '
          f'({sum(n for _, n in tables)} slides); supplementary: {len(SUPP_FIGS)} figures, {len(supp_tables)} tables '
          f'({sum(n for _, n in supp_tables)} slides); {sum(1 for n in order + [k for k, _ in SUPP_FIGS] if n in CHARTS | TABLES)} figures with their data')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    a = sys.argv[1:]
    main(a[0], pathlib.Path(a[a.index('--out') + 1]) if '--out' in a else OUT_DIR)
