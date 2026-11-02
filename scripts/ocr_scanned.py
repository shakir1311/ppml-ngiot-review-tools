#!/usr/bin/env python3
"""OCR the pages of an extraction that carry no text layer.

Uses Apple's Vision framework (built into macOS) so no external OCR engine is
needed. Operates on the page renders an extraction folder already contains.

For each page whose extracted text is empty or near-empty it writes:

    text/pages_ocr/page_NNNN.txt   OCR text for that page
    text/full_ocr.txt              all OCR'd pages, page-delimited

and it rewrites `text/full.txt` (page_text.assemble_full_text) so OCR text stands
in for the blank pages, marked as OCR so the provenance stays visible. `metadata.json` records what
was OCR'd and the mean per-page confidence.

A page whose text layer holds only a publisher's stamp or running head over a page image is OCR'd as well when it is named
(--pages, as verify_ocr.py --apply does when OCR of the rendered page reads far more than the text layer) or falls under a
raised --threshold: where OCR reads more than STANDS_IN_RATIO times the characters of the text layer, the page is marked
"ocr_stands_in" in metadata.json and its OCR text stands in for it in text/full.txt (page_text.assemble_full_text and
check_extraction.py honour the mark). OCR of named pages is merged with any earlier OCR of the paper.

    ocr_scanned.py <extraction-folder> [...] [--threshold N] [--force] [--pages N ...]
    ocr_scanned.py --manifest [--manifest-file PATH]   OCR every paper of the manifest that has such pages
"""

from __future__ import annotations

import argparse
import collections
import csv
import difflib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

import pymupdf
import Quartz

import corpus as C
import page_text as PT
import Vision
from Foundation import NSURL

DEFAULT_THRESHOLD = 100   # chars/page below which a page is treated as scanned
STANDS_IN_RATIO = 3       # with a raised --threshold: OCR text also stands in for a page whose text layer holds under a third of
                          # what OCR reads on it (a page image under a publisher's stamp or running head); the page is marked
                          # "ocr_stands_in" in metadata.json, which page_text.assemble_full_text and check_extraction.py honour
OCR_DPI = 300             # re-render resolution for OCR; 150 loses small type
PAGE_MARKER = "========== [ PAGE {n} / {total} ] =========="
OCR_MARKER = "========== [ PAGE {n} / {total} — OCR (no text layer in PDF) ] =========="


def ocr_image(path: Path, languages: list[str]) -> tuple[str, float]:
    """Return (text, mean_confidence) for one image file."""
    url = NSURL.fileURLWithPath_(str(path))
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    if src is None:
        raise RuntimeError(f"could not open image: {path}")
    image = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    if image is None:
        raise RuntimeError(f"could not decode image: {path}")

    lines: list[str] = []
    confidences: list[float] = []

    def handler(request, error):
        if error:
            return
        for obs in request.results() or []:
            cand = obs.topCandidates_(1)
            if cand and len(cand):
                lines.append(cand[0].string())
                confidences.append(float(cand[0].confidence()))

    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    if languages:
        request.setRecognitionLanguages_(languages)

    handler_obj = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, err = handler_obj.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision request failed: {err}")

    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return "\n".join(lines), mean_conf


def vision_lines(img: Path) -> list[tuple]:
    """Apple Vision, line by line: [(text, x0, y0, x1, y1, confidence)], boxes as shares of the image (origin top left)."""
    url = NSURL.fileURLWithPath_(str(img))
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    image = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None) if src is not None else None
    if image is None:
        raise RuntimeError(f"could not open image: {img}")
    out: list[tuple] = []

    def handler(request, error):
        for obs in (request.results() or []):
            cand = obs.topCandidates_(1)
            if cand and len(cand):
                bb = obs.boundingBox()
                x0, y0 = bb.origin.x, 1 - (bb.origin.y + bb.size.height)
                out.append((cand[0].string(), x0, y0, x0 + bb.size.width, y0 + bb.size.height, float(cand[0].confidence())))
    req = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(True)
    ok, err = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None).performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision request failed: {err}")
    return out


def joined_by_neighbours(lines: list[tuple]):
    """For a page without a text layer: a line that crosses the middle while both columns run on just above and just below it
    is two column lines that OCR joined across the gutter."""
    spans = lambda l: l[1] < 0.45 and l[3] > 0.55
    left = [l for l in lines if not spans(l) and (l[1] + l[3]) / 2 < 0.5]
    right = [l for l in lines if not spans(l) and (l[1] + l[3]) / 2 >= 0.5]

    def joined(l: tuple) -> bool:
        h = max(0.004, l[4] - l[2])
        near = lambda side, lo, hi: any(lo <= (m[2] + m[4]) / 2 <= hi for m in side)
        return (near(left, l[2] - 2.5 * h, l[2]) and near(right, l[2] - 2.5 * h, l[2])
                and near(left, l[4], l[4] + 2.5 * h) and near(right, l[4], l[4] + 2.5 * h))
    return joined


