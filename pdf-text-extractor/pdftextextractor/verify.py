"""Page-by-page verification and correction, and the confidence of each page.

For every page:
  1. the reading text (MuPDF, the PDF's own order) is tallied with the other two text engines (PDFium, pdfminer) over runs of
     eight words: the engines' agreement, which is all there is when OCR is off;
  2. the page is rendered (300 dpi) and read by local OCR (Apple Vision on a Mac, RapidOCR everywhere, Tesseract where it is
     installed) — a page with a text layer by the main engine and one second engine (Tesseract where installed), every engine
     where a count comes near a limit or the page has no text layer (engines_for); lines inside figures and tables are set
     aside, and over the words of the language OCR's reading is compared with the reading text:
       missing     words of the running text that OCR sees and the reading text lacks (where two engines are installed, both
                   must see a word for it to count);
       not visible words of the reading text that no OCR engine sees anywhere on the page (hidden or off-page text);
       prose order OCR's lines of running prose found in a reading in OCR's order (tables, captions and footnotes between them
                   do not count against it), against two independent orders of the page: the main OCR engine's lines in
                   column order and, where Tesseract is installed, Tesseract's own layout analysis; the better of the two
                   counts. Every reading is judged — MuPDF's, PDFium's and pdfminer's — whatever the engines agreed on,
                   since readings that share MuPDF's content order agree with it however it runs;
  3. corrections: a page with no text layer, or whose text layer holds only a stamp over a page image, is read by OCR (the
     engines vote word by word); where MuPDF's reading has under 90 % of its prose lines in OCR's order, or another reading is
     better by at least 0.05, the best reading with at least 95 % that neither lacks visible running text nor holds text that
     is not visible stands in; a reading that both of OCR's orders put in order is preferred to one that only one of them
     does; where the two orders back different readings and none satisfies both (a full-width figure or table between the
     columns: read column by column, or above it and then below it), the page is named for a look.

Confidence of a page (0 to 1): the lowest of order (1 when OCR confirms the order of the prose, or when there is too little
prose to order; otherwise the share of prose lines in order), completeness (1 when missing text is under 3 % or under 10
words, else 1 minus its share) and visibility (1 when text that is not visible is under 10 % or under 20 words, else 1 minus
its share). For a page read by OCR: the share of prose words that another OCR engine reads alike, or the OCR confidence
where only one engine is installed.
"""
from __future__ import annotations

import bisect
import collections
import re
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from . import engines as E
from . import ocr as O

DPI = 300
SHARPER_DPI, OCR_AGREE_MIN = 400, 0.95       # a scanned page whose OCR engines agree on less is read again, sharper
MISSING_SHARE, MISSING_MIN = 0.03, 10
INVISIBLE_SHARE, INVISIBLE_MIN = 0.10, 20
PROSE_LINES_MIN, LINE_ORDER_MIN, WITNESS_LINE_ORDER_MIN, WITNESS_BETTER_BY = 5, 0.90, 0.95, 0.05
IMAGE_RATIO, IMAGE_MIN = 3, 50


@dataclass
class PageResult:
    page: int
    text: str
    source: str
    confidence: float
    metrics: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def normal(text: str) -> str:
    return re.sub(r"(?<=[A-Za-z])[-­‐‑]\s*\n\s*(?=[a-z])", "", unicodedata.normalize("NFKC", text))


def bag(text: str) -> collections.Counter:
    return collections.Counter(w for w in (x.lower() for x in re.findall(r"[A-Za-z]{4,}", normal(text))) if O.is_word(w))


def spaced(words: collections.Counter, text: str) -> int:
    flat = re.sub(r"[^a-z]", "", normal(text).lower())
    return sum(c for w, c in words.items() if w in flat)


def prose_lines(lines: list[O.Line]) -> list[O.Line]:
    def prose(l):
        toks = re.findall(r"[A-Za-z]{2,}", l.text)
        return l.x1 - l.x0 >= 0.25 and len(l.text.split()) >= 6 and bool(toks) and sum(O.is_word(t) for t in toks) >= 0.6 * len(toks)
    return [l for l in lines if prose(l)]


