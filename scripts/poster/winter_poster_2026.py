#!/usr/bin/env python3
"""Builds the A1 portrait poster of the PhD for the PGRS Winter Conference 2026 on the University's Blueberry template, a
grid of titled panels with native, editable diagrams.

The layout follows the award-winning Abertay poster the author shared (17 November 2026): a centred title block, three panels
across (the problem, the gap, the idea), a "What's next" band, two wide panels (how the check works, how it will be tested),
three panels across (why it matters, the road ahead, open questions) and a closing banner. Each panel has a navy title bar,
the row-one bars with a subtitle whose key words are gold. The diagrams: federated learning and its four threats; a
three-circle diagram of the review's three conditions with its empty centre; the layered design (blockchain, validators,
gateways) with hollow arrows and one callout for the open element; the five steps of one round of the check; the test plan;
a timeline; a numbered reference list at the foot. Colours carry meaning as in the paper's figures: blue the operating role, green defence, red attack, gold the
ledger. The facts are those of paper V90 (Sections I, VI-B, VII-A and VII-B), the experiment agenda and the design evaluation.

The template's branded frame, logo and footer sit on its slide master and are kept; its sample title and sections are
removed. Text, boxes, circles and arrows are PowerPoint objects. The icons are one family in one colour: Phosphor Icons,
duotone weight (MIT), in the poster's navy, chosen by the author from three such families; fetched and rendered to
transparent PNGs by
scripts/poster/poster_icons.py into winter-conference-2026-poster/icons/. Two QR codes, drawn as vector shapes with segno:
the author's ORCID record in the tab beside the logo, and, in the Open Questions panel, the question page on GitHub Pages
(winter-conference-2026-poster/ask-page/), where one tap opens the reader's mail app with the email written; a mailto: code
was shown as text by the phone scanners tested. The references are the six designs carried forward to Phase 2 of the design evaluation
(Docs/PHASE2-DESIGNS-V3-2026-11-16.html), shortened with "et al." beyond three authors; the author's own review is not
cited.

An existing poster file is never overwritten: every change is a new version number.

Usage: python3 scripts/poster/winter_poster_2026.py <version> [--out <folder>]        e.g. 7
(run scripts/poster/poster_icons.py first if winter-conference-2026-poster/icons/png/ is missing)
(--out writes a draft elsewhere, for previews; the delivered file goes to winter-conference-2026-poster/)
"""
import math, pathlib, sys

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

import segno

ROOT = pathlib.Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'winter-conference-2026-poster'
TEMPLATE = FOLDER / 'templates' / 'Blueberry A1 Student Poster Template.pptx'
ICONS = FOLDER / 'icons' / 'png'

ORCID = 'https://orcid.org/0009-0005-2841-4373'
EMAIL = 's.zareen2400@abertay.ac.uk'
# the question page (winter-conference-2026-poster/ask-page/, published on GitHub Pages): phone scanners show a mailto: code as
# text to copy, but open a web link; one tap on the page opens the reader's mail app with the email written, placeholders to fill
QUESTION_PAGE = 'https://shakir1311.github.io/pgrs-2026-question/'

FONT = 'Source Sans Pro'        # the template's own typeface
NAVY = '13365A'                 # the template's section bars
NAVY_TINT = 'E9EEF4'
SUN = 'F5B82E'                  # the gold of the subtitles and the closing banner, on navy
INK = '1C2430'
MUTED = '5B6670'
RULE = 'B9C5D2'                 # panel borders
RED = 'B23A3A'                  # attacks
RED_TINT = 'FBEAEA'
GREEN = '2E7D4F'                # defence: the validators and the check
GREEN_TINT = 'E6F3EB'
GOLD = '9A7412'                 # the ledger
GOLD_TINT = 'FBF3DC'
BLUE = '2F64A8'                 # the operating role: devices and gateways
BLUE_TINT = 'E8EFF9'
LINE = 'A3AEB9'

CENTER, LEFT = PP_ALIGN.CENTER, PP_ALIGN.LEFT
MIDDLE, TOP = MSO_ANCHOR.MIDDLE, MSO_ANCHOR.TOP

X0, X1 = 1.60, 21.80            # content edges on the white panel, inches (panel 0.94 to 22.46, 3.3 to 31.24)
GUT = 0.40
COL3 = (X1 - X0 - 2 * GUT) / 3
PAD = 0.28                      # inside a panel


def E(inches):
    return Emu(int(round(inches * 914400)))


def rgb(h):
    return RGBColor.from_string(h)


# ---------------------------------------------------------------- primitives

