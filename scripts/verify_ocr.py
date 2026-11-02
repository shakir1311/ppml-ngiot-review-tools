#!/usr/bin/env python3
"""Verify the reading text of every page against local OCR of the rendered page — what a reader sees on it.

The last step of the mechanical extraction (run_extraction.sh): extract_paper.py, ocr_scanned.py, this, check_extraction.py.
Added at the author's request, 12 October 2026: "i dont want a single mistake in full text extraction ... install whatever is
needed and do verification using local ocr where needed ... make all incorporated into the extraction pipeline so that we can
reuse it when needed". Nothing leaves the Mac: OCR is Apple Vision and, with --tesseract, Tesseract.

For every page the page is rendered (300 dpi) and read by Apple Vision line by line, with each line's box. Lines inside the
places where the page draws figures — the figures the extraction recorded, clusters of vector graphics, raster images
smaller than most of the page — are set aside for the first measure: figure labels are not running text. Then, over the
words of four letters or more that the system dictionary knows (ligatures, mathematical letters and words hyphenated at a
line end normalised; a word whose letters are only spaced apart does not count):

  missing     words of the running text that OCR sees and the page's reading text lacks, and their share;
  not visible words of the reading text that OCR sees nowhere on the page, figures included (hidden or off-page text);
  graphics    words OCR reads inside figures that the text layer does not hold (labels drawn as outlines): with --apply
              they are kept as text/variants/page_NNNN.graphics-ocr.txt, so a quotation of them can still be found;
  order       the reading text against the OCR lines of the running text in column order (left of the middle, then right
              of it, band by band between lines that span both columns): page_text.agreement, as for the other witnesses;
  prose order OCR's lines of running prose (a quarter of the page wide, six words or more, mostly words of the language),
              found in a reading by their first forty letters: the share that come in OCR's order. Two independent orders
              of the page count — Vision's lines in column order, and Tesseract's own layout analysis (blocks, paragraphs,
              lines), both on every page — and a reading's prose order is the better of the two (Vision's column order
              alone misjudges pages whose lines cross the middle). Every reading the pipeline holds is judged: the text
              layer (PyMuPDF), pdftotext's, PDFKit's and pdfminer's (read here, by its own analysis of the layout). Where the two orders back different readings and none satisfies
              both (a full-width figure or table between the columns: read column by column, or above it and then below
              it), OCR does not settle the page's order;
  image page  OCR reads at least three times the words of the text layer, and over 50: a page image under a stamp or a
              running head, whose text only OCR can give.

A page is flagged when more than 3 % of the running text OCR sees is missing (at least 10 words), when more than 10 % of the
reading text is not visible (at least 20 words), when it is an image page whose reading text is not yet OCR text, or when
the prose of its reading text is not in OCR's order (under 90 % of at least five prose lines), whatever the engines agreed
on: PyMuPDF and the readings built on its content order can agree with each other and all be out of order. With
--tesseract a second engine reads every page whose reading text is OCR text, every page flagged as missing or not visible
text (a flag stands only when Tesseract agrees), and every page whose prose order Vision's column order leaves in doubt.

Writes ocr_check.json into each paper's folder (check_extraction.py reports it). With --apply it also
  - OCRs the image pages (ocr_scanned.process with the pages named) so that OCR text stands in for them;
  - lets the reading whose prose is in OCR's order stand in for the page: where the page's reading has under 90 % of its
    prose lines in order, or another reading is better by at least 0.05 or is put in order by both of OCR's orders where the
    page's reading is by one only, the best reading (at least 95 %, or in order by both orders) that neither lacks visible
    running text nor holds text that is not visible becomes the page's reading ("reading_order_from":
    "poppler" or "pdfkit", or the text layer again) — page_text.assemble_full_text and check_extraction.py honour it;
  - marks as confirmed (confirmed_by "ocr (prose lines)") a page whose reading has its prose in OCR's order;
  - marks "unconfirmed" and "ocr_order_not_confirmed" a page that no reading puts in OCR's order, and also
    "ocr_orders_disagree" a page whose two OCR orders back different readings: text/full.txt names it,
    and the audit lists it to be read against the page render (a page the author has checked, "order_checked_by_eye", is
    left as it is);
  - keeps the text drawn as graphics as a variant of its page;
  and reassembles text/full.txt. A later extract_paper.py run recomputes the order verdicts: run this again after it.
Prints verdicts and numbers only, never the text of a paper.

    verify_ocr.py [--manifest PATH] [--ids ID ...] [--folders DIR ...] [--jobs N] [--tesseract] [--apply] [--json OUT]
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import re
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import corpus as C
import ocr_scanned as OS
import page_text as PT
from ocr_scanned import column_order, vision_lines

DPI = 300
MISSING_SHARE, MISSING_MIN = 0.03, 10
INVISIBLE_SHARE, INVISIBLE_MIN = 0.10, 20
ORDER_MIN = 0.8
PROSE_LINE_WORDS = 6        # an OCR line of at least this many words is prose, not a label or a table cell
ENGINES_WORDS_MIN = 0.95     # on a page read by OCR: prose words that Vision and Tesseract read alike
ENGINES_ORDER_MIN = 0.90     # on a page read by OCR: consecutive prose lines in the same order in Tesseract's layout analysis
PROSE_LINES_MIN = 5           # prose lines found on a page before its order is judged
LINE_ORDER_MIN = 0.90         # the share of them in the same order in the reading text
WITNESS_LINE_ORDER_MIN = 0.95 # a witness whose reading has them in order stands in where PyMuPDF's does not
WITNESS_BETTER_BY = 0.05      # ... or where its order is better than the reading's by at least this much
SHARPER_DPI = 400             # a page read by OCR whose two engines read its prose differently is read again, sharper
IMAGE_RATIO, IMAGE_MIN = 3, 50
ENGINES_SHARE, ENGINES_MIN = 0.05, 10
_DICT: set[str] | None = None


def dictionary() -> set[str]:
    global _DICT
    if _DICT is None:
        _DICT = {w.strip().lower() for w in open("/usr/share/dict/words", encoding="utf-8", errors="ignore") if len(w.strip()) >= 4}
    return _DICT


def normal(text: str) -> str:
    """NFKC (ligatures, mathematical letters, full-width forms to plain letters); words hyphenated at a line end joined."""
    return re.sub(r"(?<=[A-Za-z])[-\u00ad\u2010\u2011]\s*\n\s*(?=[a-z])", "", unicodedata.normalize("NFKC", text))


def bag(text: str) -> collections.Counter:
    d = dictionary()
    return collections.Counter(w for w in (x.lower() for x in re.findall(r"[A-Za-z]{4,}", normal(text))) if w in d)


def split_in(word_bag: collections.Counter, text: str) -> int:
    """How many of these words the text holds with their letters split by spaces or line breaks (letter-spaced or
    small-caps headings): not missing, only spaced."""
    flat = re.sub(r"[^a-z]", "", normal(text).lower())
    return sum(c for w, c in word_bag.items() if w in flat)


def prose_lines(lines: list[tuple]) -> list[tuple]:
    """The lines of running prose: a quarter of the page wide or more, six words or more, at least 60 % words of the language
    (not table rows, labels, formulas or references)."""
    def prose(l):
        toks = re.findall(r"[A-Za-z]{2,}", l[0])
        return (l[3] - l[1]) >= 0.25 and len(l[0].split()) >= 6 and bool(toks) and sum(OS.is_word(t) for t in toks) >= 0.6 * len(toks)
    return [l for l in lines if prose(l)]


def line_order(prose: list[tuple], text: str) -> tuple[int, float | None]:
    """The prose lines (in column order) found in a text by their first forty letters, and the share of them that come in the same
    order there (the longest run in order): tables, captions and footnotes placed between them do not count against it. A line
    whose start the text holds more than once (a repeated phrase, a list) tells nothing of the order and is left out."""
    import bisect
    joined = "".join(PT.words(text))
    pos = []
    for l in prose:
        k = "".join(PT.words(l[0]))[:40]
        if len(k) >= 20 and (i := joined.find(k)) >= 0 and joined.find(k, i + 1) < 0:
            pos.append(i)
    tails: list[int] = []
    for x in pos:
        j = bisect.bisect_left(tails, x)
        tails[j:j + 1] = [x]
    return len(pos), (round(len(tails) / len(pos), 3) if pos else None)


def tesseract_lines(words: list[tuple]) -> list[tuple]:
    """Tesseract's words grouped into its lines, in the order of its own layout analysis (block, paragraph, line):
    [(text, x0, y0, x1, y1, confidence)]. An order of the page found independently of the geometry of Vision's lines."""
    lines: dict = collections.OrderedDict()
    for t in words:
        lines.setdefault(t[6], []).append(t)
    return [(" ".join(t[0] for t in ws), min(t[1] for t in ws), min(t[2] for t in ws), max(t[3] for t in ws),
             max(t[4] for t in ws), sum(t[5] for t in ws) / len(ws)) for ws in lines.values()]


