#!/usr/bin/env python3
"""Check that every figure of a built version prints its text at 8 pt or more (the standing rule on figures; Dr Kavianpour's
comment of 15 November 2026: "Ensure that all text, labels and other elements are clearly visible and sufficiently large to be
read easily"; before V91 the smallest text of every figure printed at 3 to 7 pt).

Every figure of the paper is printed two columns wide in the IEEE Access renderings, about 7 in; a text of f px on a canvas of
W px therefore prints at 504 f / W pt. For each figure the build places (build/paper-V<n>.md, the SVG beside its PNG in
build/figures/), the smallest and the median font size are reported, and the check fails when the smallest is below 8 pt.
Since 26 November 2026 (the author found a line running out of its box in Fig. 1 of V92) every line of text that sits inside a
box is measured with the font the figures render in (Helvetica Neue, Regular or Bold, through Pillow) and must fit inside the
box with 6 px to spare on each side; a line that does not is reported with its figure, its text and its overrun.
Exit code 1 on any failure.

Usage: python3 scripts/paper_ppml/check_figures.py <version> [--all]   (--all: every SVG in build/figures, placed or not)
"""
import html, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
WIDTH_IN, MIN_PT = 7.0, 8.0


FONT_FILE = '/System/Library/Fonts/HelveticaNeue.ttc'                  # the first face of figures_static.FONT, as Chrome renders it
PAD = 6


def overflows(svg_text):
    """every text line inside a box (a rect containing the line's anchor point) that is wider than the box less PAD on each side"""
    try:
        from PIL import ImageFont
    except ImportError:
        return ['(Pillow is not installed; the box-fit test was skipped)']
    rects = [tuple(float(v) for v in m) for m in re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg_text)]
    out, fonts = [], {}
    for m in re.finditer(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*font-size="([\d.]+)" font-weight="(\w+)" text-anchor="(\w+)"[^>]*>(.*?)</text>', svg_text):
        x, y, size, weight, anchor = float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4), m.group(5)
        lines = [html.unescape(re.sub(r'<[^>]+>', '', t)) for t in re.findall(r'<tspan[^>]*>(.*?)</tspan>', m.group(6))] or [html.unescape(m.group(6))]
        box = min((r for r in rects if r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3] and r[2] < 1200), key=lambda r: r[2] * r[3], default=None)
        if box is None:
            continue
        key = (size, weight)
        if key not in fonts:
            fonts[key] = ImageFont.truetype(FONT_FILE, int(round(size * 4)), index=1 if weight == 'bold' else 0)   # measured at 4x, scaled back
        for ln in lines:
            w = fonts[key].getlength(ln) / 4
            left = x - w / 2 if anchor == 'middle' else (x if anchor == 'start' else x - w)
            over = max(box[0] + PAD - left, (left + w) - (box[0] + box[2] - PAD))
            if over > 0:
                out.append(f'"{ln}" runs {over:.0f} px past its box')
    return out


def placed(version):
    md = (BUILD / f'paper-V{version}.md').read_text(encoding='utf-8')
    return [pathlib.Path(p).stem for p in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', md)]


def main(version, every=False):
    names = sorted(p.stem for p in (BUILD / 'figures').glob('*.svg')) if every else placed(version)
    fails = 0
    for name in names:
        svg = BUILD / 'figures' / f'{name}.svg'
        if not svg.exists():
            print(f'{name:16} no SVG beside the PNG'); fails += 1; continue
        s = svg.read_text(encoding='utf-8')
        m = re.search(r'viewBox="0 0 (\d+) (\d+)"', s)
        W = int(m.group(1)) if m else int(re.search(r'<svg[^>]*\bwidth="(\d+)', s).group(1))
        sizes = sorted(float(x) for x in re.findall(r'font-size="?([\d.]+)', s))
        if not sizes:
            print(f'{name:16} no text'); continue
        pt = lambda f: 504 * f / W
        lo, med = pt(sizes[0]), pt(sizes[len(sizes) // 2])
        ok = lo >= MIN_PT
        over = overflows(s)
        bad = [o for o in over if not o.startswith('(')]
        fails += (not ok) + bool(bad)
        print(f"{name:16} W={W:5} smallest {sizes[0]:5.1f} px = {lo:4.1f} pt, median {med:4.1f} pt at {WIDTH_IN:.0f} in  {'ok' if ok else 'FAIL: below 8 pt'}"
              f"{'; text fits its boxes' if not bad else '; FAIL: ' + str(len(bad)) + ' line(s) overflow'}")
        for o in over:
            print('      ', o)
    print(f'{fails} figure(s) fail' if fails else f'every figure prints its smallest text at {MIN_PT:.0f} pt or more, and every line fits its box')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(int(sys.argv[1]), '--all' in sys.argv))