def text(shapes, x, y, w, h, paras, size=20, color=INK, align=LEFT, anchor=TOP, space_after=0.0, line=None, name=None):
    """a text box; paras is a list of paragraphs, each a string, a list of (text, {bold, italic, color, size}) runs,
    or {'runs': [...], 'bullet': colour} for a bulleted paragraph"""
    tb = shapes.add_textbox(E(x), E(y), E(w), E(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        bullet = None
        if isinstance(para, dict):
            bullet, para = para.get('bullet'), para['runs']
        if line:
            p.line_spacing = line
        if space_after and i < len(paras) - 1:
            p.space_after = Pt(space_after)
        if bullet:
            _bullet(p, bullet, size)
        runs = [(para, {})] if isinstance(para, str) else para
        for t, o in runs:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = FONT
            f.size = Pt(o.get('size', size))
            f.bold = o.get('bold', False)
            f.italic = o.get('italic', False)
            f.color.rgb = rgb(o.get('color', color))
    return tb


def _bullet(p, color, size):
    """a round bullet in `color`, hanging"""
    ind = int(size / 72 * 0.95 * 914400)
    pPr = p._p.get_or_add_pPr()
    pPr.set('marL', str(ind))
    pPr.set('indent', str(-ind))
    clr = etree.SubElement(pPr, qn('a:buClr'))
    etree.SubElement(clr, qn('a:srgbClr')).set('val', color)
    etree.SubElement(pPr, qn('a:buFont')).set('typeface', 'Arial')
    etree.SubElement(pPr, qn('a:buChar')).set('char', '•')


def B(*runs, color=NAVY):
    """a bulleted paragraph for text()"""
    return {'runs': list(runs), 'bullet': color}


def box(shapes, x, y, w, h, fill=None, line=None, lw=1.5, radius=0.08, shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=None,
        opacity=None, dash=False):
    s = shapes.add_shape(shape, E(x), E(y), E(w), E(h))
    if name:
        s.name = name
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = min(0.5, radius / min(w, h))
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
        if opacity is not None:
            clr = s.fill._xPr.find(qn('a:solidFill'))[0]
            etree.SubElement(clr, qn('a:alpha')).set('val', str(int(opacity * 100000)))
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(lw)
        if dash:
            s.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    s.text_frame.text = ''
    return s


def pic(shapes, key, x, y, size):
    """an icon (Phosphor duotone, navy, rendered by poster_icons.py), size inches square, top-left corner at (x, y)"""
    png = ICONS / f'{key}.png'
    if not png.exists():
        sys.exit(f'{png} is missing; run scripts/poster/poster_icons.py first')
    pc = shapes.add_picture(str(png), E(x), E(y), E(size), E(size))
    pc.name = f'icon {key}'
    return pc


def qr(shapes, data, x, y, size, color='0E2A47', error='m'):
    """a QR code as one vector shape (each run of dark modules a rectangle) on a white square with its quiet zone"""
    code = segno.make(data, error=error, micro=False)
    rows = [list(r) for r in code.matrix]
    n = len(rows)
    quiet = 2
    m = size / (n + 2 * quiet)
    box(shapes, x, y, size, size, fill='FFFFFF', shape=MSO_SHAPE.RECTANGLE)
    fb = None
    for r, row in enumerate(rows):
        c = 0
        while c < n:
            if row[c]:
                c0 = c
                while c < n and row[c]:
                    c += 1
                x0, y0 = x + (quiet + c0) * m, y + (quiet + r) * m
                x1, y1 = x + (quiet + c) * m, y0 + m * 1.02
                if fb is None:
                    fb = shapes.build_freeform(E(x0), E(y0), scale=1.0)
                else:
                    fb.move_to(E(x0), E(y0))
                fb.add_line_segments([(E(x1), E(y0)), (E(x1), E(y1)), (E(x0), E(y1))], close=True)
            else:
                c += 1
    sh = fb.convert_to_shape()
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(color)
    sh.line.fill.background()
    sh.shadow.inherit = False
    sh.name = 'QR code'
    return code.version, n


def disc(shapes, x, y, d, label, fill, color='FFFFFF', line=None, size=20):
    """a filled circle with a short label in it"""
    box(shapes, x, y, d, d, fill=fill, line=line, lw=2.5, shape=MSO_SHAPE.OVAL)
    text(shapes, x - 0.2, y, d + 0.4, d, [[(label, {'bold': True, 'color': color, 'size': size})]], align=CENTER,
         anchor=MIDDLE)


def connector(shapes, x1, y1, x2, y2, color=INK, width=3.0, head=True, dash=False):
    c = shapes.add_connector(MSO_CONNECTOR.STRAIGHT, E(x1), E(y1), E(x2), E(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    if dash:
        c.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    if head:
        t = etree.SubElement(c.line._get_or_add_ln(), qn('a:tailEnd'))
        t.set('type', 'triangle')
        t.set('w', 'med')
        t.set('len', 'med')
    return c


def block_arrow(shapes, x, y, w, h, up, color):
    """a hollow block arrow pointing up or down"""
    s = shapes.add_shape(MSO_SHAPE.UP_ARROW if up else MSO_SHAPE.DOWN_ARROW, E(x), E(y), E(w), E(h))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb('FFFFFF')
    s.line.color.rgb = rgb(color)
    s.line.width = Pt(2.5)
    s.shadow.inherit = False
    return s


def vlabel(shapes, x, y, w, h, label, fill):
    """a layer's name, outside the layer at the right: a coloured strip with the name running upwards"""
    box(shapes, x, y, w, h, fill=fill, radius=0.1)
    tb = text(shapes, x, y, w, h, [[(label.upper(), {'bold': True, 'color': 'FFFFFF', 'size': 14})]], align=CENTER,
              anchor=MIDDLE)
    tb.text_frame._txBody.find(qn('a:bodyPr')).set('vert', 'vert270')


def panel(shapes, x, y, w, h, title, sub=None):
    """a panel: a navy title bar, with a subtitle whose (text, gold) parts are gold where marked, over a bordered body;
    returns the body's top"""
    hh = 1.16 if sub else 0.74
    box(shapes, x, y, w, h, fill='FFFFFF', line=RULE, lw=1.75, shape=MSO_SHAPE.RECTANGLE, name=f'panel {title}')
    box(shapes, x, y, w, hh, fill=NAVY, shape=MSO_SHAPE.RECTANGLE, name=f'bar {title}')
    if sub:
        text(shapes, x + 0.2, y + 0.1, w - 0.4, 0.6, [[(title, {'bold': True, 'color': 'FFFFFF', 'size': 34})]],
             align=CENTER, anchor=MIDDLE)
        text(shapes, x + 0.2, y + 0.68, w - 0.4, 0.4,
             [[(t, {'color': SUN if gold else 'FFFFFF', 'bold': bool(gold)}) for t, gold in sub]], size=19,
             align=CENTER, anchor=MIDDLE)
    else:
        text(shapes, x + 0.2, y, w - 0.4, hh, [[(title, {'bold': True, 'color': 'FFFFFF', 'size': 30})]], align=CENTER,
             anchor=MIDDLE)
    return y + hh


# ---------------------------------------------------------------- the header

def header(shapes):
    # the tab beside the logo: the event
    text(shapes, 8.5, 1.4, 9.0, 1.7, [
        [('PGRS WINTER CONFERENCE 2026', {'bold': True, 'color': NAVY, 'size': 28})],
        [('Abertay University, Dundee  ·  2–3 December 2026', {'color': MUTED, 'size': 21})],
    ], anchor=MIDDLE, space_after=2)
    # the ORCID record as a QR code at the right of the tab
    qs, qy = 1.64, 1.2
    qx = X1 - qs
    qr(shapes, ORCID, qx, qy, qs, error='m')
    text(shapes, qx - 0.4, qy + qs + 0.02, qs + 0.8, 0.5, [[('ORCID', {'bold': True, 'size': 13, 'color': NAVY})],
                                                          [('0009-0005-2841-4373', {'size': 11, 'color': MUTED})]],
         align=CENTER, line=0.9)
    text(shapes, X0, 3.55, X1 - X0, 1.5, [
        [('Keeping Smart Devices Private and Honest', {'bold': True, 'size': 56})],
        [('While They Learn Together', {'bold': True, 'size': 56})],
    ], color=NAVY, align=CENTER, line=0.9, name='title')
    text(shapes, X0, 5.08, X1 - X0, 1.4, [
        [('PhD project: Privacy-Preserving Machine Learning for Next-Generation Internet of Things (NG-IoT) Security',
          {'italic': True, 'color': BLUE, 'size': 26})],
        [('Shakir Zareen', {'bold': True, 'size': 26}), (', PhD Student  ·  Faculty of Design, Informatics and Business, '
                                                         'Abertay University', {'size': 25})],
        [('Email: s.zareen2400@abertay.ac.uk   ·   Supervisors: Dr Shailendra Rathore (Primary), Dr Laith Al-Jobouri, '
          'Dr Sanaz Kavianpour', {'size': 23, 'color': MUTED})],
    ], align=CENTER, space_after=2)


# ---------------------------------------------------------------- row one

def problem(shapes, x, y, w, h):
    by = panel(shapes, x, y, w, h, 'The Problem', [('Devices learn together, ', 0), ('and some may cheat', 1)])
    ix, iw = x + PAD, w - 2 * PAD
    yy = by + 0.24
    text(shapes, ix, yy, iw, 1.45, [
        [('Everyday objects now carry sensors and go online: the ', {}), ('Internet of Things (IoT)', {'bold': True}),
         ('. ', {}), ('Machine learning (ML)', {'bold': True}),
         (' learns from what they sense, close to the devices. Much of that data is personal.', {})]], size=20, line=1.0)
    yy += 1.5
    text(shapes, ix, yy, iw, 1.15, [
        [('Federated learning', {'bold': True}),
         (' keeps the data on each device and shares only model updates, like a study group that swaps notes and keeps '
          'its diaries at home.', {})]], size=20, line=1.0)
    yy += 1.3

    # federated learning: devices with their data locked in, updates up to a server, the shared model back
    tw, th, tg = 2.2, 0.6, 0.13
    for k in range(3):
        ty = yy + k * (th + tg)
        box(shapes, ix, ty, tw, th, fill=BLUE_TINT, line=BLUE, lw=1.25, radius=0.1)
        pic(shapes, ('device_phone', 'device_laptop', 'device_bulb')[k], ix + 0.07, ty + 0.05, 0.5)
        text(shapes, ix + 0.64, ty, 1.1, th, [[(f'device {k + 1}', {'size': 17})]], anchor=MIDDLE)
        pic(shapes, 'data_locked', ix + tw - 0.5, ty + 0.08, 0.44)
    cy = yy + 1.5 * th + tg
    sw, sh = 1.8, 1.72
    sx, sy = ix + iw - sw, cy - sh / 2
    box(shapes, sx, sy, sw, sh, fill='FFFFFF', line=INK, lw=2.0, radius=0.14)
    pic(shapes, 'server', sx + (sw - 0.74) / 2, sy + 0.06, 0.74)
    text(shapes, sx + 0.05, sy + 0.8, sw - 0.1, 0.85, [[('Server', {'bold': True, 'size': 18})],
                                                      [('merges updates', {'size': 16})]], align=CENTER)
    ax0, ax1 = ix + tw + 0.12, sx - 0.12
    connector(shapes, ax0, cy - 0.32, ax1, cy - 0.32, INK, 2.75)
    text(shapes, ax0, cy - 0.78, ax1 - ax0, 0.4, [[('updates', {'size': 16})]], align=CENTER)
    connector(shapes, ax1, cy + 0.32, ax0, cy + 0.32, NAVY, 2.75)
    text(shapes, ax0, cy + 0.38, ax1 - ax0, 0.4, [[('shared model', {'size': 16, 'color': NAVY})]], align=CENTER)
    text(shapes, ix - 0.2, yy + 3 * th + 2 * tg + 0.06, tw + 0.4, 0.34,
         [[('the data stay on the device', {'italic': True, 'size': 15, 'color': GREEN})]], align=CENTER)
    yy += 3 * th + 2 * tg + 0.6

    # what can go wrong
    text(shapes, ix, yy, iw, 0.4, [[('What can go wrong', {'bold': True, 'size': 20, 'color': RED})]])
    yy += 0.5
    threats = [('leaking', 'Leaking', 'an update gives the data away'),
               ('poisoning', 'Poisoning', 'a bad update, sent on purpose'),
               ('fake_members', 'Fake members', 'one attacker, many identities'),
               ('free_riding', 'Free riding', 'takes the model, gives nothing')]
    cw, ch, cg = (iw - 0.16) / 2, 1.0, 0.13
    for k, (ic, name, line) in enumerate(threats):
        tx = ix + (k % 2) * (cw + 0.16)
        ty = yy + (k // 2) * (ch + cg)
        box(shapes, tx, ty, cw, ch, fill=RED_TINT, radius=0.1)
        pic(shapes, ic, tx + 0.1, ty + (ch - 0.6) / 2, 0.6)
        text(shapes, tx + 0.8, ty + 0.04, cw - 0.86, ch - 0.08, [[(name, {'bold': True, 'size': 18})],
                                                              [(line, {'size': 15, 'color': INK})]], anchor=MIDDLE, line=0.92)
    return yy + 2 * ch + cg


def gap(shapes, x, y, w, h):
    by = panel(shapes, x, y, w, h, 'The Gap', [('45 published designs: ', 0), ('the three rarely meet', 1)])
    ix, iw = x + PAD, w - 2 * PAD
    yy = by + 0.24
    text(shapes, ix, yy, iw, 1.45, [
        [('Many designs add a ', {}), ('blockchain', {'bold': True}),
         (', a shared record book that no single party controls, to replace or watch over the server. A systematic '
          'review of 45 such designs checked each for three things.', {})]], size=20, line=1.0)
    yy += 1.5

    # the three conditions, each named in its own box: C1 top left, C2 top right, C3 below
    lh = 0.74
    for bx, bw_, col, tint, lines in ((ix, 2.6, BLUE, BLUE_TINT, ('Cost measured', 'for edge devices')),
                                      (ix + iw - 2.95, 2.95, GREEN, GREEN_TINT, ('Updates hidden from',
                                                                                 'whoever checks or merges'))):
        box(shapes, bx, yy, bw_, lh, fill=tint, line=col, lw=1.75, radius=0.1)
        text(shapes, bx + 0.08, yy, bw_ - 0.16, lh, [[(ln, {'bold': True})] for ln in lines], size=16.5, color=col,
             align=CENTER, anchor=MIDDLE, line=0.92)

    # three conditions as three circles; the numbers are designs, from paper V90 Table XII (one design meets C2 and C3)
    d, s = 2.12, 1.22
    cx = ix + iw / 2
    top = yy + lh + 0.04
    c1 = (cx - s / 2, top + d / 2)
    c2 = (cx + s / 2, top + d / 2)
    c3 = (cx, top + d / 2 + s * math.sqrt(3) / 2)
    circles = [(c1, BLUE), (c2, GREEN), (c3, RED)]
    for (ccx, ccy), col in circles:
        box(shapes, ccx - d / 2, ccy - d / 2, d, d, fill=col, line=col, lw=2.5, shape=MSO_SHAPE.OVAL, opacity=0.13)
    g = ((c1[0] + c2[0] + c3[0]) / 3, (c1[1] + c2[1] + c3[1]) / 3)

    def at(px, py, label, color, size=26):
        text(shapes, px - 0.4, py - 0.27, 0.8, 0.54, [[(label, {'bold': True, 'color': color, 'size': size})]],
             align=CENTER, anchor=MIDDLE)

    for (ccx, ccy), col in circles:                          # the designs meeting one condition only
        vx, vy = ccx - g[0], ccy - g[1]
        n = math.hypot(vx, vy)
        at(ccx + vx / n * 0.53, ccy + vy / n * 0.53, {BLUE: '6', GREEN: '6', RED: '12'}[col], col, 30)
    mx, my = (c2[0] + c3[0]) / 2, (c2[1] + c3[1]) / 2       # the one design meeting two
    vx, vy = mx - c1[0], my - c1[1]
    n = math.hypot(vx, vy)
    at(mx + vx / n * 0.38, my + vy / n * 0.38, '1', INK, 24)
    pic(shapes, 'gap', g[0] - 0.4, g[1] - 0.42, 0.8)      # where all three meet: what this PhD aims at
    rb_w, rb_y = 3.0, c3[1] + d / 2 + 0.08
    box(shapes, c3[0] - rb_w / 2, rb_y, rb_w, 0.46, fill=RED_TINT, line=RED, lw=1.75, radius=0.1)
    text(shapes, c3[0] - rb_w / 2, rb_y, rb_w, 0.46, [[('Tested against attacks', {'bold': True})]], size=16.5,
         color=RED, align=CENTER, anchor=MIDDLE)
    # the key
    ky = rb_y + 0.56
    pic(shapes, 'gap', ix - 0.02, ky - 0.02, 0.56)
    text(shapes, ix + 0.62, ky, 3.6, 0.66, [[('The gap: all three together.', {'bold': True})],
                                           [('This PhD aims there.', {'bold': True})]], size=16, color=NAVY, line=0.92)
    text(shapes, ix + 4.1, ky, iw - 4.1, 0.66, [[('Numbers', {})], [('count designs', {})]],
         size=15, color=MUTED, align=PP_ALIGN.RIGHT, line=0.92)
    yy = ky + 0.7

    # the reason
    bw = (iw - 0.62) / 2
    bh = 1.14
    for k, (head, line, col, tint, ic) in enumerate((
            ('PRIVACY SAYS', 'Nobody may look at an update.', GREEN, GREEN_TINT, 'privacy'),
            ('SECURITY SAYS', 'Someone must check every update.', RED, RED_TINT, 'security'))):
        bx = ix + k * (bw + 0.62)
        box(shapes, bx, yy, bw, bh, fill=tint, line=col, lw=2.0, radius=0.12)
        pic(shapes, ic, bx + 0.12, yy + 0.07, 0.48)
        text(shapes, bx + 0.62, yy + 0.1, bw - 0.7, 0.42, [[(head, {'bold': True, 'size': 15, 'color': col})]],
             anchor=MIDDLE)
        text(shapes, bx + 0.14, yy + 0.56, bw - 0.28, 0.7, [[(line, {'bold': True, 'size': 18})]], line=0.95)
    disc(shapes, ix + bw + 0.08, yy + bh / 2 - 0.23, 0.46, 'vs', 'FFFFFF', color=NAVY, line=NAVY, size=16)
    return yy + bh


def idea(shapes, x, y, w, h):
    by = panel(shapes, x, y, w, h, 'The Idea', [('Check every update ', 0), ('without seeing it', 1)])
    ix, iw = x + PAD, w - 2 * PAD
    yy = by + 0.24
    text(shapes, ix, yy, iw, 1.05, [
        [('The aim: devices that learn together while ', {}),
         ('every update is checked for cheating and nobody sees one whole.', {'bold': True})]], size=20, line=1.0)
    yy += 1.08

    # the layered design (paper V90, Fig. 7, in plain words): layer names outside at the right
    lw = iw - 0.62
    nx = ix + lw + 0.12
    layers = [('Blockchain', GOLD, GOLD_TINT, 1.32), ('Validators', GREEN, GREEN_TINT, 1.62), ('Gateways', BLUE, BLUE_TINT, 1.36)]
    gapy = 0.8
    tops = []
    ly = yy
    for name, col, tint, hh in layers:
        box(shapes, ix, ly, lw, hh, fill=tint, line=col, lw=2.0, radius=0.14, name=f'layer {name}')
        vlabel(shapes, nx, ly, 0.5, hh, name, col)
        tops.append(ly)
        ly += hh + gapy
    tx = ix + 2.25
    # blockchain: a chain of blocks
    b_y = tops[0]
    for k in range(3):
        bx = ix + 0.18 + k * 0.66
        if k:
            connector(shapes, bx - 0.13, b_y + 0.66, bx + 0.03, b_y + 0.66, GOLD, 2.5, head=False)
        pic(shapes, 'block', bx, b_y + 0.38, 0.56)
    text(shapes, tx, b_y, lw - 2.35, 1.32, [[('Keeps only fingerprints', {'bold': True, 'color': GOLD, 'size': 17})],
                                           [('and verdicts; nothing personal', {'size': 16})]], anchor=MIDDLE, line=0.95)
    # validators: a small committee, a mesh
    v_y = tops[1]
    pts = [(ix + 0.25, v_y + 0.2), (ix + 1.3, v_y + 0.2), (ix + 0.25, v_y + 0.92), (ix + 1.3, v_y + 0.92)]
    nd = 0.52
    for i in range(4):
        for j in range(i + 1, 4):
            connector(shapes, pts[i][0] + nd / 2, pts[i][1] + nd / 2, pts[j][0] + nd / 2, pts[j][1] + nd / 2, '8FB9A0',
                      1.75, head=False)
    for px, py in pts:
        box(shapes, px - 0.03, py - 0.03, nd + 0.06, nd + 0.06, fill='FFFFFF', line=GREEN, lw=1.5, radius=0.1)
        pic(shapes, 'validator', px + 0.02, py + 0.02, nd - 0.04)
    text(shapes, tx, v_y, lw - 2.35, 1.62, [[('Mark the quiz and add up', {'bold': True, 'color': GREEN, 'size': 17})],
                                           [('the updates, all in pieces; none sees one whole', {'size': 16})]],
         anchor=MIDDLE, line=0.95)
    # gateways: they learn; one cheats
    g_y = tops[2]
    for k in range(3):
        box(shapes, ix + 0.14 + k * 0.62, g_y + 0.42, 0.56, 0.56, fill='FFFFFF', line=BLUE, lw=1.25, radius=0.1)
        pic(shapes, 'gateway', ix + 0.16 + k * 0.62, g_y + 0.44, 0.52)
    bug_x, bug_y = ix + 0.2 + 2 * 0.62 + 0.3, g_y + 0.16
    pic(shapes, 'attacker', bug_x - 0.04, bug_y - 0.04, 0.4)
    text(shapes, tx, g_y, lw - 2.35, 1.36, [[('Learn on their own', {'bold': True, 'color': BLUE, 'size': 17})],
                                           [('devices’ data; a few may cheat', {'size': 16})]], anchor=MIDDLE, line=0.95)
    # what goes up and down between the layers
    for k, up in enumerate(('fingerprint and verdict', 'update and quiz answers, in pieces')):
        top = tops[k] + layers[k][3]
        block_arrow(shapes, ix + 0.42, top + 0.13, 0.4, gapy - 0.26, True, INK)
        block_arrow(shapes, ix + 0.96, top + 0.13, 0.4, gapy - 0.26, False, NAVY)
        text(shapes, ix + 1.55, top + 0.08, lw - 1.6, gapy - 0.16,
             [[('up: ' + up, {'size': 15, 'italic': True})], [('down: the new model', {'size': 15, 'italic': True,
                                                                                      'color': NAVY})]],
             anchor=MIDDLE, line=0.95)
    yy = ly - gapy + 0.22
    # the one open element, called out from the cheating gateway
    box(shapes, ix, yy, iw, 0.84, fill=RED_TINT, line=RED, lw=2.0, radius=0.12, name='callout open element')
    pic(shapes, 'open_issue', ix + 0.14, yy + 0.13, 0.56)
    text(shapes, ix + 0.82, yy + 0.02, iw - 0.95, 0.8, [[('Still open: ', {'bold': True, 'color': RED}),
                                                         ('a hidden backdoor', {'bold': True})],
                                                        [('can get past the quiz.', {'bold': True})]],
         size=18, anchor=MIDDLE, line=0.92)
    gx = ix + 0.2 + 2 * 0.62 + 0.26
    connector(shapes, gx, g_y + 1.0, gx, yy, RED, 1.75, head=False, dash=True)
    return yy + 0.84


# ---------------------------------------------------------------- row two

def band(shapes, y, label):
    box(shapes, X0, y, X1 - X0, 0.56, fill=NAVY, radius=0.28, name='band')
    text(shapes, X0, y, X1 - X0, 0.56, [[(label, {'bold': True, 'color': 'FFFFFF', 'size': 28})]], align=CENTER,
         anchor=MIDDLE)
    return y + 0.56


def steps(shapes, x, y, w, h):
    by = panel(shapes, x, y, w, h, 'How the Check Works: One Round')
    ix, iw = x + PAD, w - 2 * PAD
    cards = [('01', 'Learn', 'learn', BLUE, BLUE_TINT,
              'Each gateway trains on its own devices’ data, which never leaves it.'),
             ('02', 'Split', 'split', GREEN, GREEN_TINT,
              'Its update and quiz answers are cut into random-looking pieces (secret shares), one per validator.'),
             ('03', 'Mark', 'mark', GREEN, GREEN_TINT,
              'Validators mark the answers to test questions with known answers, working on the pieces.'),
             ('04', 'Merge', 'add_up', GREEN, GREEN_TINT,
              'Updates that score well are added up, still in pieces. Poor scorers are left out.'),
             ('05', 'Record', 'record', GOLD, GOLD_TINT,
              'The blockchain records each update’s fingerprint and the verdict. The new model goes back.')]
    ag = 0.36
    cw = (iw - 4 * ag) / 5
    ct, chh = by + 0.58, 3.3
    for k, (num, title, ic, col, tint, line) in enumerate(cards):
        cx = ix + k * (cw + ag)
        box(shapes, cx, ct, cw, chh, fill=tint, line=col, lw=2.0, radius=0.16)
        disc(shapes, cx + (cw - 0.62) / 2, ct - 0.31, 0.62, num, NAVY, line='FFFFFF', size=18)
        text(shapes, cx, ct + 0.33, cw, 0.42, [[(title, {'bold': True, 'size': 21, 'color': col})]], align=CENTER)
        pic(shapes, ic, cx + (cw - 0.62) / 2, ct + 0.76, 0.62)
        text(shapes, cx + 0.1, ct + 1.4, cw - 0.2, chh - 1.45, [[(line, {'size': 16})]], align=CENTER, line=0.98)
        if k < 4:
            ch = shapes.add_shape(MSO_SHAPE.CHEVRON, E(cx + cw + 0.09), E(ct + chh / 2 - 0.2), E(0.2), E(0.4))
            ch.fill.solid()
            ch.fill.fore_color.rgb = rgb(NAVY)
            ch.line.fill.background()
            ch.shadow.inherit = False
    # who sees what
    sy = ct + chh + 0.18
    box(shapes, ix, sy, iw, 0.84, fill=NAVY_TINT, radius=0.12)
    text(shapes, ix + 0.2, sy, 1.5, 0.84, [[('WHO SEES', {'bold': True})], [('WHAT', {'bold': True})]], size=16,
         color=NAVY, anchor=MIDDLE, line=0.95)
    seen = [('gateway', BLUE, 'A gateway', 'its own data'), ('split', GREEN, 'A validator', 'one random-looking piece'),
            ('record', GOLD, 'The blockchain', 'a fingerprint, a verdict')]
    widths = [2.75, 3.45, iw - 1.65 - 2.75 - 3.45]
    for k, (ic, col, who, what) in enumerate(seen):
        sx, sw = ix + 1.65 + sum(widths[:k]), widths[k]
        box(shapes, sx - 0.02, sy + 0.12, 0.6, 0.6, fill='FFFFFF', radius=0.1)
        pic(shapes, ic, sx + 0.02, sy + 0.16, 0.52)
        text(shapes, sx + 0.6, sy + 0.02, sw - 0.65, 0.8, [[(who, {'bold': True, 'size': 17, 'color': col})],
                                                          [(what, {'size': 16})]], anchor=MIDDLE, line=0.95)
    return sy + 0.84


def plan(shapes, x, y, w, h):
    by = panel(shapes, x, y, w, h, 'How It Will Be Tested')
    ix, iw = x + PAD, w - 2 * PAD
    rows = [('measured', NAVY, NAVY_TINT, 'Measured', [
                'Accuracy of the shared model',
                'Time, memory and data sent',
                'Attackers caught, and the harm the rest do']),
            ('compared', NAVY, NAVY_TINT, 'Compared with', [
                'Plain federated learning in the same simulator',
                'Six published designs with open code [1]–[6]']),
            ('attacker', RED, RED_TINT, 'Attacked by', [
                'Poisoning, a hidden backdoor among it',
                'Fake members and free riders',
                'Published attacks, at a stated share of attackers']),
            ('run_on', BLUE, BLUE_TINT, 'Run on', [
                'A simulated edge network with a 5G link',
                'Gateways and blockchain nodes in the simulator'])]
    lab = 2.3
    rg = 0.16
    avail = h - (by - y) - 0.26 - 0.22 - rg * (len(rows) - 1)
    weights = [len(r[4]) + 0.7 for r in rows]
    yy = by + 0.26
    for ic, col, tint, head, lines in rows:
        rh = avail * (len(lines) + 0.7) / sum(weights)
        box(shapes, ix, yy, iw, rh, fill='FFFFFF', line=RULE, lw=1.25, radius=0.1)
        box(shapes, ix, yy, lab, rh, fill=tint, radius=0.1)
        pic(shapes, ic, ix + 0.13, yy + (rh - 0.56) / 2, 0.56)
        text(shapes, ix + 0.78, yy, lab - 0.84, rh, [[(head, {'bold': True, 'size': 19, 'color': col})]], anchor=MIDDLE,
             line=0.92)
        text(shapes, ix + lab + 0.2, yy, iw - lab - 0.3, rh, [B((ln, {}), color=col) for ln in lines], size=17,
             anchor=MIDDLE, space_after=2, line=0.98)
        yy += rh + rg
    return yy - rg


# ---------------------------------------------------------------- row three

def matters(shapes, x, y, w, h):
    by = panel(shapes, x, y, w, h, 'Why It Matters')
    ix, iw = x + PAD, w - 2 * PAD
    yy = by + 0.26
    groups = [('For people and organisations', 'people', [
                  'Raw data stay where they are collected, and no single party sees an update.',
                  'A model built from sensitive data that others can still trust.',
                  'Nothing personal on the blockchain, as the European Data Protection Board advises.']),
              ('For researchers', 'research', [
                  'Costs measured at the edge, in a simulator with 5G.',
                  'The same published attacks, run against every design compared.'])]
    for head, ic, lines in groups:
        pic(shapes, ic, ix - 0.02, yy - 0.02, 0.52)
        text(shapes, ix + 0.58, yy, iw - 0.58, 0.48, [[(head, {'bold': True, 'size': 21, 'color': NAVY})]],
             anchor=MIDDLE)
        yy += 0.58
        n = sum(1 + len(t) // 50 for t in lines)
        hh = n * 0.3 + (len(lines) - 1) * 0.08
        text(shapes, ix, yy, iw, hh, [B((t, {})) for t in lines], size=18, space_after=5, line=0.98)
        yy += hh + 0.3
    return yy


def roadmap(shapes, x, y, w, h):
    by = panel(shapes, x, y, w, h, 'The Road Ahead')
    ix, iw = x + PAD, w - 2 * PAD
    stages = [('DONE', NAVY, 'Systematic review', '45 published designs read; the gap found.'),
              ('DONE', NAVY, 'First test', 'Published code [2], run as released, let every attacker in; a '
                                           'quiz-style check caught every fake member.'),
              ('NOW', GOLD, 'Baselines', 'Six published designs with open code [1]–[6], chosen to re-run.'),
              ('NEXT', BLUE, 'Test-bed', 'A simulated edge network with a 5G link; plain federated learning first.'),
              ('THEN', RED, 'Build and attack', 'Add the check part by part, measure its cost, then attack it.')]
    d = 0.4
    lx = ix + 0.2
    tw = iw - d - 0.45
    heights = [0.42 + math.ceil(len(line) / 52) * 0.255 for *_, line in stages]   # a title line, then the text
    top, bottom = by + 0.26, y + h - 0.18
    g = (bottom - top - sum(heights)) / (len(stages) - 1)
    ys = [top + sum(heights[:k]) + k * g for k in range(len(stages))]
    connector(shapes, lx + d / 2, ys[0] + d / 2, lx + d / 2, ys[-1] + d / 2, LINE, 3.5, head=False)
    for sy, hh, (tag, col, title, line) in zip(ys, heights, stages):
        filled = tag in ('DONE', 'NOW')
        box(shapes, lx, sy, d, d, fill=col if filled else 'FFFFFF', line=col, lw=3.0, shape=MSO_SHAPE.OVAL)
        text(shapes, lx + d + 0.25, sy - 0.06, tw, 0.48,
             [[(tag + '  ', {'bold': True, 'size': 15, 'color': col}), (title, {'bold': True, 'size': 19})]], anchor=MIDDLE)
        text(shapes, lx + d + 0.25, sy + 0.4, tw, hh - 0.38, [[(line, {'size': 16, 'color': INK})]], line=0.98)
    return ys[-1] + heights[-1]


def open_questions(shapes, x, y, w, h):
    by = panel(shapes, x, y, w, h, 'Open Questions')
    ix, iw = x + PAD, w - 2 * PAD
    items = [('backdoor', RED, 'A hidden backdoor', ' keeps every label honest yet passes the quiz. Rarer quiz questions '
                                               'and a sturdier merge come next.'),
             ('zk_proofs', GREEN, 'Zero-knowledge proofs', ' [1]–[6] could prove a check ran without showing any data, if they '
                                                             'fit small devices.'),
             ('erasure', GOLD, 'Erasure.', ' A blockchain resists deletion, so erasure is part of the design.')]
    # let's talk, at the foot of the panel: a question for the reader and a QR code that writes the email
    th, qs = 1.6, 1.36
    ty = y + h - 0.26 - th
    box(shapes, ix, ty, iw, th, fill=NAVY, radius=0.14, name="let's talk")
    qr(shapes, QUESTION_PAGE, ix + 0.16, ty + (th - qs) / 2, qs, error='m')
    tx = ix + 0.16 + qs + 0.24
    text(shapes, tx, ty + 0.08, ix + iw - tx - 0.16, th - 0.16, [
        [('LET’S TALK', {'bold': True, 'color': SUN, 'size': 16})],
        [('Where in your field must someone check data they may not see?', {'color': 'FFFFFF', 'bold': True})],
        [('Scan the code: one tap opens your email, ready for your question.', {'color': 'C9D6E3', 'size': 15})]],
        size=17.5, anchor=MIDDLE, space_after=3, line=0.95)
    # the questions, spread over the space above it
    heights = [max(0.56, math.ceil((len(lead) + len(rest)) / 46) * 0.285) for _, _, lead, rest in items]
    top, bottom = by + 0.26, ty - 0.24
    spare = (bottom - top - sum(heights)) / (len(items) - 1)
    yy = top
    for (ic, col, lead, rest), hh in zip(items, heights):
        pic(shapes, ic, ix, yy + 0.0, 0.56)
        text(shapes, ix + 0.7, yy, iw - 0.7, hh, [[(lead, {'bold': True}), (rest, {})]], size=16.5, line=0.98)
        yy += hh + spare
    return ty + th


REFERENCES = [   # the six designs carried forward to Phase 2 (Docs/PHASE2-DESIGNS-V3-2026-11-16.html), "et al." beyond three authors
    'C. Fan, A. Sohrabbeig, and P. Musilek, “Zero-knowledge machine learning models for blockchain peer-to-peer energy '
    'trading,” Internet of Things, vol. 32, Art. no. 101638, 2025.',
    'W. M. Alwash et al., “FL-BC-IDS: Evidence-Native Privacy-Aware Hierarchical Federated Intrusion Detection for the '
    'Internet of Vehicles,” Sensors, vol. 26, no. 17, Art. no. 5400, 2026.',
    'X. Wei et al., “PoL-BFL: Towards Trustworthy Federated Learning with Zero-Knowledge Proofs and Verifiable Incentives,” '
    'in Proc. ACM SIGKDD Conf. Knowledge Discovery and Data Mining (KDD), 2026, pp. 5291–5302.',
    'H. Lycklama et al., “RoFL: Robustness of Secure Federated Learning,” in Proc. IEEE Symp. Security and Privacy (S&P), '
    '2023, pp. 453–476.',
    'S. Garg et al., “Experimenting with Zero-Knowledge Proofs of Training,” in Proc. ACM SIGSAC Conf. Computer and '
    'Communications Security (CCS), 2023, pp. 1880–1894.',
    'J. Ramanan, G. Haldeman, and N. Apthorpe, “zk-DEAP: A Zero-Knowledge Decentralized Encrypted Aggregation Protocol,” '
    'arXiv:2611.10020, 2026.',
]


def references(shapes, y, h):
    """the numbered references in three columns, beside a navy label running upwards"""
    box(shapes, X0, y, X1 - X0, h, fill='FFFFFF', line=RULE, lw=1.75, shape=MSO_SHAPE.RECTANGLE, name='references')
    box(shapes, X0, y, 0.5, h, fill=NAVY, shape=MSO_SHAPE.RECTANGLE)
    tb = text(shapes, X0, y, 0.5, h, [[('REFERENCES', {'bold': True, 'color': 'FFFFFF', 'size': 13})]], align=CENTER,
              anchor=MIDDLE)
    tb.text_frame._txBody.find(qn('a:bodyPr')).set('vert', 'vert270')
    cols = [[1, 2], [3, 4], [5, 6]]
    cx0, cg = X0 + 0.72, 0.3
    cw = (X1 - 0.2 - cx0 - 2 * cg) / 3
    for k, nums in enumerate(cols):
        text(shapes, cx0 + k * (cw + cg), y + 0.1, cw, h - 0.2,
             [[(f'[{n}] ', {'bold': True, 'color': NAVY}), (REFERENCES[n - 1], {})] for n in nums],
             size=12.5, color=INK, anchor=MIDDLE, space_after=3, line=0.96)
    return y + h


def closing(shapes, y):
    box(shapes, X0, y, X1 - X0, 0.8, fill=NAVY, radius=0.14, name='takeaway')
    text(shapes, X0 + 0.4, y, X1 - X0 - 0.8, 0.8, [[(
        'If every update can be checked without being seen, smart devices can learn together and stay private and honest.',
        {'bold': True, 'color': SUN})]], size=26, align=CENTER, anchor=MIDDLE)
    return y + 0.8


# ---------------------------------------------------------------- build

def build(version, folder=FOLDER):
    out = pathlib.Path(folder) / f'Zareen-Winter-Conference-2026-Poster-V{version}.pptx'
    if out.exists():
        sys.exit(f'{out.name} exists; a new build takes the next version number')
    prs = Presentation(str(TEMPLATE))
    slide = prs.slides[0]
    for shp in list(slide.shapes):                 # the template's sample title and sections
        shp._element.getparent().remove(shp._element)
    shapes = slide.shapes
    header(shapes)
    cols3 = [X0 + k * (COL3 + GUT) for k in range(3)]
    r1, h1 = 6.55, 9.62
    ends = [problem(shapes, cols3[0], r1, COL3, h1), gap(shapes, cols3[1], r1, COL3, h1), idea(shapes, cols3[2], r1, COL3, h1)]
    y = band(shapes, r1 + h1 + 0.16, 'What’s Next') + 0.16
    w2a = 11.45
    h2 = 5.75
    ends += [steps(shapes, X0, y, w2a, h2), plan(shapes, X0 + w2a + GUT, y, X1 - X0 - w2a - GUT, h2)]
    y += h2 + 0.2
    h3 = 5.55
    ends += [matters(shapes, cols3[0], y, COL3, h3), roadmap(shapes, cols3[1], y, COL3, h3),
             open_questions(shapes, cols3[2], y, COL3, h3)]
    refs_end = references(shapes, y + h3 + 0.2, 1.4)
    end = closing(shapes, refs_end + 0.18)
    cp = prs.core_properties
    cp.title = 'Keeping Smart Devices Private and Honest While They Learn Together'
    cp.author = 'Shakir Zareen'
    cp.subject = 'PGRS Winter Conference 2026 poster (A1 portrait, Abertay Blueberry template)'
    prs.save(str(out))
    print(f'wrote {out}; content ends at {end:.2f} in (panel ends 31.24 in)')
    panels = ['problem', 'gap', 'idea', 'steps', 'plan', 'matters', 'roadmap', 'open questions']
    bottoms = [r1 + h1] * 3 + [y - 0.2] * 2 + [y + h3] * 3
    for name, e, b in zip(panels, ends, bottoms):
        if e > b - 0.12:
            print(f'  overflow: {name} content ends {e:.2f}, panel ends {b:.2f}')


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or not args[0].isdigit() or (len(args) > 1 and (len(args) != 3 or args[1] != '--out')):
        sys.exit(__doc__)
    build(int(args[0]), args[2] if len(args) == 3 else FOLDER)
