#!/usr/bin/env python3
"""Render part of a page at a higher resolution, to read a table, a figure or an equation closely.

    crop_page.py <paper folder | ID> <page> [x0 y0 x1 y1] [--dpi 220] [--name table1]

x0 y0 x1 y1 are fractions of the page, from its top left corner: 0 0 1 1 is the whole page (the default),
0 0 1 0.5 its top half, 0.5 0 1 1 its right column. The image is written to <paper folder>/images/crops/
and its path is printed. The paper itself is only read.
"""
from __future__ import annotations

import argparse
import re
import sys

import fitz  # PyMuPDF

import corpus as C


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paper", help="paper folder or paper ID")
    ap.add_argument("page", type=int, help="PDF page number, from 1")
    ap.add_argument("box", nargs="*", type=float, help="x0 y0 x1 y1 as fractions of the page")
    ap.add_argument("--dpi", type=int, default=220)
    ap.add_argument("--name", default="")
    args = ap.parse_args()
    if args.box and len(args.box) != 4:
        ap.error("the box needs four numbers: x0 y0 x1 y1")
    x0, y0, x1, y1 = args.box or (0.0, 0.0, 1.0, 1.0)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        ap.error("the box must satisfy 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1")
    folder = C.resolve(args.paper)
    with fitz.open(C.pdf_of(folder)) as doc:
        if not 1 <= args.page <= doc.page_count:
            print(f"the paper has {doc.page_count} pages")
            return 2
        page = doc[args.page - 1]
        r = page.rect
        clip = fitz.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height, r.x0 + x1 * r.width, r.y0 + y1 * r.height)
        pix = page.get_pixmap(dpi=args.dpi, clip=clip)
    out = folder / "images" / "crops"
    out.mkdir(parents=True, exist_ok=True)
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", args.name).strip("-") or "-".join(f"{int(v * 100):03d}" for v in (x0, y0, x1, y1))
    target = out / f"page_{args.page:04d}_{label}.png"
    pix.save(target)
    print(f"{target}  ({pix.width} x {pix.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