def line_order(prose: list[O.Line], text: str) -> tuple[int, float | None]:
    """The prose lines found in a text by their first forty letters, and the share of them that come in the same order there (the
    longest run in order). A line whose start the text holds more than once tells nothing of the order and is left out."""
    joined = "".join(E.words(text))
    pos = []
    for l in prose:
        k = "".join(E.words(l.text))[:40]
        if len(k) >= 20 and (i := joined.find(k)) >= 0 and joined.find(k, i + 1) < 0:
            pos.append(i)
    tails: list[int] = []
    for x in pos:
        j = bisect.bisect_left(tails, x)
        tails[j:j + 1] = [x]
    return len(pos), (round(len(tails) / len(pos), 3) if pos else None)


def backed(v: dict) -> int:
    """How many of OCR's orders of the page (each with at least five prose lines found) put a reading's prose in order."""
    return sum(1 for f, o in (v["columns"], v["layout"]) if f >= PROSE_LINES_MIN and (o or 0) >= LINE_ORDER_MIN)


def orders_disagree(readings: dict) -> bool:
    """OCR's two orders back different readings and none satisfies both: one reading is in order only by the column order of OCR's
    lines, another only by Tesseract's layout analysis (a full-width figure or table between the columns: read column by column,
    or above it and then below it). OCR then does not settle the page's order."""
    def only(a, b):
        return any(v[a][0] >= PROSE_LINES_MIN and (v[a][1] or 0) >= LINE_ORDER_MIN and v[b][0] >= PROSE_LINES_MIN
                   and (v[b][1] or 0) < LINE_ORDER_MIN for v in readings.values())
    return only("columns", "layout") and only("layout", "columns") and not any(backed(v) == 2 for v in readings.values())


def best_reading(readings: dict, now: str, ocr_words: int) -> str | None:
    """The reading whose prose comes closest to OCR's order of the page, among those that neither lack visible running text nor
    hold text that is not visible (no more than the page's reading, within the thresholds). A reading that both of OCR's orders
    put in order comes first; of two readings equally in order, the one also in order by OCR's other order wins, then the one in
    which more of the page's prose lines are found; then the page's own reading."""
    base = readings.get(now, {})
    ok = {k: v for k, v in readings.items() if v["order"] is not None
          and v["not_visible"] <= max(INVISIBLE_MIN, base.get("not_visible", 0))
          and v["missing"] <= base.get("missing", 0) + max(3, int(0.01 * ocr_words))}
    pref = [now] + [k for k in ("re-ordered",) if k in readings and k != now] + [k for k in readings if k not in (now, "re-ordered")]
    found = lambda v: v["columns"][0] + v["layout"][0]
    return max(ok, key=lambda k: (backed(ok[k]), ok[k]["order"], ok[k]["worse"], found(ok[k]), -pref.index(k))) if ok else None


def figure_regions(page, extra: list) -> list[tuple]:
    w, h = page.rect.width, page.rect.height
    boxes = [(r.x0 / w - 0.01, r.y0 / h - 0.01, r.x1 / w + 0.01, r.y1 / h + 0.01) for r in extra]
    try:
        boxes += [(r.x0 / w, r.y0 / h, r.x1 / w, r.y1 / h) for r in page.cluster_drawings()]
    except Exception:  # noqa: BLE001
        pass
    for im in page.get_image_info():
        x0, y0, x1, y1 = im["bbox"]
        if (x1 - x0) * (y1 - y0) < 0.6 * w * h:
            boxes.append((x0 / w, y0 / h, x1 / w, y1 / h))
    return boxes


