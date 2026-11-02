"""Three independent readings of a PDF's text layer, page by page.

  MuPDF (PyMuPDF)   the reading text: the order in which the PDF lays its text down — for a publisher's two-column paper
                    that is column by column (sorting by position would read straight across the columns);
  PDFium (pypdfium2) a second engine, Chrome's;
  pdfminer          a third, with its own layout analysis, which groups lines into columns and boxes.

They read the same text layer, so they share its faults (text hidden or set outside the page, pages that are images); OCR of the
rendered page (ocr.py) is the independent view of what a reader sees.
"""
from __future__ import annotations

import re
import unicodedata

LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}


def repair(text: str) -> str:
    """Ligatures to letters, soft hyphens removed, Windows line ends unified; nothing else is changed."""
    for k, v in LIGATURES.items():
        text = text.replace(k, v)
    return text.replace("­", "").replace("\r\n", "\n").replace("\r", "\n")


def mupdf_pages(doc) -> list[str]:
    return [repair(page.get_text("text")) for page in doc]


def reordered_pages(doc) -> list[str]:
    """MuPDF's own lines — every character exactly as the text layer holds it — put in the order of the page's layout: band by band
    between the lines that span both columns, the left column of a band before its right one (ocr.column_order). A reading for
    pages whose text the PDF lays down out of order and no engine reads in order with every word."""
    from .ocr import Line, column_order
    out = []
    for page in doc:
        w, h = page.rect.width or 1, page.rect.height or 1
        lines = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"])
                if text.strip():
                    x0, y0, x1, y1 = line["bbox"]
                    lines.append(Line(text, x0 / w, y0 / h, x1 / w, y1 / h, 1.0))
        out.append(repair("\n".join(l.text for l in column_order(lines))))
    return out


def pdfium_pages(path) -> list[str] | None:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    try:
        pdf = pdfium.PdfDocument(str(path))
        out = []
        for i in range(len(pdf)):
            page = pdf[i]
            tp = page.get_textpage()
            out.append(repair(tp.get_text_range()))
            tp.close()
            page.close()
        pdf.close()
        return out
    except Exception:  # noqa: BLE001 - an engine that cannot read the file is simply not a witness
        return None


def pdfminer_pages(path, page_count: int) -> list[str] | None:
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LAParams, LTTextContainer
    except ImportError:
        return None
    try:
        out = []
        for layout in extract_pages(str(path), laparams=LAParams()):        # the document is parsed once
            out.append(repair("".join(el.get_text() for el in layout if isinstance(el, LTTextContainer))))
        return out if len(out) == page_count else None
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------------------- comparing two readings
RUN, STEP, MIN_RUNS = 8, 3, 25


def words(text: str) -> list[str]:
    """Lower-case words; a word split by a hyphen at the end of a line is joined."""
    text = unicodedata.normalize("NFKD", repair(text))
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.findall(r"[a-z0-9]+", text.lower())


def agreement(a: str, b: str) -> float | None:
    """Share of the eight-word runs of the shorter text that run on in the longer; None when too short to judge."""
    wa, wb = words(a), words(b)
    if len(wa) > len(wb):
        wa, wb = wb, wa
    runs = ["".join(wa[i:i + RUN]) for i in range(0, max(0, len(wa) - RUN + 1), STEP)]
    if len(runs) < MIN_RUNS:
        return None
    body = "".join(wb)
    return round(sum(1 for r in runs if r in body) / len(runs), 3)


def runs_found(text: str, witness: str) -> float | None:
    """Share of the eight-word runs of `text` that run on, in the same order, in `witness`."""
    wt = words(text)
    runs = ["".join(wt[i:i + RUN]) for i in range(0, max(0, len(wt) - RUN + 1), STEP)]
    if len(runs) < MIN_RUNS:
        return None
    body = "".join(words(witness))
    return round(sum(1 for r in runs if r in body) / len(runs), 3)
