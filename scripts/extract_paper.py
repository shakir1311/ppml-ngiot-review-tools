#!/usr/bin/env python3
"""Extract one PDF into a self-contained, fully analysable folder.

Produces, next to the PDF, a folder named after the PDF stem containing:

    text/full.txt              the reading text of every page, page-delimited (PyMuPDF; OCR where a page has no text)
    text/pages/page_NNNN.txt   the reading text of one page: PyMuPDF get_text(), in the order the PDF lays it down
    text/variants/             each page as read by pdftotext and by PDFKit (see page_text.py)
    text/full_layout.txt       layout-preserving text (poppler pdftotext -layout)
    text/full.md               markdown with headings/tables (pymupdf4llm, run by markdown_pdf.py)
    images/pages/page_NNNN.png full-page renders (every figure guaranteed visible)
    images/embedded/...        embedded raster images, named by page
    images/figures/...         cropped figure regions (vector + raster artwork)
    tables/...                 detected tables as CSV and Markdown
    metadata.json              doc metadata, outline, per-page stats, inventories
    README.md                  human-readable summary of the extraction

Usage:
    extract_paper.py <file.pdf> [--outdir DIR] [--dpi N] [--force] [--text-only] [--quiet]

--force extracts from scratch: everything an earlier extraction left in the folder is removed first; the paper itself,
notes/ and images/crops/ (enlargements made while reading) are kept.
--text-only rewrites the text outputs of a paper that is already extracted and leaves its images, tables and full.md
alone (full.md is made only when it is missing).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

import page_text as PT

# ---------------------------------------------------------------- tuning knobs

PAGE_DPI = 150            # full-page render resolution
FIGURE_DPI = 200          # cropped figure render resolution
MIN_EMBEDDED_PX = 16      # skip embedded images smaller than this on either side
MIN_FIGURE_PT = 40        # skip figure regions smaller than this (points) either side
MAX_DRAWINGS = 60000      # bail out of vector clustering on pathological pages
SCANNED_CHAR_THRESHOLD = 100   # chars/page below this suggests a scanned page
CLUSTER_PAD = 6.0         # points of slack when merging artwork rectangles


# --------------------------------------------------------------------- helpers

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_stem(name: str) -> str:
    """Filesystem-safe folder name that still reads like the paper title."""
    cleaned = name.replace("/", "-").replace(":", " -").strip()
    return cleaned.rstrip(". ") or "paper"


def default_outdir(pdf: Path) -> Path:
    """Where a PDF's extraction belongs.

    Normally a sibling folder named after the PDF. Once the PDF has been moved
    inside that folder, the folder itself is the target - otherwise a re-run
    would nest a second extraction underneath it.
    """
    if pdf.parent.name == safe_stem(pdf.stem):
        return pdf.parent
    return pdf.parent / safe_stem(pdf.stem)


def rects_overlap(a: pymupdf.Rect, b: pymupdf.Rect, pad: float = CLUSTER_PAD) -> bool:
    a2 = pymupdf.Rect(a.x0 - pad, a.y0 - pad, a.x1 + pad, a.y1 + pad)
    return bool(a2.intersects(b))


def cluster_rects(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Merge overlapping/adjacent rectangles into figure-sized regions."""
    out: list[pymupdf.Rect] = []
    for r in rects:
        merged = pymupdf.Rect(r)
        changed = True
        while changed:
            changed = False
            keep: list[pymupdf.Rect] = []
            for o in out:
                if rects_overlap(merged, o):
                    merged |= o
                    changed = True
                else:
                    keep.append(o)
            out = keep
        out.append(merged)
    return out


@dataclass
class PageStat:
    page: int
    width: float
    height: float
    chars: int
    words: int
    blocks: int
    embedded_images: int
    figures: int
    tables: int
    links: int
    likely_scanned: bool
    notes: list[str] = field(default_factory=list)
    order_status: str = ""                     # confirmed | unconfirmed | too little text (see page_text.verdict)
    confirmed_by: list[str] = field(default_factory=list)
    agreement: dict = field(default_factory=dict)
    text_sha1: str = ""                        # of text/pages/page_NNNN.txt, so the audit can prove the file is current


# ------------------------------------------------------------------ extraction