def joined_by_layout(side_by_side: list[tuple[float, float]]):
    """For a page with a text layer: a line that crosses the middle is two column lines joined by OCR only where the text layer
    has a line in each column side by side at that height (side_by_side: those heights, as shares of the page)."""
    return lambda l: any(y0 <= (l[2] + l[4]) / 2 <= y1 for y0, y1 in side_by_side)


def column_order(lines: list[tuple], joined=None) -> list[tuple]:
    """Lines in reading order: bands separated by lines that span the middle of the page; in each band the left column top to
    bottom, then the right column. Vision returns lines top to bottom across the page, which on a two-column page interleaves
    the columns; this puts them in the order a reader reads them. joined(line) marks the lines that cross the middle but are
    two column lines OCR joined across the gutter: they stay with the left column and do not cut the page into bands."""
    spans = lambda l: l[1] < 0.45 and l[3] > 0.55
    glued = {id(l) for l in lines if spans(l) and joined is not None and joined(l)}
    spanning = sorted((l for l in lines if spans(l) and id(l) not in glued), key=lambda l: l[2])
    rest = [l for l in lines if not spans(l) or id(l) in glued]
    on_left = lambda l: id(l) in glued or (l[1] + l[3]) / 2 < 0.5
    out, top = [], -1.0
    for cut in spanning + [None]:
        bottom = cut[2] if cut else 2.0
        band = [l for l in rest if top <= (l[2] + l[4]) / 2 < bottom]
        out += sorted((l for l in band if on_left(l)), key=lambda l: l[2])
        out += sorted((l for l in band if not on_left(l)), key=lambda l: l[2])
        if cut:
            out.append(cut)
            top = cut[2]
    return out


# ------------------------------------------------------------------------------- Tesseract, the second OCR engine (optional)
TESSERACT = shutil.which("tesseract")
_WORDS: set[str] | None = None


def tesseract_version() -> str | None:
    if not TESSERACT:
        return None
    out = subprocess.run([TESSERACT, "--version"], capture_output=True).stdout.decode(errors="replace").split()
    return f"Tesseract {out[1]}" if len(out) > 1 else "Tesseract"


def tesseract_words(img: Path) -> list[tuple]:
    """Tesseract (eng, automatic page segmentation): [(word, x0, y0, x1, y1, confidence, line key)], boxes as shares."""
    r = subprocess.run([TESSERACT, str(img), "stdout", "-l", "eng", "--psm", "3", "tsv"], capture_output=True, timeout=600)
    out, w, h = [], 1.0, 1.0
    for row in csv.DictReader(io.StringIO(r.stdout.decode("utf-8", errors="replace")), delimiter="\t"):
        if row["level"] == "1":
            w, h = float(row["width"]), float(row["height"])
        elif row["level"] == "5" and row["text"].strip():
            x0, y0 = float(row["left"]) / w, float(row["top"]) / h
            out.append((row["text"], x0, y0, x0 + float(row["width"]) / w, y0 + float(row["height"]) / h, float(row["conf"]),
                        (row["block_num"], row["par_num"], row["line_num"])))
    return out


def tesseract_text(words: list[tuple]) -> str:
    lines: dict = collections.OrderedDict()
    for t in words:
        lines.setdefault(t[6], []).append(t[0])
    return "\n".join(" ".join(ws) for ws in lines.values())


def is_word(token: str) -> bool:
    global _WORDS
    if _WORDS is None:
        _WORDS = {x.strip().lower() for x in open("/usr/share/dict/words", encoding="utf-8", errors="ignore") if x.strip()}
    w = re.sub(r"[^a-z]", "", unicodedata.normalize("NFKC", token).lower())
    return len(w) >= 2 and w in _WORDS


def arbitrate(vlines: list[tuple], twords: list[tuple]) -> tuple[list[str], int]:
    """Vision's lines, word by word against the Tesseract words inside each line's box: where both read the same span with as
    many words, and Vision's word is not a dictionary word while Tesseract's similar word is, Tesseract's word is taken (a
    misreading by Vision). -> (lines, number of words taken from Tesseract)"""
    out, fixed = [], 0
    for v in vlines:
        inside = sorted((t for t in twords if v[1] - 0.01 <= (t[1] + t[3]) / 2 <= v[3] + 0.01
                         and v[2] - 0.005 <= (t[2] + t[4]) / 2 <= v[4] + 0.005), key=lambda t: t[1])
        a, b = v[0].split(), [t[0] for t in inside]
        new = list(a)
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if op == "replace" and i2 - i1 == j2 - j1:
                for k in range(i2 - i1):
                    x, y = a[i1 + k], b[j1 + k]
                    if not is_word(x) and is_word(y) and difflib.SequenceMatcher(None, x.lower(), y.lower()).ratio() >= 0.6:
                        new[i1 + k] = y
                        fixed += 1
        out.append(" ".join(new) if new != a else v[0])
    return out, fixed