def read_page(page, n: int, dpi: int, ocr_engines: list, notes: list) -> dict:
    """Every OCR engine's lines for the page rendered at dpi; an engine that fails is noted and left out."""
    raw: dict[str, list[O.Line]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / f"p{n}.png"
        pix = page.get_pixmap(dpi=dpi)
        pix.save(str(img))
        for e in ocr_engines:
            try:
                raw[e.name] = e.read(img, pix.width, pix.height)
            except Exception as exc:  # noqa: BLE001 - an engine that fails must not stop the others
                notes.append(f"{e.name} could not read the page ({type(exc).__name__})")
    return raw


def engines_for(ocr_engines: list, has_text_layer: bool) -> list:
    """The OCR engines a page is read with first. A page with a text layer: the main engine and one second engine — Tesseract
    where it is installed, since its layout analysis gives the second order of the page as well (RapidOCR would add a third
    reading of the same words at the cost of a second of processor time a page). A page without one: every engine, to vote."""
    if not has_text_layer or len(ocr_engines) <= 2:
        return list(ocr_engines)
    second = next((e for e in ocr_engines[1:] if e.name == "Tesseract"), ocr_engines[1])
    return [ocr_engines[0], second]


def ocr_reading(raw: dict) -> tuple[str, int, float | None, list]:
    """The page read by OCR: the main engine's lines in column order, words voted with the other engines. -> (text, words taken
    from another engine, share of prose words another engine reads alike, the main engine's lines)."""
    reads = {k: O.column_order(v, O.joined_by_neighbours(v)) for k, v in raw.items()}   # no text layer: neighbours tell
    primary = next(iter(reads))
    lines = reads[primary]
    others = [reads[k] for k in reads if k != primary]
    voted, taken = O.vote(lines, others)
    return "\n".join(voted), taken, (O.agreement_on_prose(lines, others) if others else None), lines


def table_page(page) -> bool:
    """A page set as a table, with or without rules: its text-layer lines fall into three or more columns, each with at least a
    fifth of the lines and each at least 15 % of the page's width from the next (edges within 5 % are one: indented first
    lines do not count), and most of its lines are short (under 30 % of the page's width) — a two-column page of prose has two
    such columns and long lines. Asked only of a page whose prose order is not confirmed and whose prose is short (verify_page):
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
    """The heights (as shares of the page) where the text layer has a line in each column next to each other."""
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


def letters(text: str) -> collections.Counter:
    return collections.Counter(c for c in unicodedata.normalize("NFKC", text).lower() if c.isalnum())


def verify_page(doc, i: int, texts: dict, ocr_engines: list, regions: list, use_ocr: bool, reordered: str | None = None) -> PageResult:
    """Verify page i (0-based); texts: engine name -> list of page texts (None where an engine could not read the file);
    reordered: the text layer's own lines in the order of the page's layout (engines.reordered_pages), a reading that may stand
    in for the page's order where Tesseract's layout analysis confirms it."""
    n = i + 1
    page = doc[i]
    body = texts["MuPDF"][i]
    wit = {k: v[i] for k, v in texts.items() if k != "MuPDF" and v is not None}
    agree = {k: E.agreement(body, v) for k, v in wit.items()}
    judged = {k: v for k, v in agree.items() if v is not None}
    order = "too little text" if not judged else "confirmed" if max(judged.values()) >= 0.8 else "unconfirmed"
    m = {"agreement": agree, "order": order, "characters": len(body.strip())}
    notes: list[str] = []

    def text_layer_only(why: str) -> PageResult:
        conf = 1.0 if order != "unconfirmed" else max(judged.values()) / 0.8
        if len(body.strip()) < 100:
            notes.append(f"almost no text layer and {why}")
            conf = 0.0
        return PageResult(n, body, "text layer", round(min(1.0, conf), 3), m, notes)

    if not use_ocr or not ocr_engines:
        return text_layer_only("OCR is off" if not use_ocr else "no OCR engine is installed")
    raw = read_page(page, n, DPI, engines_for(ocr_engines, len(body.strip()) >= 100), notes)
    if not raw:
        return text_layer_only("no OCR engine could read the page")
    joined = O.joined_by_layout(side_by_side(page)) if len(body.strip()) >= 100 else None   # the text layer tells where OCR
    reads = {k: O.column_order(v, joined or O.joined_by_neighbours(v)) for k, v in raw.items()}   # joined two column lines
    primary = next(iter(reads))
    lines = reads[primary]
    boxes = figure_regions(page, regions)
    inside = lambda l: any(x0 <= (l.x0 + l.x1) / 2 <= x1 and y0 <= (l.y0 + l.y1) / 2 <= y1 for x0, y0, x1, y1 in boxes)
    kept = [l for l in lines if not inside(l)]
    every_text = "\n".join(l.text for k in reads for l in reads[k])
    seen = bag(every_text)
    bo, bb = bag("\n".join(l.text for l in kept)), bag(body)
    image_page = sum(bo.values()) >= IMAGE_MIN and sum(bb.values()) * IMAGE_RATIO <= sum(bo.values())
    if len(body.strip()) < 100 or image_page:                  # OCR stands in: the engines vote word by word
        rest = [e for e in ocr_engines if e.name not in raw]
        if rest:                                                # a page image under a stamp: every engine reads it, to vote
            raw.update(read_page(page, n, DPI, rest, notes))
        body, taken, alike, lines = ocr_reading(raw)
        dpi = DPI
        if alike is not None and alike < OCR_AGREE_MIN and len(raw) > 1:    # a second, sharper look: small type reads better
            raw2 = read_page(page, n, SHARPER_DPI, ocr_engines, [])
            if raw2 and next(iter(raw2)) == primary:
                body2, taken2, alike2, lines2 = ocr_reading(raw2)
                if alike2 is not None and alike2 > alike:
                    body, taken, alike, lines, dpi = body2, taken2, alike2, lines2, SHARPER_DPI
        source = f"OCR ({primary})"
        notes.append("no text layer: read by OCR" if len(texts["MuPDF"][i].strip()) < 100 else "a page image under a stamp: read by OCR")
        if dpi != DPI:
            notes.append(f"read again at {dpi} dpi, where the OCR engines agree better")
        if taken:
            notes.append(f"{taken} word(s) taken from another OCR engine where {primary} misread")
        conf = alike if alike is not None else (sum(l.conf for l in lines) / len(lines) if lines else 0.0)
        m.update({"ocr_engines": list(raw), "prose_read_alike": alike, "order": "column order (OCR)", "dpi": dpi})
        return PageResult(n, body, source, round(min(1.0, conf), 3), m, notes)

    # The order of the prose, judged on every page whatever the engines agreed on (readings that share MuPDF's content order
    # agree with it however it runs): every reading against OCR's orders of the page — the main engine's lines outside figures
    # and tables in column order (a figure's own lines do not cut the page into bands) and, where Tesseract is installed,
    # Tesseract's own layout analysis — the better of the two counting. On a page with a full-width figure or table between
    # the columns the two can differ (column by column, or above it and then below it): the page is then named.
    prose_c = prose_lines(O.column_order([l for l in raw[primary] if not inside(l)], joined))   # figures set aside before the lines
    prose_t = prose_lines([l for l in raw["Tesseract"] if not inside(l)]) if "Tesseract" in raw else None  # are ordered
    cands = {"MuPDF": body, **{k: v for k, v in wit.items() if v and v.strip()}}
    if reordered and reordered.strip() and letters(reordered) == letters(body):
        cands["re-ordered"] = reordered                    # every character of the text layer, only the order of its lines changed
    readings = {}
    for k, t in cands.items():
        fc, oc = line_order(prose_c, t)
        ft, ot = line_order(prose_t, t) if prose_t is not None else (0, None)
        shares = [o for f, o in ((fc, oc), (ft, ot)) if f >= PROSE_LINES_MIN and o is not None]
        b = bag(t)
        readings[k] = {"order": max(shares) if shares else None, "worse": min(shares) if shares else None,
                       "columns": [fc, oc], "layout": [ft, ot],
                       "not_visible": sum((b - seen).values()) - spaced(b - seen, every_text),
                       "missing": sum((bo - b).values()) - spaced(bo - b, t)}
    # The re-ordered text layer is put in order by the same geometry as OCR's column order, so that order is no witness for it:
    # Tesseract's layout analysis alone judges it. It stands in where Tesseract has its prose in order (95 % or more) and the
    # text layer's reading is not in order by both of OCR's orders, nor confirmed by Tesseract as well (or clearly worse by it).
    ro = readings.pop("re-ordered", None)
    tess = lambda v: v["layout"][1] if v["layout"][0] >= PROSE_LINES_MIN else None
    chosen, source = "MuPDF", "text layer"
    cur = readings["MuPDF"]["order"]
    t_ro, t_mu = (tess(ro) if ro else None), tess(readings["MuPDF"])
    if cur is not None and cur < LINE_ORDER_MIN and len(prose_c) < 15 and table_page(page):   # a table: its cells are no prose
        order = "a table page: the order of its cells is not judged"
        readings["MuPDF"] = {**readings["MuPDF"], "order": None}
    elif (t_ro is not None and t_ro >= WITNESS_LINE_ORDER_MIN and backed(readings["MuPDF"]) < 2
            and (t_mu is None or t_mu < LINE_ORDER_MIN or t_ro - t_mu >= WITNESS_BETTER_BY)):
        readings["re-ordered"] = {**ro, "order": t_ro, "worse": t_ro}
        chosen, body, source = "re-ordered", cands["re-ordered"], "text layer, re-ordered"
        order = "confirmed: the text layer re-ordered by the page's layout stands in"
        notes.append("the text layer's lines re-ordered by the page's layout stand in: Tesseract's layout analysis puts the prose "
                     "in that order, not in the order the PDF lays it down")
    elif cur is None:                                           # too little prose for OCR to judge: the engines' verdict stands
        if order == "unconfirmed":
            order = "too little prose"
    else:
        best = best_reading(readings, "MuPDF", sum(bo.values()))
        b = readings[best]["order"] if best else 0
        both = best and backed(readings[best]) == 2 and backed(readings["MuPDF"]) < 2
        if best and best != "MuPDF" and (both or (b >= WITNESS_LINE_ORDER_MIN and (cur < LINE_ORDER_MIN or b - cur >= WITNESS_BETTER_BY))):
            chosen, body = best, cands[best]
            source, order = f"{best} (order)", f"confirmed: {best}'s reading stands in"
            notes.append(f"{best}'s reading stands in: OCR puts the prose in its order, not in MuPDF's")
        elif orders_disagree(readings):
            order = "OCR's two orders disagree"
            notes.append("OCR's two orders of the page back different readings (a full-width figure or table between the columns?): "
                         "check the order against the page")
        elif cur >= LINE_ORDER_MIN:
            order = "confirmed by OCR (prose lines)"
        else:
            order = "not confirmed by OCR (prose lines)"
    lo = readings[chosen]["order"]
    found = readings[chosen]["columns"][0]
    bb = bag(body)

    def counts(reads: dict) -> tuple[int, int]:
        """Missing words (the main engine sees them in the running text, another engine too, the text lacks them) and words of
        the text no engine sees anywhere on the page."""
        every = "\n".join(l.text for k in reads for l in reads[k])
        lack = bo - bb
        others = [k for k in reads if k != primary]
        if others:
            seen2 = collections.Counter()
            for k in others:
                seen2 |= bag("\n".join(l.text for l in reads[k] if not inside(l)))
            lack = (bo & seen2) - bb
        unseen = bb - bag(every)
        return sum(lack.values()) - spaced(lack, body), sum(unseen.values()) - spaced(unseen, every)

    missing, invisible = counts(reads)
    total_bo, total_bb = sum(bo.values()), sum(bb.values())
    alone = bo - bb
    alone = sum(alone.values()) - spaced(alone, body)              # what the main engine alone finds missing
    rest = [e for e in ocr_engines if e.name not in raw]
    if rest and ((alone >= MISSING_MIN and alone > MISSING_SHARE * total_bo)
                 or (invisible >= INVISIBLE_MIN and invisible > INVISIBLE_SHARE * total_bb)):
        raw.update(read_page(page, n, DPI, rest, notes))             # a doubt: every engine reads the page, and every one counts
        reads = {k: O.column_order(v, joined or O.joined_by_neighbours(v)) for k, v in raw.items()}
        missing, invisible = counts(reads)
    miss_share = missing / max(1, total_bo)
    inv_share = invisible / max(1, total_bb)
    completeness = 1.0 if (miss_share <= MISSING_SHARE or missing < MISSING_MIN) else 1 - miss_share
    visibility = 1.0 if (inv_share <= INVISIBLE_SHARE or invisible < INVISIBLE_MIN) else 1 - inv_share
    order_score = (1.0 if (order.startswith("confirmed") or order.startswith("too little") or order.startswith("a table page")) else readings[chosen]["worse"]
                   if order.startswith("OCR's two orders") else (lo if lo is not None else max(judged.values(), default=0)))
    if completeness < 1:
        notes.append(f"{missing} word(s) of running text that OCR sees are missing from the text layer")
    if visibility < 1:
        notes.append(f"{invisible} word(s) of the text layer are not visible on the page")
    if order_score < 1 and not order.startswith("OCR's two orders"):
        notes.append("the order of the prose is not confirmed")
    m.update({"order": order, "ocr_engines": list(reads), "ocr_words": total_bo, "missing": missing, "not_visible": invisible,
              "prose_lines": found, "prose_line_order": lo,
              "readings": {**readings, **({"re-ordered": ro} if ro and "re-ordered" not in readings else {})}})
    return PageResult(n, body, source, round(min(order_score, completeness, visibility), 3), m, notes)
