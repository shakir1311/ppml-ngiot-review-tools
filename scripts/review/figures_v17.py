#!/usr/bin/env python3
"""Figures of the V17 review, written to myliteraturereviewpaper/_src/V17/figures.

The drawings are those of figures_v16, computed from the V17 set of included studies. Only the selection diagram
differs: after the search rounds, citation searching and backward snowballing both fed studies into the review.

Usage: scripts/.venv/bin/python scripts/review/figures_v17.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tables_v17 as T17            # noqa: E402  (points tables_v16 at the V17 sources)
import figures_v16 as F             # noqa: E402
from figures_static import box, arrow, text, render, FONT, INK2, BLUE, BLUE_L, GREY, GREY_L   # noqa: E402

F.T = T17
F.FS.OUT = F.FS.ROOT / 'myliteraturereviewpaper' / '_src' / 'V17' / 'figures'
F.FS.OUT.mkdir(parents=True, exist_ok=True)


def prisma(c, first=None, screened=None, left_head=None):
    """first, screened, left_head: optional labels for the first box, the screening box and the left column (V24
    corrects them; V17 keeps its own)"""
    W, H = 1030, 800
    b = []
    for y0, hh, lab in ((20, 150, 'Identification'), (190, 420, 'Screening'), (630, 150, 'Included')):
        b.append(f'<rect x="16" y="{y0}" width="34" height="{hh}" rx="5" fill="{BLUE}"/>')
        b.append(f'<text transform="translate(38,{y0 + hh / 2}) rotate(-90)" font-family="{FONT}" font-size="14" '
                 f'font-weight="bold" fill="#ffffff" text-anchor="middle">{lab}</text>')
    L, LW, R, RW, O, OW = 66, 335, 420, 280, 735, 280
    b.append(text(L + LW / 2, 13, [left_head or 'Search rounds and snowballing'], size=12.5, fill=INK2, italic=True))
    b.append(text(O + OW / 2, 13, ['After the search rounds'], size=12.5, fill=INK2, italic=True))
    b.append(box(L, 30, LW, 120, first or ['Records retained from the', 'search rounds, January–', 'September 2026 (database',
                                           f"searches, snowballing) (n = {c['identified']})"], size=13))
    b.append(box(R, 30, RW, 120, ['Records removed before', f"screening: duplicates (n = {c['dup']});",
                                  'preprints superseded by the', f"published version (n = {c['superseded']})"],
                 fill=GREY_L, stroke=GREY, size=12.5))
    b.append(arrow(L + LW, 90, R, 90))
    b.append(arrow(L + LW / 2, 150, L + LW / 2, 215))
    b.append(box(L, 215, LW, 70, screened or ['Records screened (date, title', f"and abstract) (n = {c['screened']})"],
                 size=13))
    b.append(box(R, 215, RW, 70, [f"Records excluded (n = {c['excl_screen']}):", 'published before 2020, IC4'],
                 fill=GREY_L, stroke=GREY, size=12.5))
    b.append(arrow(L + LW, 250, R, 250))
    b.append(arrow(L + LW / 2, 285, L + LW / 2, 335))
    b.append(box(L, 335, LW, 60, [f"Reports sought for retrieval (n = {c['sought']})"], size=13))
    b.append(box(R, 335, RW, 60, ['Reports not retrieved (n = 0)'], fill=GREY_L, stroke=GREY, size=12.5))
    b.append(arrow(L + LW, 365, R, 365))
    b.append(arrow(L + LW / 2, 395, L + LW / 2, 445))
    b.append(box(L, 445, LW, 70, ['Reports assessed for eligibility', f"(full text) (n = {c['assessed']})"], size=13))
    b.append(box(R, 420, RW, 130, [f"Reports excluded (n = {c['excl_full']}):",
                                   f"retracted, EC1 (n = {c['excl_full_retracted']})",
                                   f"out of topic, IC1 (n = {c['excl_full_topic']})",
                                   f"no identifiable venue, IC3 (n = {c['excl_full_venue']})"],
                 fill=GREY_L, stroke=GREY, size=12.5))
    b.append(arrow(L + LW, 480, R, 480))
    b.append(arrow(L + LW / 2, 515, L + LW / 2, 645))
    b.append(box(O, 30, OW, 150, ['Records identified by', 'citation searching of the', f"included studies (n = {c['other_citation']})",
                                  'and by backward snowballing', f"from two surveys (n = {c['other_snowball']})"], size=13))
    b.append(arrow(O + OW / 2, 180, O + OW / 2, 445))
    b.append(box(O, 445, OW, 70, ['Reports assessed for', f"eligibility (n = {c['other_assessed']})"], size=13))
    b.append(f'<path d="M {O + OW / 2} 515 L {O + OW / 2} 695 L {L + LW + 8} 695" fill="none" stroke="{INK2}" '
             f'stroke-width="1.4"/>')
    b.append(arrow(L + LW + 9, 695, L + LW, 695))
    b.append(box(L, 645, LW, 100, [f"Studies included (n = {c['included']})", f"primary studies (n = {c['primary']})",
                                   f"secondary studies (n = {c['secondary']})"], fill=BLUE_L, stroke=BLUE, size=13.5))
    b.append(text(O + OW / 2 - 60, 772, ['IC = inclusion criterion, EC = exclusion criterion'], size=11.5,
                  fill=INK2, italic=True))
    return render('fig-prisma', W, H, ''.join(b))


def main():
    d = T17.load()
    out = [prisma(d['prisma']), F.taxonomy(d), F.architecture(), F.overview(d), F.mechanisms(d), F.challenges(d)]
    for f in out:
        print(f.name)


if __name__ == '__main__':
    main()
