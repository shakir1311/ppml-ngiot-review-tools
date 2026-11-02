#!/usr/bin/env python3
"""The text of every page, taken from standard tools, and the evidence that its reading order is right.

    reading text   PyMuPDF   page.get_text()    the order in which the PDF lays its text down
    witnesses      poppler   pdftotext          works the columns out from the page geometry
                   Apple     PDFKit             the engine behind Preview
                   pymupdf4llm                  text/full.md, from its layout engine (see markdown_pdf.py)

A page's reading order is confirmed when PyMuPDF's text agrees with at least one witness: most of its eight-word runs
also run on in the witness. Text read straight across two columns scores well under 0.5; the same order with a
caption, footnote or list placed differently scores 0.8 and more. Pages that no witness confirms are listed by
check_extraction.py for a person to check against the page render.

The witnesses' readings are kept (`text/variants/`), and the notes checker accepts a quotation found on the cited page
in the reading text or in a witness. Text sorted by position on the page — the method used before 28 Sep 2026 — reads
a two-column page across both columns; it is not produced and not kept.
"""
from __future__ import annotations

import collections
import contextlib
import hashlib
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

RUN = 8                 # words in a run when two versions of a page are compared
STEP = 3                # a run starts every STEP words
AGREE = 0.80            # PyMuPDF's order is confirmed by a witness at or above this share of runs
MIN_RUNS = 25           # fewer runs than this (about 80 words) is too little running text to compare
VARIANTS = ("poppler", "pdfkit")               # text/variants/page_NNNN.<name>.txt
STANDS_IN = {"poppler": "pdftotext", "pdfkit": "PDFKit", "pdfminer": "pdfminer",   # readings verify_ocr.py can let stand in
             "reordered": "the text layer re-ordered by the page's layout"}

# ------------------------------------------------------------------------------------------------ normalisation


def words(text: str) -> list[str]:
    """Lower-case words; a word split by a hyphen at the end of a line is joined."""
    text = unicodedata.normalize("NFKD", text).replace("­", "")
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.findall(r"[a-z0-9]+", text.lower())


def characters(text: str) -> collections.Counter:
    """How often each letter and digit occurs; two versions of a page hold the same text when these are equal."""
    return collections.Counter(re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text).lower()))


def overlap(a: collections.Counter, b: collections.Counter) -> float:
    """Share of the letters and digits of a that are also in b."""
    total = sum(a.values())
    return 1.0 if not total else sum((a & b).values()) / total


def repair(text: str) -> str:
    """Join UTF-16 surrogate pairs into the characters they stand for (PDFKit hands some maths symbols over as
    pairs); a half pair that is left over becomes the replacement character. Other text is returned unchanged."""
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def sha1(text: str) -> str:
    return hashlib.sha1(repair(text).encode("utf-8")).hexdigest()

# ------------------------------------------------------------------------------------------------ the engines


def pymupdf_text(page) -> str:
    return repair(page.get_text("text"))


def poppler_pages(pdf: Path, page_count: int) -> tuple[list[str] | None, str]:
    """pdftotext's reading order, one string per page. -> pages or None, remark"""
    exe = shutil.which("pdftotext")
    if not exe:
        return None, "pdftotext not installed (brew install poppler)"
    try:
        out = subprocess.run([exe, "-enc", "UTF-8", "-eol", "unix", str(pdf), "-"], capture_output=True,
                             timeout=900, check=True).stdout.decode("utf-8", errors="replace")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return None, f"pdftotext failed: {exc}"
    chunks = out.split("\f")
    if len(chunks) == page_count + 1 and not chunks[-1].strip():
        chunks = chunks[:-1]
    if len(chunks) != page_count:
        return None, f"pdftotext gave {len(chunks)} pages for {page_count}; not used"
    return chunks, ""


def poppler_layout(pdf: Path, dest: Path) -> str:
    """Layout-preserving text of the whole paper (tables keep their columns). -> remark, empty when written"""
    exe = shutil.which("pdftotext")
    if not exe:
        return "pdftotext not installed - no layout-preserving text"
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        subprocess.run([exe, "-layout", "-enc", "UTF-8", "-eol", "unix", str(pdf), str(tmp)],
                       check=True, capture_output=True, timeout=900)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return f"pdftotext -layout failed: {exc}"
    os.replace(tmp, dest)
    return ""


@contextlib.contextmanager
def quiet_stderr():
    """Silence C-level stderr: PDFKit prints a line for every glyph without a Unicode mapping."""
    saved, null = os.dup(2), os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 2)
    try:
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(null)


