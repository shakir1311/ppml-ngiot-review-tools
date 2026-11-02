#!/usr/bin/env python3
"""Free icons for the paper's figures: a Tabler Icons outline icon (MIT; copies with the licence in
myliteraturereviewpaper/ppml2026/icons/tabler/) placed into one of our SVG figures as plain stroked paths.

The icon's paths (relative commands, arcs) are flattened into absolute M/L polylines, so that both renderers of the
figures draw them the same: headless Chrome for the PNG, and figures_pptx.py, which reads M/L/C paths only, for the
editable deck. The icon sits on a 24-unit grid; `icon(name, x, y, size, color)` scales it to `size` px at (x, y).

Usage (from a figure module): import icons; body.append(icons.icon('router', 80, 120, 46, '#6C8EBF'))
"""
import math, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIR = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'icons' / 'tabler'
_TOK = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')


def _arc(p0, rx, ry, phi, fa, fs, p1, n=14):
    """points along an SVG elliptical arc from p0 to p1 (implementation notes F.6.5 of the SVG specification)"""
    (x1, y1), (x2, y2) = p0, p1
    if rx == 0 or ry == 0 or (x1, y1) == (x2, y2):
        return [p1]
    rx, ry, phi = abs(rx), abs(ry), math.radians(phi)
    c, s = math.cos(phi), math.sin(phi)
    xp = c * (x1 - x2) / 2 + s * (y1 - y2) / 2
    yp = -s * (x1 - x2) / 2 + c * (y1 - y2) / 2
    lam = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    den = rx * rx * yp * yp + ry * ry * xp * xp
    coef = (1 if fa != fs else -1) * math.sqrt(max(0.0, num / den)) if den else 0.0
    cxp, cyp = coef * rx * yp / ry, -coef * ry * xp / rx
    cx = c * cxp - s * cyp + (x1 + x2) / 2
    cy = s * cxp + c * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        d = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return d
    t1 = ang(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    dt = ang((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    if fs and dt < 0:
        dt += 2 * math.pi
    pts = []
    for k in range(1, n + 1):
        t = t1 + dt * k / n
        pts.append((cx + rx * math.cos(t) * c - ry * math.sin(t) * s, cy + rx * math.cos(t) * s + ry * math.sin(t) * c))
    return pts


def _bezier(p0, ctrl, p1, n=12):
    pts = []
    for k in range(1, n + 1):
        t = k / n
        if len(ctrl) == 2:
            (x1, y1), (x2, y2) = ctrl
            x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3 * p1[0]
            y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3 * p1[1]
        else:
            (x1, y1), = ctrl
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * x1 + t * t * p1[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * y1 + t * t * p1[1]
        pts.append((x, y))
    return pts


def flatten(d):
    """an SVG path as a list of subpaths, each a list of absolute points"""
    tok = _TOK.findall(d)
    subs, cur, pos, start, i, cmd, last_c = [], [], (0.0, 0.0), (0.0, 0.0), 0, None, None
    while i < len(tok):
        if re.match(r'[A-Za-z]', tok[i]):
            cmd = tok[i]
            i += 1
            if cmd in 'Zz':
                if cur:
                    cur.append(start)
                    subs.append(cur)
                cur, pos = [], start
                continue
        rel = cmd.islower()
        c = cmd.upper()

        def num(k):
            return float(tok[i + k])

        def pt(k, base=None):
            b = base or pos
            return (num(k) + (b[0] if rel else 0), num(k + 1) + (b[1] if rel else 0))
        if c == 'M':
            pos = pt(0)
            if cur:
                subs.append(cur)
            cur, start = [pos], pos
            i += 2
            cmd = 'l' if rel else 'L'
        elif c == 'L':
            pos = pt(0)
            cur.append(pos)
            i += 2
        elif c == 'H':
            pos = (num(0) + (pos[0] if rel else 0), pos[1])
            cur.append(pos)
            i += 1
        elif c == 'V':
            pos = (pos[0], num(0) + (pos[1] if rel else 0))
            cur.append(pos)
            i += 1
        elif c == 'C':
            c1, c2, p1 = pt(0), pt(2), pt(4)
            cur.extend(_bezier(pos, (c1, c2), p1))
            pos, last_c = p1, c2
            i += 6
        elif c == 'S':
            c1 = (2 * pos[0] - last_c[0], 2 * pos[1] - last_c[1]) if last_c else pos
            c2, p1 = pt(0), pt(2)
            cur.extend(_bezier(pos, (c1, c2), p1))
            pos, last_c = p1, c2
            i += 4
        elif c == 'Q':
            c1, p1 = pt(0), pt(2)
            cur.extend(_bezier(pos, (c1,), p1))
            pos, last_c = p1, c1
            i += 4
        elif c == 'T':
            c1 = (2 * pos[0] - last_c[0], 2 * pos[1] - last_c[1]) if last_c else pos
            p1 = pt(0)
            cur.extend(_bezier(pos, (c1,), p1))
            pos, last_c = p1, c1
            i += 2
        elif c == 'A':
            rx, ry, phi, fa, fs = num(0), num(1), num(2), int(float(tok[i + 3])), int(float(tok[i + 4]))
            p1 = pt(5)
            cur.extend(_arc(pos, rx, ry, phi, fa, fs, p1))
            pos = p1
            i += 7
        else:
            raise ValueError(f'path command {cmd!r}')
        if c not in 'CSQT':
            last_c = None
    if cur:
        subs.append(cur)
    return subs


def paths_of(name):
    """the flattened subpaths of a Tabler icon, on its 24-unit grid"""
    svg = (DIR / f'{name}.svg').read_text(encoding='utf-8')
    out = []
    for d in re.findall(r'\bd="([^"]+)"', svg):
        out.extend(flatten(d))
    return out


def icon(name, x, y, size=46, color='#52514e', sw=2.0):
    """the icon as stroked absolute M/L paths, `size` px wide, its top-left corner at (x, y)"""
    k = size / 24
    out = []
    for sub in paths_of(name):
        pts = [(x + px * k, y + py * k) for px, py in sub]
        if len(pts) == 1 or (len(pts) == 2 and abs(pts[0][0] - pts[1][0]) + abs(pts[0][1] - pts[1][1]) < 0.05):
            pts = [pts[0], (pts[0][0] + 0.3, pts[0][1])]                   # a dot: a hair-long line with round caps
        d = 'M ' + ' L '.join(f'{px:.1f} {py:.1f}' for px, py in pts)
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw * k:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
    return ''.join(out)


if __name__ == '__main__':
    import sys
    for n in sys.argv[1:] or ['router']:
        print(n, len(paths_of(n)), 'subpaths')