def source_pdf_for(folder: Path, meta: dict) -> Path | None:
    """Locate the PDF an extraction folder came from, if it is still there."""
    name = meta.get("source_pdf")
    if not name:
        return None
    # The PDF may sit inside its extraction folder or alongside it.
    for candidate in (folder / name, folder.parent / name):
        if candidate.is_file():
            return candidate
    return None


def render_page_for_ocr(pdf: Path, pno: int, dpi: int, tmpdir: Path) -> Path:
    """Render one page at OCR resolution; sharper than the stored 150dpi render."""
    doc = pymupdf.open(str(pdf))
    try:
        pix = doc[pno - 1].get_pixmap(dpi=dpi)
        if pix.colorspace and pix.colorspace.n > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        out = tmpdir / f"ocr_page_{pno:04d}.png"
        pix.save(str(out))
        return out
    finally:
        doc.close()


def scanned_pages(meta: dict, threshold: int) -> list[int]:
    return [p["page"] for p in meta.get("pages", []) if p.get("chars", 0) < threshold]


def process(folder: Path, threshold: int, languages: list[str], force: bool,
            dpi: int = OCR_DPI, pages: list[int] | None = None) -> dict:
    """OCR the pages under the threshold, or the pages named (merged with any earlier OCR of the paper)."""
    meta_path = folder / "metadata.json"
    if not meta_path.exists():
        raise RuntimeError(f"not an extraction folder (no metadata.json): {folder}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    if meta.get("ocr") and not force and not pages:
        return {"folder": folder.name, "status": "already OCR'd",
                "pages_ocr": len(meta["ocr"].get("pages", []))}

    targets = sorted(set(pages)) if pages else scanned_pages(meta, threshold)
    if not targets:
        return {"folder": folder.name, "status": "no pages need OCR", "pages_ocr": 0}

    page_img_dir = folder / "images" / "pages"
    ocr_dir = folder / "text" / "pages_ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)

    total = meta["page_count"]
    results: list[dict] = []
    ocr_text: dict[int, str] = {}
    pdf = source_pdf_for(folder, meta)
    render_dpi = dpi if pdf else meta.get("extracted_with", {}).get("page_render_dpi")

    tmp = tempfile.TemporaryDirectory()
    tmpdir = Path(tmp.name)
    for pno in targets:
        img = None
        if pdf:
            try:
                img = render_page_for_ocr(pdf, pno, dpi, tmpdir)
            except Exception:  # noqa: BLE001 - fall back to the stored render
                img = None
        if img is None:
            img = page_img_dir / f"page_{pno:04d}.png"
        if not img.exists():
            results.append({"page": pno, "error": "no page image available"})
            continue
        try:
            raw = vision_lines(img)
            vl = column_order(raw, joined_by_neighbours(raw))   # two columns read column by column; lines joined across the gutter
        except Exception as exc:  # noqa: BLE001 - one bad page must not stop the rest
            results.append({"page": pno, "error": str(exc)})
            continue
        lines, fixed, second = [l[0] for l in vl], 0, None
        if TESSERACT:                       # the second engine: arbitration word by word, and its reading kept as a variant
            try:
                tw = tesseract_words(img)
                lines, fixed = arbitrate(vl, tw)
                second = tesseract_text(tw)
                (folder / "text" / "variants" / f"page_{pno:04d}.tesseract.txt").write_text(second, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001 - Vision's reading stands without it
                print(f"  page {pno:>3}: Tesseract failed: {exc}", file=sys.stderr)
        text = "\n".join(lines)
        conf = sum(l[5] for l in vl) / len(vl) if vl else 0.0
        (ocr_dir / f"page_{pno:04d}.txt").write_text(text, encoding="utf-8")
        ocr_text[pno] = text
        results.append({"page": pno, "chars": len(text), "mean_confidence": round(conf, 4),
                        **({"words_taken_from_tesseract": fixed} if second is not None else {})})
        print(f"  page {pno:>3}: {len(text):>6} chars, conf {conf:.3f}", file=sys.stderr)
    tmp.cleanup()

    if pages and meta.get("ocr"):        # pages named: keep the earlier OCR of the other pages
        earlier = {r["page"]: r for r in meta["ocr"].get("pages", []) if r["page"] not in ocr_text}
        results = [earlier.get(k) or next(r for r in results if r["page"] == k) for k in sorted(set(earlier) | {r["page"] for r in results})]
        for f in sorted(ocr_dir.glob("page_*.txt")):
            k = int(f.stem.split("_")[1])
            ocr_text.setdefault(k, f.read_text(encoding="utf-8"))
    stands_in = []                       # a text layer that is only a stamp or a running head over a page image
    for p in meta.get("pages", []):
        n = p["page"]
        if n in ocr_text and p.get("chars", 0) >= 100 and len(ocr_text[n]) > STANDS_IN_RATIO * p.get("chars", 0):
            p["ocr_stands_in"] = True
        if p.get("ocr_stands_in"):
            stands_in.append(n)
    if ocr_text:
        combined = "\n\n".join(
            OCR_MARKER.format(n=p, total=total) + "\n\n" + ocr_text[p]
            for p in sorted(ocr_text)
        )
        PT.write_atomic(folder / "text" / "full_ocr.txt", combined)
        PT.write_atomic(folder / "text" / "full.txt", PT.assemble_full_text(folder, meta["pages"]))

    conf_values = [r["mean_confidence"] for r in results if "mean_confidence" in r]
    meta["ocr"] = {
        "engine": "Apple Vision (VNRecognizeTextRequest, accurate)",
        "second_engine": (tesseract_version() + " (eng, page segmentation 3): words where Vision reads a non-word and "
                          "Tesseract a similar dictionary word taken from Tesseract; its reading kept as text/variants/page_NNNN.tesseract.txt")
                         if TESSERACT else "not installed",
        "languages": languages or ["auto"],
        "threshold_chars_per_page": threshold,
        "ocr_render_dpi": render_dpi,
        "pages": results,
        "mean_confidence": round(sum(conf_values) / len(conf_values), 4)
        if conf_values else None,
        "characters_recovered": sum(len(t) for t in ocr_text.values()),
        "pages_where_ocr_stands_in": stands_in,
    }
    meta.setdefault("warnings", []).append(
        f"{len(ocr_text)} page(s) had no text layer and were recovered by OCR "
        f"(see text/pages_ocr/ and text/full_ocr.txt)"
    )
    PT.write_atomic(meta_path, json.dumps(meta, indent=2, ensure_ascii=False))

    return {"folder": folder.name, "status": "ocr complete",
            "pages_ocr": len(ocr_text),
            "characters_recovered": meta["ocr"]["characters_recovered"],
            "mean_confidence": meta["ocr"]["mean_confidence"]}


def find_candidates(threshold: int, manifest: Path | None = None) -> list[Path]:
    """Every paper of the manifest (or of another manifest of the same form) with at least one page whose text layer
    holds almost nothing."""
    out: list[Path] = []
    for entry in C.load_manifest(manifest):
        meta_path = C.folder_of(entry) / "metadata.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if scanned_pages(meta, threshold):
            out.append(meta_path.parent)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="*", type=Path)
    ap.add_argument("--manifest", action="store_true",
                    help="OCR every paper of the manifest that has pages without a text layer")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    ap.add_argument("--lang", default="en-US",
                    help="comma-separated Vision language codes")
    ap.add_argument("--dpi", type=int, default=OCR_DPI,
                    help="re-render resolution for OCR (default %(default)s)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--pages", nargs="*", type=int, help="OCR these pages (of each folder given), merged with earlier OCR")
    ap.add_argument("--manifest-file", type=Path, help="with --manifest: another manifest of the same form")
    args = ap.parse_args()

    languages = [s for s in args.lang.split(",") if s.strip()]
    folders = list(args.folders)
    if args.manifest:
        folders += find_candidates(args.threshold, args.manifest_file)
    if not folders:
        print("No paper has pages without a text layer." if args.manifest else
              "Nothing to do. Pass extraction folders or --manifest.", file=sys.stderr)
        return 0

    rc = 0
    for folder in folders:
        folder = folder.resolve()
        print(f"OCR: {folder.name}", file=sys.stderr)
        try:
            res = process(folder, args.threshold, languages, args.force, args.dpi, args.pages)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {folder.name}: {exc}")
            rc = 1
            continue
        extra = ""
        if res.get("characters_recovered"):
            extra = (f" | {res['characters_recovered']:,} chars recovered"
                     f" | conf {res['mean_confidence']}")
        print(f"{res['status']}: {res['folder']} ({res['pages_ocr']} page(s)){extra}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