def write(path: Path, data: str) -> None:
    PT.write_atomic(path, data)


def make_markdown(pdf: Path, dest: Path) -> str:
    """text/full.md by pymupdf4llm, in a process of its own (see markdown_pdf.py). -> remark, empty when written"""
    try:
        r = subprocess.run([sys.executable, str(Path(__file__).with_name("markdown_pdf.py")), str(pdf), str(dest)],
                           capture_output=True, text=True, timeout=1800,
                           env={**os.environ, "ORT_DISABLE_TELEMETRY": "1"})
    except subprocess.TimeoutExpired:
        return "markdown rendering timed out"
    if r.returncode != 0:
        return f"markdown rendering failed (exit {r.returncode}): {r.stderr.strip()[-300:]}"
    return ""


def tool_versions() -> dict:
    out = {"pymupdf": pymupdf.__version__}
    try:
        v = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True, timeout=30)
        out["pdftotext"] = (v.stderr or v.stdout).splitlines()[0].strip()
    except Exception:  # noqa: BLE001
        out["pdftotext"] = "not available"
    return out


def save_pixmap(pix: pymupdf.Pixmap, dest: Path) -> None:
    """Save as PNG, whole or not at all: a failed save leaves no file behind."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if pix.colorspace is None or pix.colorspace.n not in (1, 3):      # CMYK, separation, mask: PNG takes grey or RGB
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        pix.save(str(tmp), output="png")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()


def extract_embedded_images(doc, page, pno: int, outdir: Path,
                            seen: dict[int, str], inventory: list[dict]) -> int:
    count = 0
    for idx, info in enumerate(page.get_images(full=True), start=1):
        xref = info[0]
        try:
            if xref in seen:
                inventory.append({
                    "page": pno, "xref": xref, "file": seen[xref],
                    "duplicate_of_earlier_page": True,
                })
                continue
            base = doc.extract_image(xref)
            width, height = base.get("width", 0), base.get("height", 0)
            if width < MIN_EMBEDDED_PX or height < MIN_EMBEDDED_PX:
                continue
            name = f"p{pno:04d}_img{idx:02d}.png"
            pix = pymupdf.Pixmap(doc, xref)
            if pix.alpha:
                pix = pymupdf.Pixmap(pix, 0)  # drop alpha for a flat PNG
            save_pixmap(pix, outdir / name)
            seen[xref] = name
            inventory.append({
                "page": pno, "xref": xref, "file": name,
                "width": width, "height": height,
                "source_format": base.get("ext"),
                "colorspace": base.get("colorspace"),
            })
            count += 1
        except Exception as exc:  # noqa: BLE001 - one bad image must not stop the run
            inventory.append({"page": pno, "xref": xref, "error": str(exc)})
    return count


def extract_figure_regions(page, pno: int, outdir: Path,
                           inventory: list[dict]) -> tuple[int, list[str]]:
    """Crop artwork regions (vector drawings + placed rasters) to PNG.

    Catches figures drawn as vectors, which raster-image extraction misses.
    """
    notes: list[str] = []
    page_rect = page.rect
    page_area = page_rect.get_area() or 1.0
    rects: list[pymupdf.Rect] = []

    for info in page.get_image_info():
        r = pymupdf.Rect(info["bbox"])
        if r.width >= MIN_FIGURE_PT and r.height >= MIN_FIGURE_PT:
            rects.append(r)

    try:
        drawings = page.get_drawings()
    except Exception as exc:  # noqa: BLE001
        drawings = []
        notes.append(f"vector drawing scan failed: {exc}")
    if len(drawings) > MAX_DRAWINGS:
        notes.append(f"skipped vector clustering ({len(drawings)} paths exceeds cap)")
        drawings = []
    for d in drawings:
        r = pymupdf.Rect(d["rect"])
        if r.is_empty or r.is_infinite:
            continue
        # Ignore page-spanning rules/borders and hairlines.
        if r.get_area() >= 0.95 * page_area:
            continue
        if r.width < 2 or r.height < 2:
            continue
        rects.append(r)

    merged = [r for r in cluster_rects(rects)
              if r.width >= MIN_FIGURE_PT and r.height >= MIN_FIGURE_PT
              and r.get_area() < 0.98 * page_area]
    merged.sort(key=lambda r: (round(r.y0, 1), round(r.x0, 1)))

    count = 0
    for idx, r in enumerate(merged, start=1):
        clip = (r + (-CLUSTER_PAD, -CLUSTER_PAD, CLUSTER_PAD, CLUSTER_PAD)) & page_rect
        if clip.is_empty:
            continue
        name = f"p{pno:04d}_fig{idx:02d}.png"
        try:
            pix = page.get_pixmap(dpi=FIGURE_DPI, clip=clip)
            save_pixmap(pix, outdir / name)
        except Exception as exc:  # noqa: BLE001
            inventory.append({"page": pno, "region": idx, "error": str(exc)})
            continue
        inventory.append({
            "page": pno, "file": name,
            "bbox": [round(v, 2) for v in (clip.x0, clip.y0, clip.x1, clip.y1)],
        })
        count += 1
    return count, notes


def extract_tables(page, pno: int, outdir: Path, inventory: list[dict]) -> int:
    try:
        finder = page.find_tables()
    except Exception as exc:  # noqa: BLE001
        inventory.append({"page": pno, "error": f"table detection failed: {exc}"})
        return 0
    count = 0
    for idx, table in enumerate(finder.tables, start=1):
        try:
            rows = table.extract()
            if not rows:
                continue
            stem = f"p{pno:04d}_table{idx:02d}"
            sheet = io.StringIO(newline="")
            csv.writer(sheet).writerows([["" if c is None else PT.repair(str(c)).replace("\n", " ") for c in row]
                                         for row in rows])
            write(outdir / f"{stem}.csv", sheet.getvalue())      # written whole or not at all
            try:
                write(outdir / f"{stem}.md", table.to_markdown())
            except Exception:  # noqa: BLE001 - CSV is the authoritative copy
                pass
            inventory.append({
                "page": pno, "file": f"{stem}.csv",
                "rows": len(rows), "cols": max(len(r) for r in rows),
                "bbox": [round(v, 2) for v in table.bbox],
            })
            count += 1
        except Exception as exc:  # noqa: BLE001
            inventory.append({"page": pno, "table": idx, "error": str(exc)})
    return count


def extract_text(doc, pdf: Path, folder: Path, markdown: bool) -> tuple[list[dict], list[str]]:
    """Write every text output of a paper and judge the reading order of every page.

    markdown: make text/full.md even when it exists.  -> per-page facts, warnings
    """
    text_dir = folder / "text"
    pages_dir, variants_dir = text_dir / "pages", text_dir / "variants"
    warnings: list[str] = []
    md_path = text_dir / "full.md"
    if markdown or not md_path.exists():
        remark = make_markdown(pdf, md_path)
        if remark:
            warnings.append(remark)
    whole = {"full.md": PT.read_exact(md_path)} if md_path.exists() else {}
    poppler, remark = PT.poppler_pages(pdf, doc.page_count)
    if remark:
        warnings.append(remark)
    pdfkit, remark = PT.pdfkit_pages(pdf, doc.page_count)
    if remark:
        warnings.append(remark)

    rows: list[dict] = []
    keep: set[str] = set()
    for pno0, page in enumerate(doc):
        pno = pno0 + 1
        notes: list[str] = []
        try:
            text = PT.pymupdf_text(page)
        except Exception as exc:  # noqa: BLE001
            text = ""
            notes.append(f"text extraction failed: {exc}")
        versions = {"poppler": poppler[pno0] if poppler else None,
                    "pdfkit": pdfkit[pno0] if pdfkit else None}
        name = f"page_{pno:04d}.txt"
        write(pages_dir / name, text)
        keep.add(f"pages/{name}")
        for variant, body in versions.items():
            if body is not None:
                vname = f"page_{pno:04d}.{variant}.txt"
                write(variants_dir / vname, body)
                keep.add(f"variants/{vname}")
        judged = PT.verdict(text, {"pdftotext": versions["poppler"], "pdfkit": versions["pdfkit"]}, whole)
        if judged["order_status"] == "unconfirmed":
            notes.append("reading order not confirmed by pdftotext, PDFKit or full.md - check against the page render")
        rows.append({"page": pno, "chars": len(text.strip()), "words": len(text.split()), "notes": notes,
                     "text_sha1": PT.sha1(text), **judged})

    for sub in (pages_dir, variants_dir):          # pages or variants left over from an earlier extraction
        for f in sub.glob("page_*"):
            if f"{sub.name}/{f.name}" not in keep:
                f.unlink()
    remark = PT.poppler_layout(pdf, text_dir / "full_layout.txt")
    if remark:
        warnings.append(remark)
    write(text_dir / "full.txt", PT.assemble_full_text(folder, rows))

    scanned = [r["page"] for r in rows if r["chars"] < SCANNED_CHAR_THRESHOLD]
    if scanned:
        warnings.append(f"{len(scanned)} page(s) yielded almost no text (likely scanned/image-only): {scanned[:20]}"
                        + (" ..." if len(scanned) > 20 else ""))
    unconfirmed = [r["page"] for r in rows if r["order_status"] == "unconfirmed"]
    if unconfirmed:
        warnings.append(f"{len(unconfirmed)} page(s) whose reading order no second engine confirms: {unconfirmed[:30]}"
                        + (" ..." if len(unconfirmed) > 30 else ""))
    return rows, warnings


def text_totals(rows: list[dict], page_count: int) -> dict:
    chars = sum(r["chars"] for r in rows)
    return {"characters": chars, "words": sum(r["words"] for r in rows),
            "pages_likely_scanned": sum(1 for r in rows if r["chars"] < SCANNED_CHAR_THRESHOLD),
            "pages_order_confirmed": sum(1 for r in rows if r["order_status"] == "confirmed"),
            "pages_order_unconfirmed": sum(1 for r in rows if r["order_status"] == "unconfirmed"),
            "pages_too_little_text": sum(1 for r in rows if r["order_status"] == "too little text"),
            "mean_chars_per_page": round(chars / max(page_count, 1), 1)}


TEXT_KEYS = ("chars", "words", "order_status", "confirmed_by", "agreement", "text_sha1")
OLD_KEYS = ("order_agreement", "reading_order_doubtful")
TEXT_WARNINGS = ("pdftotext", "markdown", "PDFKit", "yielded almost no text", "reading order", "doubtful")


def extract_text_only(pdf: Path, outdir: Path) -> dict:
    """Rewrite the text outputs of a paper that is already extracted; images, tables and inventories stay."""
    meta = json.loads((outdir / "metadata.json").read_text(encoding="utf-8"))
    with pymupdf.open(str(pdf)) as doc:
        if len(meta.get("pages", [])) != doc.page_count:
            raise RuntimeError(f"metadata lists {len(meta.get('pages', []))} pages, the PDF has {doc.page_count}; "
                               f"run a full extraction (--force)")
        rows, warnings = extract_text(doc, pdf, outdir, markdown=False)
        page_count = doc.page_count
    for page, row in zip(meta["pages"], rows):
        checked = page.get("order_checked_by_eye") if page.get("text_sha1") == row["text_sha1"] else None
        for k in OLD_KEYS + ("order_checked_by_eye",):
            page.pop(k, None)
        kept = [n for n in page.get("notes", []) if not n.startswith(("text extraction", "reading order", "margin"))]
        page.update({k: row[k] for k in TEXT_KEYS}, likely_scanned=row["chars"] < SCANNED_CHAR_THRESHOLD,
                    notes=kept + row["notes"])
        if checked:
            page["order_checked_by_eye"] = checked
    meta["totals"].update(text_totals(rows, page_count))
    for k in ("pages_reading_order_doubtful",):
        meta["totals"].pop(k, None)
    meta["extracted_with"].pop("text_order", None)
    meta["extracted_with"].update(tool_versions(), text="PyMuPDF get_text() (content order); witnesses pdftotext, "
                                                        "PDFKit, full.md")
    meta["warnings"] = [w for w in meta.get("warnings", []) if not any(k in w for k in TEXT_WARNINGS)] + warnings
    write(outdir / "metadata.json", json.dumps(meta, indent=2, ensure_ascii=False))
    write(outdir / "README.md", build_readme(pdf, meta))
    return meta


OUTPUTS = ("text", "tables", "images/pages", "images/embedded", "images/figures", "metadata.json", "README.md",
           "EXTRACTION_FAILED.txt")


def clean_outputs(outdir: Path) -> None:
    """Remove what an earlier extraction left in the folder. The paper, notes/ and images/crops/ stay."""
    for name in OUTPUTS:
        target = outdir / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def extract(pdf: Path, outdir: Path, dpi: int, quiet: bool) -> dict:
    clean_outputs(outdir)
    text_dir = outdir / "text"
    pages_txt_dir = text_dir / "pages"
    page_img_dir = outdir / "images" / "pages"
    emb_dir = outdir / "images" / "embedded"
    fig_dir = outdir / "images" / "figures"
    tbl_dir = outdir / "tables"
    for d in (text_dir, pages_txt_dir, page_img_dir, emb_dir, fig_dir, tbl_dir):
        d.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    doc = pymupdf.open(str(pdf))
    if doc.needs_pass:
        raise RuntimeError("PDF is password protected")

    stats: list[PageStat] = []
    emb_inventory: list[dict] = []
    fig_inventory: list[dict] = []
    tbl_inventory: list[dict] = []
    seen_xrefs: dict[int, str] = {}
    text_rows, text_warnings = extract_text(doc, pdf, outdir, markdown=True)
    warnings += text_warnings

    for pno0, page in enumerate(doc):
        pno = pno0 + 1
        row = text_rows[pno0]
        notes: list[str] = list(row["notes"])

        try:
            pix = page.get_pixmap(dpi=dpi)
            save_pixmap(pix, page_img_dir / f"page_{pno:04d}.png")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"page render failed: {exc}")

        n_emb = extract_embedded_images(doc, page, pno, emb_dir, seen_xrefs, emb_inventory)
        n_fig, fig_notes = extract_figure_regions(page, pno, fig_dir, fig_inventory)
        notes += fig_notes
        n_tbl = extract_tables(page, pno, tbl_dir, tbl_inventory)

        chars = row["chars"]
        stats.append(PageStat(
            page=pno,
            width=round(page.rect.width, 1), height=round(page.rect.height, 1),
            chars=chars, words=row["words"],
            blocks=len(page.get_text("blocks")),
            embedded_images=n_emb, figures=n_fig, tables=n_tbl,
            links=len(page.get_links()),
            likely_scanned=chars < SCANNED_CHAR_THRESHOLD,
            notes=notes,
            **{k: row[k] for k in ("order_status", "confirmed_by", "agreement", "text_sha1")},
        ))
        if not quiet:
            print(f"  page {pno:>3}/{doc.page_count}: {chars:>6} chars, "
                  f"{n_emb} img, {n_fig} fig, {n_tbl} tbl", file=sys.stderr)

    fonts = sorted({f[3] for p in range(doc.page_count)
                    for f in doc.get_page_fonts(p)}) if doc.page_count else []

    meta = {
        "source_pdf": pdf.name,
        "source_sha256": sha256_of(pdf),
        "source_bytes": pdf.stat().st_size,
        "extracted_with": {
            **tool_versions(),
            "text": "PyMuPDF get_text() (content order); witnesses pdftotext, PDFKit, full.md",
            "page_render_dpi": dpi,
            "figure_render_dpi": FIGURE_DPI,
        },
        "page_count": doc.page_count,
        "pdf_metadata": dict(doc.metadata or {}),
        "is_pdf": doc.is_pdf,
        "outline": doc.get_toc(simple=True),
        "fonts": fonts,
        "totals": {
            **text_totals(text_rows, doc.page_count),
            "embedded_images": sum(s.embedded_images for s in stats),
            "figure_crops": sum(s.figures for s in stats),
            "tables": sum(s.tables for s in stats),
        },
        "warnings": warnings,
        "pages": [s.__dict__ for s in stats],
        "embedded_image_inventory": emb_inventory,
        "figure_inventory": fig_inventory,
        "table_inventory": tbl_inventory,
    }
    doc.close()

    write(outdir / "metadata.json", json.dumps(meta, indent=2, ensure_ascii=False))
    write(outdir / "README.md", build_readme(pdf, meta))
    return meta


def build_readme(pdf: Path, meta: dict) -> str:
    t = meta["totals"]
    title = (meta["pdf_metadata"].get("title") or "").strip() or "(none in PDF metadata)"
    author = (meta["pdf_metadata"].get("author") or "").strip() or "(none in PDF metadata)"
    warn = meta["warnings"]
    lines = [
        f"# Extraction: {pdf.stem}",
        "",
        f"- **Source PDF:** `{meta['source_pdf']}`",
        f"- **Embedded title:** {title}",
        f"- **Embedded author:** {author}",
        f"- **Pages:** {meta['page_count']}",
        f"- **Characters of text:** {t['characters']:,} "
        f"(mean {t['mean_chars_per_page']:,} per page)",
        f"- **Embedded images:** {t['embedded_images']}",
        f"- **Figure crops:** {t['figure_crops']}",
        f"- **Tables:** {t['tables']}",
        f"- **Pages with no usable text layer:** {t['pages_likely_scanned']}",
        f"- **Reading order:** confirmed by a second engine on {t.get('pages_order_confirmed', 0)} page(s); "
        f"not confirmed on {t.get('pages_order_unconfirmed', 0)}; too little text to judge on "
        f"{t.get('pages_too_little_text', 0)}",
        "",
        "## Contents",
        "",
        "| Path | What it holds |",
        "| --- | --- |",
        "| `text/full.txt` | Whole paper as plain text in reading order (PyMuPDF), delimited by page markers. |",
        "| `text/full_layout.txt` | Same text with column/table spacing preserved. |",
        "| `text/full.md` | Markdown with headings, lists and tables. |",
        "| `text/pages/` | One plain-text file per page, in reading order (PyMuPDF). |",
        "| `text/variants/` | Each page again, as pdftotext and as PDFKit read it. |",
        "| `images/pages/` | Full-page renders — every figure is visible here. |",
        "| `images/embedded/` | Raster images lifted out of the PDF at native resolution. |",
        "| `images/figures/` | Cropped artwork regions, including vector-drawn figures. |",
        "| `tables/` | Detected tables as CSV (authoritative) and Markdown. |",
        "| `metadata.json` | Metadata, outline, per-page statistics, full inventories. |",
        "",
    ]
    if warn:
        lines += ["## Warnings", ""] + [f"- {w}" for w in warn] + [""]
    return "\n".join(lines)


# ------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description="Fully extract a PDF for analysis.")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--outdir", type=Path, default=None,
                    help="output folder (default: sibling folder named after the PDF)")
    ap.add_argument("--dpi", type=int, default=PAGE_DPI)
    ap.add_argument("--force", action="store_true",
                    help="re-extract even if the folder already looks complete")
    ap.add_argument("--text-only", action="store_true",
                    help="rewrite only the text outputs of a paper that is already extracted")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.is_file():
        print(f"ERROR: no such file: {pdf}", file=sys.stderr)
        return 2

    outdir = args.outdir or default_outdir(pdf)
    marker = outdir / "metadata.json"
    if args.text_only and marker.exists():
        try:
            meta = extract_text_only(pdf, outdir)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {pdf.name}: {exc}", file=sys.stderr)
            return 1
        t = meta["totals"]
        print(f"OK: {pdf.name} | {meta['page_count']}p | {t['characters']:,} chars | text only | order confirmed "
              f"{t['pages_order_confirmed']}, unconfirmed {t['pages_order_unconfirmed']}, "
              f"too little text {t['pages_too_little_text']}")
        return 0
    if marker.exists() and not args.force:
        if not args.quiet:
            print(f"SKIP (already extracted): {pdf.name}", file=sys.stderr)
        return 0

    if not args.quiet:
        print(f"EXTRACT: {pdf.name}", file=sys.stderr)
    try:
        meta = extract(pdf, outdir, args.dpi, args.quiet)
    except Exception as exc:  # noqa: BLE001 - record the failure, keep the batch going
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "EXTRACTION_FAILED.txt").write_text(
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")
        print(f"FAIL: {pdf.name}: {exc}", file=sys.stderr)
        return 1

    t = meta["totals"]
    print(f"OK: {pdf.name} | {meta['page_count']}p | {t['characters']:,} chars | "
          f"{t['embedded_images']} img | {t['figure_crops']} fig | {t['tables']} tbl"
          + (f" | {len(meta['warnings'])} warning(s)" if meta["warnings"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
