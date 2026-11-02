"""Extract every PDF of a folder into an organised output folder: one subfolder per paper, named after the paper's title.

    <output>/<title>/
        <title>.pdf            a copy of the paper, named after its title (the original file name is kept in report.json)
        full_text.txt          the verified full text, page by page ("===== Page n / N =====")
        full_text.md           the same text broken into its sections, with the pages each runs over
        sections.json          the sections, with every page of text they hold
        pages/page_NNNN.txt    the verified text of each page
        figures/, tables/      figures and tables as images (tables also as CSV)
        report.json            how every page was read and checked, and its confidence
    <output>/index.json        every paper with its confidence
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
import shutil
import unicodedata
from pathlib import Path

from . import __version__
from . import engines as E
from . import figures as F
from . import ocr as O
from . import sections as S
from . import title as TI
from . import verify as V

ATTENTION = 0.95          # a page below this confidence is listed for a look


MARK = ".pdf-text-extractor.json"      # written into every paper folder the app makes: only such a folder is ever replaced
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_name(stem: str) -> str:
    """A folder or file name valid on Windows and macOS alike ("Title: subtitle" becomes "Title - subtitle"), cut at a word to
    stay inside Windows' limit on the length of a path."""
    t = unicodedata.normalize("NFKC", stem)
    t = re.sub(r"\s*:\s*", " - ", t)
    t = re.sub(r"[\\/|]+", "-", t)
    t = re.sub(r"[*?\"<>\x00-\x1f]+", "", t)
    t = re.sub(r"\s+", " ", t).strip(" .-")
    if len(t) > 80:
        cut = t[:80]
        t = (cut[:cut.rfind(" ")] if " " in cut[40:] else cut).rstrip(" .-,;")
    name = t or "paper"
    return f"{name}-" if name.split(".")[0].upper() in WINDOWS_RESERVED else name


def paper_folder(pdf: Path, out_root: Path, base: str) -> Path:
    """The paper's own folder. The app's earlier extraction of the same file is replaced; a folder of that name that holds anything
    else (another paper whose name reads the same, or folders the app did not make) is left alone and the next name is taken."""
    for k in range(1, 1000):
        out = out_root / (base if k == 1 else f"{base} ({k})")
        if not out.exists():
            return out
        try:
            if out.is_dir() and json.loads((out / MARK).read_text(encoding="utf-8"))["file"] == pdf.name:
                shutil.rmtree(out)
                return out
        except (OSError, ValueError, KeyError, TypeError):
            pass
    raise RuntimeError("the output folder has no free folder name for this paper")