def pdfkit_pages(pdf: Path, page_count: int) -> tuple[list[str] | None, str]:
    """Apple PDFKit's text, one string per page. -> pages or None, remark"""
    try:
        import Quartz
        from Foundation import NSURL
    except ImportError:
        return None, "PDFKit not available (pyobjc-framework-Quartz is not installed)"
    with quiet_stderr():
        doc = Quartz.PDFDocument.alloc().initWithURL_(NSURL.fileURLWithPath_(str(pdf)))
        if doc is None:
            return None, "PDFKit could not open the PDF"
        pages = [repair(str(doc.pageAtIndex_(i).string() or "")) for i in range(doc.pageCount())]
    if len(pages) != page_count:
        return None, f"PDFKit gave {len(pages)} pages for {page_count}; not used"
    return pages, ""

# ------------------------------------------------------------------------------------------------ agreement


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


def page_agreement(text: str, witness: str) -> float | None:
    """Share of the page's runs that run on in the witness (which may be the whole paper, as full.md is)."""
    wt = words(text)
    runs = ["".join(wt[i:i + RUN]) for i in range(0, max(0, len(wt) - RUN + 1), STEP)]
    if len(runs) < MIN_RUNS:
        return None
    body = "".join(words(witness))
    return round(sum(1 for r in runs if r in body) / len(runs), 3)


def verdict(text: str, witnesses: dict[str, str | None], whole_paper: dict[str, str] | None = None) -> dict:
    """Is the reading order of this page confirmed?

    witnesses:   other engines' text of the same page (None where an engine gave nothing)
    whole_paper: other engines' text of the whole paper, without page breaks (full.md)
    -> {"order_status": confirmed | unconfirmed | too little text, "confirmed_by": [...], "agreement": {...}}
    """
    scores = {name: (agreement(text, w) if w is not None else None) for name, w in witnesses.items()}
    for name, w in (whole_paper or {}).items():
        scores[name] = page_agreement(text, w)
    judged = {k: v for k, v in scores.items() if v is not None}
    if not judged:
        status, by = "too little text", []
    else:
        by = [k for k, v in judged.items() if v >= AGREE]
        status = "confirmed" if by else "unconfirmed"
    return {"order_status": status, "confirmed_by": by, "agreement": scores}

# ------------------------------------------------------------------------------------------------ files


def read_exact(path: Path) -> str:
    """The text of a file exactly as written. Python's default reading turns a carriage return into a line feed;
    maths fonts put such characters into the text of a page, and the page on disk must equal the page extracted."""
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        return fh.read()


def write_atomic(path: Path, data: str) -> None:
    """Write a file so that it is either the old version or the complete new one, never half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(repair(data))
    os.replace(tmp, path)


def marker(n: int, total: int, note: str = "") -> str:
    return f"========== [ PAGE {n} / {total}{' — ' + note if note else ''} ] =========="


def assemble_full_text(folder: Path, pages_meta: list[dict]) -> str:
    """text/full.txt from the reading text of every page; OCR text stands in for a page without a text layer."""
    total = len(pages_meta)
    parts = []
    for p in pages_meta:
        n = p["page"]
        body = read_exact(folder / "text" / "pages" / f"page_{n:04d}.txt")
        ocr = folder / "text" / "pages_ocr" / f"page_{n:04d}.txt"
        note = ""
        if len(body.strip()) < 100 and ocr.exists():
            body, note = read_exact(ocr), "OCR (no text layer in PDF)"
        elif p.get("ocr_stands_in") and ocr.exists():
            body, note = read_exact(ocr), "OCR (the text layer holds only a stamp or running head over a page image)"
        elif p.get("reading_order_from") in STANDS_IN and \
                (folder / "text" / "variants" / f"page_{n:04d}.{p['reading_order_from']}.txt").exists():
            body = read_exact(folder / "text" / "variants" / f"page_{n:04d}.{p['reading_order_from']}.txt")
            note = (f"reading order of {STANDS_IN[p['reading_order_from']]} (OCR of the page puts its prose "
                    "in this order, not in PyMuPDF's content order)")
        elif p.get("order_status") == "unconfirmed" and not p.get("order_checked_by_eye"):
            note = ("OCR's two orders of the page put its prose in different orders (a full-width figure or table between the "
                    "columns?): check the order against the page render" if p.get("ocr_orders_disagree") else
                    "OCR of the page does not confirm the order of its prose in any reading: check against the page render"
                    if p.get("ocr_order_not_confirmed") else "reading order not confirmed by a second engine: check against the page render")
        parts.append(f"{marker(n, total, note)}\n\n{body}")
    return "\n\n".join(parts) + "\n"