def prose_order(text: str, prose_v: list[tuple], prose_t: list[tuple] | None) -> dict:
    """A reading's prose-line order against two independent orders of the page: Vision's lines in column order, and Tesseract's
    lines in its own layout order. -> [found, share] for each, and "order": the better share of the two where at least five prose
    lines are found (None: too little prose). A reading in reading order agrees with at least one of them; Vision's column
    order alone misjudges pages whose lines cross the middle (a full-width figure, table or abstract)."""
    fv, ov = line_order(prose_v, text)
    ft, ot = line_order(prose_t, text) if prose_t is not None else (0, None)
    shares = [o for f, o in ((fv, ov), (ft, ot)) if f >= PROSE_LINES_MIN and o is not None]
    return {"vision": [fv, ov], "tesseract": [ft, ot], "order": max(shares) if shares else None}


READINGS = {"text layer": None, "pdftotext": "poppler", "PDFKit": "pdfkit", "pdfminer": "pdfminer",   # -> reading_order_from
            "re-ordered": "reordered"}
NAMES = {v: k for k, v in READINGS.items() if v}                                  # reading_order_from mark -> reading


def table_page(page) -> bool:
    """A page set as a table, with or without rules: its text-layer lines fall into three or more columns, each with at least a
    fifth of the lines and each at least 15 % of the page's width from the next (edges within 5 % are one: indented first
    lines do not count), and most of its lines are short (under 30 % of the page's width) — a two-column page of prose has two
    such columns and long lines. Asked only of a page whose prose order is not confirmed and whose prose is short (verify --apply):
    the order of a table's cells is not prose, and it is not judged."""
    w = page.rect.width or 1
    lines = [l["bbox"] for b in page.get_text("dict").get("blocks", []) for l in b.get("lines", [])
             if "".join(s["text"] for s in l["spans"]).strip()]
    if len(lines) < 20:
        return False
    edges = sorted(x0 / w for x0, _y0, _x1, _y1 in lines)
    groups, start = [], 0
    for i in range(1, len(edges) + 1):
        if i == len(edges) or edges[i] - edges[i - 1] > 0.05:
            groups.append((edges[start], i - start))
            start = i
    big = [x for x, k in groups if k >= 0.2 * len(lines)]
    widths = sorted((x1 - x0) / w for x0, _y0, x1, _y1 in lines)
    return (len(big) >= 3 and all(b - a >= 0.15 for a, b in zip(big, big[1:]))
            and widths[len(widths) // 2] < 0.30)


def side_by_side(page) -> list[tuple[float, float]]:
    """The heights (as shares of the page) where the text layer has a line in each column next to each other: where OCR joins
    a line across the gutter, it joined two column lines (ocr_scanned.joined_by_layout)."""
    w, h = page.rect.width or 1, page.rect.height or 1
    left, right = [], []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            x0, y0, x1, y1 = line["bbox"]
            if x1 / w < 0.52:
                left.append((y0 / h, y1 / h))
            elif x0 / w > 0.48:
                right.append((y0 / h, y1 / h))
    return [(min(a0, b0), max(a1, b1)) for a0, a1 in left for b0, b1 in right
            if min(a1, b1) - max(a0, b0) > 0.5 * min(a1 - a0, b1 - b0)]


def reordered_page(page) -> str:
    """The text layer's own lines — every character as PyMuPDF holds it — in the order of the page's layout: band by band between
    the lines that span both columns, the left column of a band before its right one. Its column order is the geometry OCR's
    column order uses too, so only Tesseract's layout analysis may confirm it."""
    w, h = page.rect.width or 1, page.rect.height or 1
    lines = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"])
            if text.strip():
                x0, y0, x1, y1 = line["bbox"]
                lines.append((text, x0 / w, y0 / h, x1 / w, y1 / h, 1.0))
    return "\n".join(l[0] for l in column_order(lines))


def letters(text: str) -> collections.Counter:
    return collections.Counter(c for c in unicodedata.normalize("NFKC", text).lower() if c.isalnum())


def pdfminer_pages(pdf: Path, count: int) -> list[str] | None:
    """pdfminer's reading of every page, by its own analysis of the layout (its text boxes in its order): a fourth reading, from
    a layout analysis of its own, where neither pdftotext's nor PDFKit's has the prose in OCR's order. None when it cannot
    read the file."""
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LAParams, LTTextContainer
        out = ["".join(el.get_text() for el in layout if isinstance(el, LTTextContainer))
               for layout in extract_pages(str(pdf), laparams=LAParams())]
        lig = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st"}
        fix = lambda t: "".join(lig.get(c, c) for c in t).replace("\u00ad", "")    # ligatures to letters, soft hyphens out
        return ([fix(t) for t in out] + [""] * count)[:count]
    except Exception:  # noqa: BLE001 - a file pdfminer cannot read: the other readings stand
        return None


def backed(v: dict) -> int:
    """How many of OCR's two orders of the page (each with at least five prose lines found) put a reading's prose in order."""
    return sum(1 for f, o in (v["vision"], v["tesseract"]) if f >= PROSE_LINES_MIN and (o or 0) >= LINE_ORDER_MIN)


def orders_disagree(readings: dict) -> bool:
    """OCR's two orders back different readings and none satisfies both: one reading is in order only by Vision's column order,
    another only by Tesseract's layout analysis (a full-width figure or table between the columns: read column by column, or
    above it and then below it). The page's order is then not settled by OCR."""
    def only(a, b):
        return any(v[a][0] >= PROSE_LINES_MIN and (v[a][1] or 0) >= LINE_ORDER_MIN and v[b][0] >= PROSE_LINES_MIN
                   and (v[b][1] or 0) < LINE_ORDER_MIN for v in readings.values())
    return only("vision", "tesseract") and only("tesseract", "vision") and not any(backed(v) == 2 for v in readings.values())


def engines_on_prose(vlines: list[tuple], twords: list[tuple]) -> dict:
    """Vision against Tesseract on the prose of a page read by OCR, line by line by position: each Vision line of prose width
    (a quarter of the page or more, five words or more; labels and table cells are short) is matched with the Tesseract words
    inside its box. -> the share of its words both engines read alike, and the share of consecutive prose lines that
    Tesseract's own layout analysis puts in the same order (an independent check of the column order)."""
    import difflib
    norm = lambda w: re.sub(r"[^a-z0-9]", "", w.lower())
    order = {}
    for t in twords:
        order.setdefault(t[6], len(order))
    alike = total = 0
    seq = []
    for v in vlines:
        if (v[3] - v[1]) < 0.25 or len(v[0].split()) < 5:
            continue
        inside = sorted((t for t in twords if v[1] - 0.01 <= (t[1] + t[3]) / 2 <= v[3] + 0.01
                         and v[2] - 0.005 <= (t[2] + t[4]) / 2 <= v[4] + 0.005), key=lambda t: t[1])
        a = [norm(x) for x in v[0].split() if norm(x)]
        b = [norm(t[0]) for t in inside if norm(t[0])]
        alike += sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
        total += len(a)
        keys = collections.Counter(t[6] for t in inside)
        if keys:
            seq.append(order[keys.most_common(1)[0][0]])
    pairs = list(zip(seq, seq[1:]))
    return {"prose_words": total, "read_alike": round(alike / total, 4) if total else None,
            "order_same_as_tesseract": round(sum(1 for x, y in pairs if y >= x) / len(pairs), 4) if pairs else None}


def body_of(folder: Path, n: int, page_meta: dict) -> tuple[str, str]:
    """The page's reading text as text/full.txt holds it: the text layer, OCR text where it stands in, or pdftotext's
    PDFKit's or pdfminer's reading where it stands in for the order."""
    layer = PT.read_exact(folder / "text" / "pages" / f"page_{n:04d}.txt")
    ocr = folder / "text" / "pages_ocr" / f"page_{n:04d}.txt"
    if ocr.exists() and (len(layer.strip()) < 100 or page_meta.get("ocr_stands_in")):
        return PT.read_exact(ocr), "ocr"
    src = page_meta.get("reading_order_from")
    if src in NAMES and (folder / "text" / "variants" / f"page_{n:04d}.{src}.txt").exists():
        return PT.read_exact(folder / "text" / "variants" / f"page_{n:04d}.{src}.txt"), NAMES[src]
    return layer, "text layer"


def figure_regions(page, recorded: list) -> list[tuple]:
    """Where a page draws figures, as shares of the page: the figures the extraction recorded, the clusters of vector
    graphics, and raster images smaller than most of the page (a page that is one image is not a figure)."""
    w, h = page.rect.width, page.rect.height
    boxes = [(b[0] / w - 0.01, b[1] / h - 0.01, b[2] / w + 0.01, b[3] / h + 0.01) for b in recorded]
    try:
        boxes += [(r.x0 / w, r.y0 / h, r.x1 / w, r.y1 / h) for r in page.cluster_drawings()]
    except Exception:  # noqa: BLE001 - an older PyMuPDF without clustering: the recorded figures still count
        pass
    for im in page.get_image_info():
        x0, y0, x1, y1 = im["bbox"]
        if (x1 - x0) * (y1 - y0) < 0.6 * w * h:
            boxes.append((x0 / w, y0 / h, x1 / w, y1 / h))
    return boxes


def check_page(folder: Path, page, n: int, page_meta: dict, recorded: list, tmp: Path, use_tesseract: bool,
               miner: str | None = None, reordered: str | None = None) -> dict:
    img = tmp / f"p{n:04d}.png"
    page.get_pixmap(dpi=DPI).save(str(img))
    lines = vision_lines(img)
    regions = figure_regions(page, recorded)
    inside = lambda l: any(x0 <= (l[1] + l[3]) / 2 <= x1 and y0 <= (l[2] + l[4]) / 2 <= y1 for x0, y0, x1, y1 in regions)
    kept = [l for l in lines if not inside(l)]
    figure_lines = [l for l in lines if inside(l)]
    body, source = body_of(folder, n, page_meta)
    joined = OS.joined_by_layout(side_by_side(page)) if source != "ocr" else OS.joined_by_neighbours(lines)
    all_text = "\n".join(l[0] for l in lines)
    ocr_col = "\n".join(l[0] for l in column_order(kept, joined))
    bo, ball, bb = bag("\n".join(l[0] for l in kept)), bag(all_text), bag(body)
    lack = bo - bb
    missing = sum(lack.values()) - split_in(lack, body)                    # visible running text the reading text lacks
    unseen = bb - ball
    invisible = sum(unseen.values()) - split_in(unseen, all_text)          # reading text that OCR sees nowhere on the page
    graphics = [l for l in figure_lines if bag(l[0]) - bb]                 # text drawn as graphics, not in the text layer
    row = {"page": n, "reading_text": source, "ocr_words": sum(bo.values()), "text_words": sum(bb.values()),
           "missing": missing, "missing_share": round(missing / max(1, sum(bo.values())), 4),
           "invisible": invisible, "invisible_share": round(invisible / max(1, sum(bb.values())), 4),
           "order_agreement": PT.agreement(body, ocr_col), "order_status": page_meta.get("order_status"),
           "prose_order": PT.page_agreement(ocr_col, body),        # runs of the visible text outside figures, column order
           "figure_lines_set_aside": len(figure_lines),
           "graphics_words_not_in_text": sum(sum((bag(l[0]) - bb).values()) for l in graphics),
           "ocr_confidence": round(sum(l[5] for l in lines) / len(lines), 3) if lines else None}
    prose = prose_lines(column_order(kept, joined))
    row["prose_lines"], vision_order = line_order(prose, body)
    twords: list[tuple] | None = None

    def tess() -> list[tuple]:                                             # Tesseract reads the page once, when needed
        nonlocal twords
        if twords is None:
            twords = OS.tesseract_words(img) if use_tesseract and OS.TESSERACT else []
        return twords
    row["image_page"] = (source == "text layer" and sum(bo.values()) >= IMAGE_MIN                   # running text only: a page
                         and sum(bb.values()) * IMAGE_RATIO <= sum(bo.values()))                   # with a text-heavy figure is not one
    flag_missing = row["missing_share"] > MISSING_SHARE and missing >= MISSING_MIN
    flag_invisible = row["invisible_share"] > INVISIBLE_SHARE and invisible >= INVISIBLE_MIN
    if use_tesseract and (source == "ocr" or flag_missing or flag_invisible or row["image_page"]):
        t = OS.tesseract_text(tess()) if OS.TESSERACT else None
        if t is not None:
            bt = bag(t)
            row["tesseract"] = {"words": sum(bt.values()), "not_in_reading_text": sum((bt - bb).values()),
                                "reading_text_not_seen": sum((bb - bt).values()), "order_agreement": PT.agreement(body, t)}
            if flag_missing:            # a missing-text flag stands only when the second engine sees the missing words too
                both = (bo & bt) - bb
                miss2 = sum(both.values()) - split_in(both, body)
                row["tesseract"]["missing_confirmed"] = miss2
                flag_missing = miss2 >= MISSING_MIN and miss2 > MISSING_SHARE * max(1, sum(bo.values()))
            if flag_invisible:          # a not-visible flag stands only when the second engine does not see those words either
                unseen2 = unseen - bt
                inv2 = sum(unseen2.values()) - split_in(unseen2, t)
                row["tesseract"]["invisible_confirmed"] = inv2
                flag_invisible = inv2 >= INVISIBLE_MIN and inv2 > INVISIBLE_SHARE * max(1, sum(bb.values()))
            if source == "ocr":         # the reading text is OCR text: the two engines must agree on the prose, word and order
                eng = engines_on_prose(column_order(lines, joined), tess())
                row["tesseract"].update(eng)
                row["tesseract"]["engines_disagree"] = ((eng["read_alike"] is not None and eng["read_alike"] < ENGINES_WORDS_MIN)
                                                        or (eng["order_same_as_tesseract"] is not None
                                                            and eng["order_same_as_tesseract"] < ENGINES_ORDER_MIN))
    row["prose_line_order"] = vision_order
    if source != "ocr":     # the order of the prose, every reading against OCR's two orders of the page
        need_t = use_tesseract and OS.TESSERACT                 # both OCR orders, to see where they back different readings
        prose_t = prose_lines([l for l in tesseract_lines(tess()) if not inside(l)]) if need_t else None
        seen = ball | (bag(OS.tesseract_text(twords)) if twords else collections.Counter())
        layer = PT.read_exact(folder / "text" / "pages" / f"page_{n:04d}.txt")
        texts = {"text layer": layer, "pdftotext": PT.read_exact(folder / "text" / "variants" / f"page_{n:04d}.poppler.txt"),
                 "PDFKit": PT.read_exact(folder / "text" / "variants" / f"page_{n:04d}.pdfkit.txt"), "pdfminer": miner or ""}
        if reordered and reordered.strip() and letters(reordered) == letters(layer):
            texts["re-ordered"] = reordered                     # every character of the text layer, only its lines re-ordered
        readings = {}
        for name, text in texts.items():
            if not text.strip():
                continue
            b = bag(text)
            o = prose_order(text, prose, prose_t)
            if name == "re-ordered":                            # its column order is OCR's own geometry: Tesseract alone counts
                f, t = o["tesseract"]
                o = {"order": t if f >= PROSE_LINES_MIN else None, "vision": [0, None], "tesseract": o["tesseract"],
                     "vision_same_geometry": o["vision"]}
            readings[name] = {"order": o["order"], "vision": o["vision"], "tesseract": o["tesseract"],
                              "not_visible": sum((b - seen).values()) - split_in(b - seen, all_text),
                              "missing": sum((bo - b).values()) - split_in(bo - b, text)}
        row["readings"] = readings
        if source in readings:
            row["prose_line_order"] = readings[source]["order"]
            row["prose_lines_tesseract"] = readings[source]["tesseract"][0]
        cur_o = row["prose_line_order"]
        if cur_o is not None and cur_o < LINE_ORDER_MIN and len(prose) < 15 and table_page(page):
            row["table_page"] = True                         # a table: the order of its cells is not prose, not judged
            row["prose_line_order"] = None
    row["flags"] = [x for x, c in (("missing", flag_missing),
                                   ("invisible", flag_invisible),
                                   ("image page", row["image_page"]),
                                   ("order", ((row["prose_line_order"] is not None and row["prose_line_order"] < LINE_ORDER_MIN
                                     and (source != "ocr" or row["prose_lines"] >= PROSE_LINES_MIN))
                                    or (source != "ocr" and orders_disagree(row.get("readings") or {})
                                        and backed((row.get("readings") or {}).get(source, {"vision": [0, None], "tesseract": [0, None]})) < 2))
                                    and not page_meta.get("order_checked_by_eye") and not row.get("table_page")),
                                   ("ocr engines disagree", row.get("tesseract", {}).get("engines_disagree"))) if c]
    row["_graphics"] = "\n".join(l[0] for l in column_order(graphics))
    return row


def best_reading(row: dict) -> str | None:
    """The reading whose prose comes closest to OCR's order of the page, among those that neither lack visible running text nor
    hold text that is not visible (no more than the page's reading text, within the thresholds). A reading that both of OCR's
    orders put in order comes first; of two readings equally in order, the one also in order by the other of OCR's two orders
    wins, then the one in which more of the page's prose lines are found; then the page's own reading, then the text layer."""
    rd, now = {k: v for k, v in (row.get("readings") or {}).items() if k != "re-ordered"}, row["reading_text"]
    base = rd.get(now, {})
    ok = {k: v for k, v in rd.items() if v["order"] is not None
          and v["not_visible"] <= max(INVISIBLE_MIN, base.get("not_visible", 0))
          and v["missing"] <= base.get("missing", 0) + max(3, int(0.01 * row["ocr_words"]))}
    pref = [now] + [k for k in READINGS if k != now]
    worse = lambda v: min(o for f, o in (v["vision"], v["tesseract"]) if f >= PROSE_LINES_MIN and o is not None)
    found = lambda v: v["vision"][0] + v["tesseract"][0]                 # more of the page's prose lines found in it
    return max(ok, key=lambda k: (backed(ok[k]), ok[k]["order"], worse(ok[k]), found(ok[k]), -pref.index(k))) if ok else None


def verify(folder: Path, use_tesseract: bool, apply: bool) -> dict:
    import pymupdf
    meta_path = folder / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    pm = {p["page"]: p for p in meta.get("pages", [])}
    figs = collections.defaultdict(list)
    for f in meta.get("figure_inventory", []):
        if f.get("page") and f.get("bbox") and len(f["bbox"]) == 4:
            figs[f["page"]].append(f["bbox"])
    pdf = C.pdf_of(folder)
    doc = pymupdf.open(pdf)
    miner = pdfminer_pages(pdf, doc.page_count) or [None] * doc.page_count
    reord = [reordered_page(page) for page in doc]
    applied = {"ocr_stands_in": [], "order_confirmed_by_ocr": [], "reading_order_from_witness": [], "order_not_confirmed_by_ocr": [],
               "graphics_text_kept": []}
    changed = False
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rows = [check_page(folder, page, i + 1, pm.get(i + 1, {}), figs[i + 1], tmp, use_tesseract, miner[i], reord[i])
                for i, page in enumerate(doc)]
        if apply:
            images = [r["page"] for r in rows if r["image_page"]]
            if images:
                OS.process(folder, OS.DEFAULT_THRESHOLD, ["en-US"], False, DPI, images)
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                pm = {p["page"]: p for p in meta.get("pages", [])}
                for n in images:
                    pm[n]["ocr_stands_in"] = True               # the verification found it a page image: OCR stands in
                    applied["ocr_stands_in"].append(n)
                    rows[n - 1] = check_page(folder, doc[n - 1], n, pm[n], figs[n], tmp, use_tesseract, miner[n - 1], reord[n - 1])
                changed = True
            sharper = [r["page"] for r in rows if r["reading_text"] == "ocr"
                       and (r.get("tesseract") or {}).get("read_alike") is not None and r["tesseract"]["read_alike"] < ENGINES_WORDS_MIN]
            for n in sharper:            # a page read by OCR whose two engines read its prose differently: read again, sharper
                kept_files = {f: f.read_bytes() for f in (meta_path, folder / "text" / "full.txt", folder / "text" / "full_ocr.txt",
                                                          folder / "text" / "pages_ocr" / f"page_{n:04d}.txt",
                                                          folder / "text" / "variants" / f"page_{n:04d}.tesseract.txt") if f.exists()}
                OS.process(folder, OS.DEFAULT_THRESHOLD, ["en-US"], False, SHARPER_DPI, [n])
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                pm = {p["page"]: p for p in meta.get("pages", [])}
                again = check_page(folder, doc[n - 1], n, pm.get(n, {}), figs[n], tmp, use_tesseract, miner[n - 1], reord[n - 1])
                before, after = rows[n - 1]["tesseract"]["read_alike"], (again.get("tesseract") or {}).get("read_alike")
                if after is not None and after > before:
                    rows[n - 1] = again
                    applied.setdefault("read_again_sharper", []).append(n)
                    changed = True
                else:                                            # no better: the earlier reading is put back as it was
                    for f, data in kept_files.items():
                        f.write_bytes(data)
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    pm = {p["page"]: p for p in meta.get("pages", [])}
            for i, t in enumerate(miner):                        # pdfminer's reading of every page, kept as a variant
                if t is not None:
                    PT.write_atomic(folder / "text" / "variants" / f"page_{i + 1:04d}.pdfminer.txt", t)
            for i, t in enumerate(reord):                        # the text layer re-ordered by the layout, kept as a variant
                PT.write_atomic(folder / "text" / "variants" / f"page_{i + 1:04d}.reordered.txt", t)
            for r in rows:           # the reading order of the prose: OCR's two orders of the page decide, whatever the engines said
                n, p = r["page"], pm.get(r["page"], {})
                if r["reading_text"] == "ocr" or "readings" not in r or p.get("order_checked_by_eye"):
                    continue
                cur = r["prose_line_order"]
                if cur is None:                                  # too little prose for its order to be judged (a table, a figure)
                    if p.get("order_status") != "unconfirmed":
                        continue
                    p.update(order_status="too little text", too_little_prose=True)
                    applied.setdefault("too_little_prose", []).append(n)
                else:
                    best = best_reading(r)
                    b = r["readings"][best]["order"] if best else 0
                    rd, now = r["readings"], r["reading_text"]
                    nil = {"vision": [0, None], "tesseract": [0, None]}
                    tess = lambda v: v["tesseract"][1] if v["tesseract"][0] >= PROSE_LINES_MIN else None
                    t_ro, t_now = (tess(rd["re-ordered"]) if "re-ordered" in rd else None), tess(rd.get(now, nil))
                    if (now != "re-ordered" and t_ro is not None and t_ro >= WITNESS_LINE_ORDER_MIN and backed(rd.get(now, nil)) < 2
                            and (t_now is None or t_now < LINE_ORDER_MIN or t_ro - t_now >= WITNESS_BETTER_BY)):
                        best, b = "re-ordered", t_ro            # the text layer re-ordered by the layout, confirmed by Tesseract
                    both = best and backed(rd[best]) == 2 and backed(rd.get(now, nil)) < 2
                    if best and best != now and (best == "re-ordered" or both or (b >= WITNESS_LINE_ORDER_MIN and (cur < LINE_ORDER_MIN or b - cur >= WITNESS_BETTER_BY))):
                        if READINGS[best]:                       # a witness's reading stands in for the page
                            p["reading_order_from"] = READINGS[best]
                        else:                                    # the text layer's own reading is the one in order
                            p.pop("reading_order_from", None)
                        p.pop("ocr_order_not_confirmed", None)
                        p.pop("ocr_orders_disagree", None)
                        p.update(order_status="confirmed", confirmed_by=["ocr (prose lines)"])
                        p.setdefault("agreement", {})["ocr (prose lines)"] = b
                        applied["reading_order_from_witness"].append(n)
                    elif orders_disagree(rd):                   # OCR's two orders back different readings: the page is named
                        if p.get("ocr_orders_disagree") and p.get("order_status") == "unconfirmed":
                            continue
                        p.update(order_status="unconfirmed", ocr_order_not_confirmed=True, ocr_orders_disagree=True)
                        applied["order_not_confirmed_by_ocr"].append(n)
                    elif cur >= LINE_ORDER_MIN:
                        if p.get("order_status") == "confirmed" and not p.get("ocr_order_not_confirmed"):
                            continue
                        p.pop("ocr_orders_disagree", None)
                        p.pop("ocr_order_not_confirmed", None)
                        p.update(order_status="confirmed", confirmed_by=list(p.get("confirmed_by") or []) + ["ocr (prose lines)"])
                        p.setdefault("agreement", {})["ocr (prose lines)"] = cur
                        applied["order_confirmed_by_ocr"].append(n)
                    else:                                        # no reading puts the prose in OCR's order: the page is named
                        if p.get("ocr_order_not_confirmed") and p.get("order_status") == "unconfirmed":
                            continue
                        p.update(order_status="unconfirmed", ocr_order_not_confirmed=True)
                        applied["order_not_confirmed_by_ocr"].append(n)
                changed = True
                rows[n - 1] = check_page(folder, doc[n - 1], n, p, figs[n], tmp, use_tesseract, miner[n - 1], reord[n - 1])
            for r in rows:                                       # text drawn as graphics, kept as a variant of its page
                f = folder / "text" / "variants" / f"page_{r['page']:04d}.graphics-ocr.txt"
                if r["_graphics"].strip():
                    PT.write_atomic(f, r["_graphics"] + "\n")
                    applied["graphics_text_kept"].append(r["page"])
                elif f.exists():
                    f.unlink()
            if changed:
                PT.write_atomic(meta_path, json.dumps(meta, indent=2, ensure_ascii=False))
                PT.write_atomic(folder / "text" / "full.txt", PT.assemble_full_text(folder, meta["pages"]))
    for r in rows:
        r.pop("_graphics", None)
    rec = {"date": time.strftime("%Y-%m-%d %H:%M"), "pdf_sha256": C.sha256_of(pdf),
           "engine": "Apple Vision (VNRecognizeTextRequest, accurate)"
                     + (f"; {OS.tesseract_version() or 'Tesseract not installed'} as the second engine" if use_tesseract else ""), "dpi": DPI,
           "thresholds": {"missing_share": MISSING_SHARE, "missing_min": MISSING_MIN, "invisible_share": INVISIBLE_SHARE,
                          "invisible_min": INVISIBLE_MIN, "order_min": ORDER_MIN, "prose_lines_min": PROSE_LINES_MIN,
                          "line_order_min": LINE_ORDER_MIN, "witness_line_order_min": WITNESS_LINE_ORDER_MIN,
                          "witness_better_by": WITNESS_BETTER_BY, "image_ratio": IMAGE_RATIO, "image_min": IMAGE_MIN},
           "applied": applied, "pages": rows, "flagged": [r["page"] for r in rows if r["flags"]]}
    PT.write_atomic(folder / "ocr_check.json", json.dumps(rec, indent=1, ensure_ascii=False))
    return {"folder": str(folder), **{k: rec[k] for k in ("applied", "flagged")}, "pages": len(rows),
            "flags": {r["page"]: r["flags"] for r in rows if r["flags"]},
            "ocr_words": sum(r["ocr_words"] for r in rows), "missing": sum(r["missing"] for r in rows)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", type=Path, help="a manifest of the corpus form (default: the corpus manifest)")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--folders", nargs="*", type=Path)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--tesseract", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--json", type=Path, help="also write all results to this file")
    args = ap.parse_args()
    folders = [f.resolve() for f in args.folders or []]
    if not folders:
        papers = C.load_manifest(args.manifest)
        if args.ids:
            wanted = {i.upper() for i in args.ids}
            papers = [p for p in papers if p["id"].upper() in wanted]
        folders = [C.folder_of(p) for p in papers]
    res = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futs = {pool.submit(verify, f, args.tesseract, args.apply): f for f in folders}
        for fut in concurrent.futures.as_completed(futs):
            try:
                r = fut.result()
            except Exception as exc:  # noqa: BLE001 - one paper must not stop the others
                r = {"folder": str(futs[fut]), "error": f"{type(exc).__name__}: {exc}", "pages": 0, "flagged": [], "flags": {},
                     "applied": {}, "ocr_words": 0, "missing": 0}
            res.append(r)
            name = Path(r["folder"]).name
            print(f"{name}: " + (f"ERROR {r['error']}" if r.get("error") else
                                 f"{r['pages']} pages; flagged {len(r['flagged'])}" + (f" {r['flags']}" if r["flags"] else "")
                                 + (f"; applied {r['applied']}" if any(r['applied'].values()) else "")))
    pages = sum(r["pages"] for r in res)
    flagged = sum(len(r["flagged"]) for r in res)
    errors = sum(1 for r in res if r.get("error"))
    if args.json:
        PT.write_atomic(args.json, json.dumps({"date": time.strftime("%Y-%m-%d %H:%M"), "papers": len(res), "pages": pages,
                                               "pages_flagged": flagged, "errors": errors, "results": res}, indent=1))
    print(f"{'PASS' if not flagged and not errors else 'CHECK'}: {len(res)} papers, {pages} pages verified by OCR; flagged {flagged}; "
          f"errors {errors}; OCR saw {sum(r['ocr_words'] for r in res)} dictionary words, {sum(r['missing'] for r in res)} missing from the reading text")
    return 0 if not flagged and not errors else 1


if __name__ == "__main__":
    sys.exit(main())