def finished_folder(pdf: Path, out_root: Path) -> Path | None:
    """The app's finished extraction of this very file (same name, same contents), if the output folder holds one."""
    digest = None
    for mark in out_root.glob(f"*/{MARK}"):
        try:
            if json.loads(mark.read_text(encoding="utf-8"))["file"] != pdf.name:
                continue
            rep = json.loads((mark.parent / "report.json").read_text(encoding="utf-8"))
            digest = digest or sha256(pdf)
            if rep.get("sha256") == digest:
                return mark.parent
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def summary_of(folder: Path) -> dict:
    """What process_pdf returns, read back from a finished folder's report."""
    r = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    return {"paper": folder.name, "title": r.get("title", ""), "folder": str(folder), "pages": r["pages"], "confidence": r["confidence"],
            "pages_needing_a_look": r["pages_needing_a_look"], "sections": r["sections"]["count"],
            "figures": len(r["figures"]), "tables": len(r["tables"])}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def process_pdf(pdf: Path, out_root: Path, use_ocr: bool = True, progress=None, stop=None) -> dict:
    """Extract one PDF; progress(done, total, message) is called page by page; stop() may end it early."""
    import pymupdf
    doc = pymupdf.open(pdf)
    if doc.needs_pass:
        raise RuntimeError("the PDF is protected by a password")
    title, title_from = TI.title_of(doc, pdf.stem)
    name = safe_name(title)
    out = paper_folder(pdf, out_root, name)
    out.mkdir(parents=True)
    (out / MARK).write_text(json.dumps({"file": pdf.name, "app_version": __version__}), encoding="utf-8")
    say = progress or (lambda *a: None)
    say(0, doc.page_count, "reading the text layer with three engines")
    texts = {"MuPDF": E.mupdf_pages(doc), "PDFium": E.pdfium_pages(pdf), "pdfminer": E.pdfminer_pages(pdf, doc.page_count)}
    reordered = E.reordered_pages(doc)                     # the text layer's own lines in the order of the page's layout
    ocr_engines = O.engines() if use_ocr else []
    results, saved = [], []
    for i in range(doc.page_count):
        if stop and stop():
            raise InterruptedError("stopped")
        page = doc[i]
        say(i, doc.page_count, f"page {i + 1} of {doc.page_count}: figures, tables, OCR and checks")
        items = F.save(page, i + 1, out)
        saved += items
        regions = [pymupdf.Rect(x["bbox"]) for x in items]
        results.append(V.verify_page(doc, i, texts, ocr_engines, regions, use_ocr, reordered[i]))
    pages = [r.text for r in results]
    (out / "pages").mkdir()
    for r in results:
        (out / "pages" / f"page_{r.page:04d}.txt").write_text(r.text, encoding="utf-8")
    total = len(results)
    with open(out / "full_text.txt", "w", encoding="utf-8") as fh:
        for r in results:
            fh.write(f"===== Page {r.page} / {total}{' (' + r.source + ')' if r.source != 'text layer' else ''} =====\n\n{r.text.strip()}\n\n")
    say(total, total, "breaking the text into sections")
    secs = S.sections_of(doc, pages, {r.page for r in results if r.source.startswith("OCR")})
    (out / "sections.json").write_text(json.dumps(secs, indent=1, ensure_ascii=False), encoding="utf-8")
    md = []
    for s in secs["sections"]:
        pages_ = s["pages"]
        where = f"p. {pages_[0]}" if pages_ and pages_[0] == pages_[1] else f"pp. {pages_[0]}–{pages_[1]}" if pages_ else ""
        head = s["title"] if s["level"] == 0 else f"{(s['number'] + ' ') if s['number'] else ''}{s['title']}"
        md.append(f"{'#' * min(6, s['level'] + 1)} {head}  ({where})\n")
        for c in s["chunks"]:
            md.append(f"[p. {c['page']}]\n{c['text'].strip()}\n")
    (out / "full_text.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    shutil.copy2(pdf, out / f"{name}.pdf")
    weights = [max(200, len(r.text)) for r in results]
    conf = round(sum(w * r.confidence for w, r in zip(weights, results)) / max(1, sum(weights)), 4)
    report = {
        "file": pdf.name, "title": title, "title_from": title_from, "sha256": sha256(pdf), "pages": total, "extracted": datetime.datetime.now().isoformat(timespec="seconds"),
        "app_version": __version__,
        "text_engines": [k for k, v in texts.items() if v is not None], "ocr_engines": [e.name for e in ocr_engines],
        "confidence": conf, "pages_needing_a_look": [r.page for r in results if r.confidence < ATTENTION],
        "sections": {k: secs[k] for k in ("mode", "scheme", "numbering_runs_on", "skipped", "lossless")} | {"count": len(secs["sections"])},
        "figures": [x for x in saved if x["kind"] == "figure"], "tables": [x for x in saved if x["kind"] == "table"],
        "page_results": [{"page": r.page, "source": r.source, "confidence": r.confidence, "notes": r.notes, "metrics": r.metrics}
                         for r in results]}
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"paper": out.name, "title": title, "folder": str(out), "pages": total, "confidence": conf,
            "pages_needing_a_look": report["pages_needing_a_look"], "sections": len(secs["sections"]),
            "figures": len(report["figures"]), "tables": len(report["tables"])}


def write_index(out_root: Path) -> list[dict]:
    rows = []
    for rep in sorted(out_root.glob("*/report.json")):
        r = json.loads(rep.read_text(encoding="utf-8"))
        rows.append({"paper": rep.parent.name, "title": r.get("title", ""), "file": r["file"], "pages": r["pages"], "confidence": r["confidence"],
                     "pages_needing_a_look": r["pages_needing_a_look"], "sections": r["sections"]["count"],
                     "figures": len(r["figures"]), "tables": len(r["tables"])})
    (out_root / "index.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    return rows


def pdfs_in(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf" and not p.name.startswith("._"))
