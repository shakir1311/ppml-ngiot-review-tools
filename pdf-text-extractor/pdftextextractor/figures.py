"""Figures and tables of a page, saved as images.

Tables are found by PyMuPDF's table finder; each is saved as an image of its area and, where its cells can be read, as CSV.
Figures are the raster images on the page and the clusters of vector drawing, merged where they overlap, leaving out what is a
table, a full-page background, or a rule. Each is saved as an image of its area at 200 dpi, named by page and number; a caption
next to it ("Fig. 3 …", "Table II …") is recorded with it.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

CAPTION = re.compile(r"^\s*(fig\.?|figure|table|tab\.)\s*[\dIVXL]+", re.I)


def _merge(rects: list) -> list:
    rects = [r for r in rects]
    merged = True
    while merged:
        merged = False
        out = []
        while rects:
            r = rects.pop()
            for i, o in enumerate(rects):
                if r.intersects(o) or (abs(r.y1 - o.y0) < 4 or abs(o.y1 - r.y0) < 4) and r.x0 < o.x1 and o.x0 < r.x1:
                    rects[i] = o | r
                    merged = True
                    break
            else:
                out.append(r)
        rects = out
    return rects


def caption_near(page, rect) -> str:
    """A caption line just below or above a figure or table, or ''."""
    import pymupdf
    best = ""
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        r = pymupdf.Rect(b[:4])
        text = " ".join(b[4].split())
        if CAPTION.match(text) and r.x0 < rect.x1 and rect.x0 < r.x1 and (0 <= r.y0 - rect.y1 < 40 or 0 <= rect.y0 - r.y1 < 40):
            best = text[:300]
            break
    return best


def regions(page) -> tuple[list, list]:
    """(figures, tables) of a page: [(rect, table or None)], page coordinates."""
    import pymupdf
    area = page.rect.width * page.rect.height
    tables = []
    try:
        for t in page.find_tables().tables:
            r = pymupdf.Rect(t.bbox)
            if r.width > 40 and r.height > 20:
                tables.append((r, t))
    except Exception:  # noqa: BLE001 - a page whose tables cannot be analysed has none recorded
        pass
    cands = []
    for im in page.get_image_info():
        r = pymupdf.Rect(im["bbox"]) & page.rect
        if 0.015 * area <= r.width * r.height <= 0.9 * area:
            cands.append(r)
    try:
        for r in page.cluster_drawings():
            r = pymupdf.Rect(r) & page.rect
            if r.width > 30 and r.height > 30 and 0.02 * area <= r.width * r.height <= 0.9 * area:
                cands.append(r)
    except Exception:  # noqa: BLE001
        pass
    figures = []
    for r in _merge(cands):
        if any((r & t).get_area() > 0.5 * r.get_area() for t, _ in tables):
            continue                                                # the drawing of a table
        figures.append((r, None))
    return sorted(figures, key=lambda x: (x[0].y0, x[0].x0)), sorted(tables, key=lambda x: (x[0].y0, x[0].x0))


def save(page, n: int, out: Path) -> list[dict]:
    """Save the figures and tables of page n into out/figures and out/tables; -> what was saved."""
    figs, tabs = regions(page)
    saved = []
    for kind, items in (("figure", figs), ("table", tabs)):
        folder = out / ("figures" if kind == "figure" else "tables")
        for i, (r, t) in enumerate(items, 1):
            folder.mkdir(parents=True, exist_ok=True)
            name = f"page{n:03d}_{kind}{i}"
            page.get_pixmap(dpi=200, clip=r).save(str(folder / f"{name}.png"))
            rec = {"kind": kind, "page": n, "file": f"{folder.name}/{name}.png", "bbox": [round(v, 1) for v in r],
                   "caption": caption_near(page, r)}
            if t is not None:
                try:
                    rows = t.extract()
                    with open(folder / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
                        csv.writer(fh).writerows([[("" if c is None else str(c)) for c in row] for row in rows])
                    rec["csv"] = f"{folder.name}/{name}.csv"
                except Exception:  # noqa: BLE001
                    pass
            saved.append(rec)
    return saved
