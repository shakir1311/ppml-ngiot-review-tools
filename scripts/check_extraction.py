#!/usr/bin/env python3
"""Audit of the mechanical extraction: every page of every paper is checked again, from the PDF itself.

For each paper in the manifest:

  1. the PDF is the file registered in the manifest (SHA-256) and it opens;
  2. the folder holds the text, the metadata, and one text file, one render and the variants for every page;
  3. every page text on disk is exactly what PyMuPDF gives for that page now — the page is extracted again and
     compared — and its SHA-1 is the one recorded in metadata.json (no stale, half-written or altered file);
  4. text/full.txt holds every page, in order, each identical to its page file (or to its OCR text);
  5. nothing is missing: the letters and digits that pdftotext and PDFKit both find on a page are in the reading text;
  6. the reading order of every page is confirmed by a second engine; pages that are not are listed for a check
     by eye against the page render;
  7. every page without a text layer has OCR text;
  8. no failure marker and no temporary file is left behind;
  9. the folder holds nothing of unknown origin: every file is one this mechanism writes, and the figures, embedded
     images and tables on disk are exactly those recorded in metadata.json.

Checks 1–4 and 7–9 must hold for the audit to pass. Checks 5 and 6 list pages for a person (or a reader) to look at.

 11. where the folder holds text/sections.json (sections.py), the sections hold text/full.txt exactly — every character in one
     section, nothing added — and their numbering runs on (or every entry of the PDF's outline is found); a section cut that
     loses or adds text is an error, a numbering that skips is listed.
 10. where the folder holds ocr_check.json (verify_ocr.py), every page was compared with local OCR of the rendered page: the
     pages where OCR sees text the reading text lacks, text that is not visible, a page image whose text only OCR can give,
     or an order that OCR does not confirm either are listed; for a page of check 5, OCR shows whether any visible text is
     really lacking. An ocr_check.json made for another PDF is an error.

    check_extraction.py [--manifest PATH] [--ids S007 ...] [--json OUT.json] [--report OUT.html]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path

import pymupdf

import corpus as C
import page_text as PT

REQUIRED = ["text/full.txt", "text/full.md", "text/full_layout.txt", "text/pages", "text/variants", "images/pages",
            "metadata.json"]
KNOWN = [r"[^/]+\.pdf", r"README\.md", r"metadata\.json", r"text/full\.txt", r"text/full\.md", r"text/full_layout\.txt",
         r"text/full_ocr\.txt", r"text/pages/page_\d{4}\.txt", r"text/variants/page_\d{4}\.(poppler|pdfkit|pdfminer|reordered|tesseract|graphics-ocr)\.txt",
         r"text/pages_ocr/page_\d{4}\.txt", r"images/pages/page_\d{4}\.png", r"images/(embedded|figures|crops)/[^/]+",
         r"tables/[^/]+", r"notes/(NOTES\.md|SUMMARY\.md|LINKS\.json|check\.json)",
         r"PROVENANCE\.json", r"ocr_check\.json", r"text/sections\.(json|md)"]       # the filing record of a downloaded report; the OCR verification
MISSING_SHARE = 0.01     # a page is listed when the reading text lacks more than this share of the letters and
MISSING_COUNT = 40       # digits that both witnesses hold, and more than this many of them
LITTLE_TEXT = 100


def audit(entry: dict) -> dict:
    d = C.folder_of(entry)
    row = {"id": entry["id"], "folder": entry["folder"], "pages": entry["pages"], "errors": [], "unconfirmed": [],
           "possibly_incomplete": [], "too_little_text": [], "ocr_pages": [], "confirmed": 0, "characters": 0,
           "ocr_verified": 0, "ocr_flagged": [], "sections": None, "sections_numbering_runs_on": None}
    err = row["errors"]
    pdf = d / entry["pdf"]
    if not pdf.is_file():
        err.append("the PDF is not in the folder")
        return row
    if C.sha256_of(pdf) != entry["sha256"]:
        err.append("the PDF is not the file registered in the manifest (SHA-256 differs)")
    err += [f"missing {r}" for r in REQUIRED if not (d / r).exists()]
    if (d / "EXTRACTION_FAILED.txt").exists():
        err.append("failure marker EXTRACTION_FAILED.txt is present")
    leftovers = [f.relative_to(d).as_posix() for f in d.rglob("*.tmp")]
    if leftovers:
        err.append(f"temporary files left behind: {leftovers[:5]}")
    if err:
        return row
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    pages_meta = {p["page"]: p for p in meta.get("pages", [])}

    unknown = [f.relative_to(d).as_posix() for f in d.rglob("*")
               if f.is_file() and f.name != ".DS_Store" and not f.name.startswith("._")
               and not any(re.fullmatch(k, f.relative_to(d).as_posix()) for k in KNOWN)]
    if unknown:
        err.append(f"{len(unknown)} file(s) this mechanism does not write: {unknown[:4]}")
    for sub, inventory in (("images/figures", "figure_inventory"), ("images/embedded", "embedded_image_inventory")):
        recorded = {x["file"] for x in meta.get(inventory, []) if x.get("file")}
        on_disk = {f.name for f in (d / sub).glob("*") if f.is_file() and not f.name.startswith(".")} if (d / sub).is_dir() else set()
        if recorded != on_disk:
            err.append(f"{sub}: {len(on_disk - recorded)} file(s) on disk that metadata.json does not record, "
                       f"{len(recorded - on_disk)} recorded but not on disk")
    recorded = {Path(x["file"]).stem for x in meta.get("table_inventory", []) if x.get("file")}     # a CSV and a .md each
    on_disk = {f.stem for f in (d / "tables").glob("*") if f.is_file() and not f.name.startswith(".")} if (d / "tables").is_dir() else set()
    if recorded != on_disk:
        err.append(f"tables: {len(on_disk - recorded)} table(s) on disk that metadata.json does not record, "
                   f"{len(recorded - on_disk)} recorded but not on disk")

    with pymupdf.open(pdf) as doc:
        total = doc.page_count
        if total != entry["pages"]:
            err.append(f"the PDF has {total} pages, the manifest says {entry['pages']}")
        for kind, folder, pattern in (("page texts", d / "text" / "pages", "page_*.txt"),
                                      ("page renders", d / "images" / "pages", "page_*.png")):
            n = len(list(folder.glob(pattern)))
            if n != total:
                err.append(f"{n} {kind} for {total} pages")
        for variant in PT.VARIANTS:
            n = len(list((d / "text" / "variants").glob(f"page_*.{variant}.txt")))
            if n != total:
                err.append(f"{n} '{variant}' variants for {total} pages")
        if len(pages_meta) != total:
            err.append(f"metadata.json describes {len(pages_meta)} pages for {total}")
        if err:
            return row

        bodies: dict[int, str] = {}
        for pno0, page in enumerate(doc):
            n = pno0 + 1
            stored = PT.read_exact(d / "text" / "pages" / f"page_{n:04d}.txt")
            again = PT.pymupdf_text(page)
            if stored != again:
                err.append(f"p{n}: the text on disk is not what PyMuPDF gives for the page")
            if PT.sha1(stored) != pages_meta[n].get("text_sha1"):
                err.append(f"p{n}: the text on disk does not carry the SHA-1 recorded in metadata.json")
            row["characters"] += len(stored.strip())
            ocr = d / "text" / "pages_ocr" / f"page_{n:04d}.txt"
            bodies[n] = stored
            if len(stored.strip()) < LITTLE_TEXT or pages_meta[n].get("ocr_stands_in"):
                if ocr.exists():
                    row["ocr_pages"].append(n)
                    bodies[n] = PT.read_exact(ocr)
                else:
                    err.append(f"p{n}: almost no text layer and no OCR text")

            pop = PT.read_exact(d / "text" / "variants" / f"page_{n:04d}.poppler.txt")
            kit = PT.read_exact(d / "text" / "variants" / f"page_{n:04d}.pdfkit.txt")
            src = pages_meta[n].get("reading_order_from")
            if src in PT.STANDS_IN and bodies[n] is stored:                                     # verify_ocr.py --apply
                bodies[n] = PT.read_exact(d / "text" / "variants" / f"page_{n:04d}.{src}.txt")
            both = PT.characters(pop) & PT.characters(kit)
            lacking = both - PT.characters(stored)
            count = sum(lacking.values())
            if count > MISSING_COUNT and count > MISSING_SHARE * max(1, sum(both.values())):
                row["possibly_incomplete"].append({"page": n, "characters": count,
                                                   "share": round(count / sum(both.values()), 4)})
            status = pages_meta[n].get("order_status")
            if status == "confirmed":
                row["confirmed"] += 1
            elif status == "too little text":
                row["too_little_text"].append(n)
            elif status == "unconfirmed":
                row["unconfirmed"].append({"page": n, "agreement": pages_meta[n].get("agreement"),
                                           "checked_by_eye": pages_meta[n].get("order_checked_by_eye")})
            else:
                err.append(f"p{n}: no verdict on the reading order in metadata.json")

    full = PT.read_exact(d / "text" / "full.txt")
    marks = list(C.PAGE_MARKER.finditer(full))
    if [int(m.group(1)) for m in marks] != list(range(1, total + 1)):
        err.append("text/full.txt does not hold the pages 1 to N in order")
    else:
        for i, m in enumerate(marks):
            body = full[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(full)]
            if body.strip() != bodies[i + 1].strip():
                err.append(f"p{i + 1}: text/full.txt differs from the page text")
    sec_path = d / "text" / "sections.json"                              # check 11: the sections hold full.txt exactly
    if sec_path.exists():
        sec = json.loads(sec_path.read_text(encoding="utf-8"))
        cut = "".join(c["text"] for s in sec.get("sections", []) for c in s.get("chunks", []))
        whole = "".join(full[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(full)] for i, m in enumerate(marks))
        if cut != whole:
            err.append("text/sections.json does not hold text/full.txt exactly: run sections.py again")
        row["sections"] = len(sec.get("sections", []))
        row["sections_numbering_runs_on"] = sec.get("numbering_runs_on")
    oc_path = d / "ocr_check.json"                                       # check 10: the OCR verification, where it was run
    if oc_path.exists():
        oc = json.loads(oc_path.read_text(encoding="utf-8"))
        if oc.get("pdf_sha256") != entry["sha256"]:
            err.append("ocr_check.json was made for another PDF (SHA-256 differs): run verify_ocr.py again")
        else:
            byp = {p["page"]: p for p in oc.get("pages", [])}
            row["ocr_verified"] = len(byp)
            row["ocr_flagged"] = [{"page": p["page"], "flags": p["flags"], "missing": p["missing"], "invisible": p["invisible"],
                                   "order_agreement": p["order_agreement"]} for p in oc.get("pages", []) if p.get("flags")]
            for u in row["possibly_incomplete"]:
                q = byp.get(u["page"], {})
                u["ocr_missing"] = q.get("missing")
                u["ocr_clear"] = bool(q) and "missing" not in q.get("flags", [])
    return row


def report(out: dict, path: str) -> None:
    e = html.escape
    rows = out["rows"]
    bad = [r for r in rows if r["errors"]]
    unconf = [(r, u) for r in rows for u in r["unconfirmed"]]
    incomplete = [(r, u) for r in rows for u in r["possibly_incomplete"]]

    def score(a):
        return " · ".join(f"{e(k)} {v:.2f}" if v is not None else f"{e(k)} —" for k, v in (a or {}).items())
    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Extraction audit — {e(out['date'])}</title>
<style>
:root {{ --ink:#1b1f24; --muted:#57606a; --line:#d0d7de; --ok:#1a7f37; --bad:#b42318; --soft:#f6f8fa; }}
* {{ box-sizing:border-box; }}
body {{ font:15px/1.5 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif; color:var(--ink); background:#fff;
       margin:0 auto; padding:24px 16px 48px; max-width:1100px; }}
h1 {{ font-size:1.6rem; margin:0 0 4px; }} h2 {{ font-size:1.15rem; margin:28px 0 8px; }}
p.sub {{ color:var(--muted); margin:0 0 16px; }}
table {{ border-collapse:collapse; width:100%; font-size:.9rem; table-layout:auto; }}
th,td {{ border:1px solid var(--line); padding:5px 8px; text-align:left; vertical-align:top; overflow-wrap:anywhere; }}
th {{ background:var(--soft); }} td.n {{ text-align:right; }}
td.n, td.k, th.k {{ white-space:nowrap; overflow-wrap:normal; }}
.ok {{ color:var(--ok); font-weight:600; }} .bad {{ color:var(--bad); font-weight:600; }}
.box {{ border:1px solid var(--line); border-left:4px solid var(--ok); background:var(--soft); padding:10px 14px;
        margin:12px 0; }}
.box.bad {{ border-left-color:var(--bad); font-weight:400; color:var(--ink); }}
.wrap {{ overflow-x:auto; }}
@page {{ size:auto; margin:14mm 12mm; }}
@media print {{
  body {{ max-width:none; padding:0; font-size:10.5pt; color:#000; background:#fff; }}
  .wrap {{ overflow-x:visible; }} table {{ font-size:9pt; }}
  th {{ background:#eee !important; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  tr, .box, h2 {{ break-inside:avoid; }} h2 {{ break-after:avoid; }} thead {{ display:table-header-group; }}
}}
</style></head><body>
<h1>Extraction audit</h1>
<p class="sub">{e(out['date'])} · {out['papers']} papers · {out['pages']} pages · made by <code>scripts/check_extraction.py</code></p>
<div class="box{'' if not bad else ' bad'}"><strong class="{'ok' if not bad else 'bad'}">{'PASS' if not bad else 'FAIL'}</strong> —
{out['papers'] - len(bad)} of {out['papers']} papers pass every check that must hold
(the PDF is the registered file; every page has its text, render and variants; the text on disk is exactly what
PyMuPDF gives for the page when it is extracted again; <code>full.txt</code> holds every page in order; pages without
a text layer have OCR text; nothing is left half-written).</div>
<h2>Summary</h2>
<div class="wrap"><table><tbody>
<tr><th>Pages whose text was extracted again and found identical</th><td class="n">{out['pages_identical']} of {out['pages']}</td></tr>
<tr><th>Characters of reading text</th><td class="n">{out['characters']:,}</td></tr>
<tr><th>Pages whose reading order is confirmed (by OCR of the page where it was verified)</th><td class="n">{out['pages_confirmed']}</td></tr>
<tr><th>Pages with too little running text for the order to matter (under about 80 words)</th><td class="n">{out['pages_too_little_text']}</td></tr>
<tr><th>Pages whose reading order is not confirmed — marked in <code>full.txt</code>, to be read against the page render</th><td class="n">{len(unconf)}</td></tr>
<tr><th>Pages where the reading text may lack text that both other engines hold</th><td class="n">{len(incomplete)}</td></tr>
<tr><th>Pages without a text layer, read by OCR</th><td class="n">{out['pages_ocr']}</td></tr>
<tr><th>Pages compared with local OCR of the rendered page (<code>verify_ocr.py</code>)</th><td class="n">{out.get('pages_ocr_verified', 0)}</td></tr>
<tr><th>Pages that OCR flags (visible text missing, text not visible, a page image, or an order OCR does not confirm)</th><td class="n">{out.get('pages_ocr_flagged', 0)}</td></tr>
</tbody></table></div>
<h2>How the reading order is confirmed</h2>
<p>The reading text of a page is what PyMuPDF returns in the order in which the PDF lays its text down. At extraction it
is compared with other readings of the same page — poppler's <code>pdftotext</code>, Apple's PDFKit, and the Markdown
rendering by pymupdf4llm — by the share of its eight-word runs that also run on in the other reading (0.80 confirms). That
agreement shows only that the readings share an order: readings built on the PDF's content order agree with it however it
runs. Where a paper is verified against OCR (<code>verify_ocr.py</code>), the order of the prose decides on every page:
OCR's lines of running prose must come in the same order in the page's reading — at least 90 % of at least five lines — by
Vision's column order or by Tesseract's own layout analysis. Where the text layer's reading falls short, or
<code>pdftotext</code>'s, PDFKit's or pdfminer's is clearly better or is put in order by both of OCR's orders, that reading
stands in for the page in <code>full.txt</code>. A page that no reading puts in OCR's order, or whose two OCR orders back different
readings (a full-width figure or table between the columns, read column by column or above it and then below it), is listed
to be read against the page render.</p>"""]
    if bad:
        parts.append("<h2>Papers that fail</h2><div class='wrap'><table><thead><tr><th>ID</th><th>Paper</th><th>Problems</th></tr></thead><tbody>")
        for r in bad:
            parts.append(f"<tr><td class='k'>{e(r['id'])}</td><td>{e(r['folder'])}</td><td>{'<br>'.join(e(x) for x in r['errors'][:12])}</td></tr>")
        parts.append("</tbody></table></div>")
    if unconf:
        parts.append("<h2>Pages to read against the page render</h2><p>Pages that are mainly a table, a figure with many "
                     "labels, a list of abbreviations or a reference list, where the engines differ in how they walk through "
                     "the cells or labels; and pages whose prose no reading puts in the order OCR sees (a sidebar, a boxed "
                     "algorithm or a list may be what OCR orders differently).</p><div class='wrap'><table><thead><tr><th class='k'>ID</th><th class='k'>Page</th>"
                     "<th>Agreement with each witness</th><th>Checked by eye</th><th>Paper</th></tr></thead><tbody>")
        for r, u in unconf:
            parts.append(f"<tr><td class='k'>{e(r['id'])}</td><td class='n'>{u['page']}</td><td>{score(u['agreement'])}</td>"
                         f"<td>{e(str(u['checked_by_eye'] or ''))}</td><td>{e(r['folder'].split('/')[-1])}</td></tr>")
        parts.append("</tbody></table></div>")
    if incomplete:
        main_corpus = Path(out.get("manifest", str(C.MANIFEST))).resolve() == C.MANIFEST.resolve()
        parts.append("<h2>Pages where the reading text may lack text</h2><p>"
                     + ("The pages of the corpus listed on 28 September 2026 were examined then: what the other engines hold in "
                        "addition is symbols of formulas read differently, text the PDF carries twice, or hidden data of figures "
                        "(for instance <code>sha1_base64</code> strings of formula images) — no visible text of a paper is lacking. "
                        if main_corpus else "")
                     + "Where the folder holds <code>ocr_check.json</code>, the last column gives the words that local OCR of the "
                       "rendered page sees and the reading text lacks: none means that what the other engines read in addition is not "
                       "visible on the page (hidden or off-page text, text carried twice, formula symbols).</p>"
                     "<div class='wrap'><table><thead><tr><th class='k'>ID</th>"
                     "<th class='k'>Page</th><th>Letters and digits lacking</th><th class='k'>Share</th><th class='k'>Visible words missing (OCR)</th>"
                     "<th>Paper</th></tr></thead><tbody>")
        for r, u in incomplete:
            ocr_col = "—" if u.get("ocr_missing") is None else ("none" if u.get("ocr_clear") else str(u["ocr_missing"]))
            parts.append(f"<tr><td class='k'>{e(r['id'])}</td><td class='n'>{u['page']}</td><td class='n'>{u['characters']}</td>"
                         f"<td class='n'>{u['share']:.1%}</td><td class='n'>{e(ocr_col)}</td><td>{e(r['folder'].split('/')[-1])}</td></tr>")
        parts.append("</tbody></table></div>")
    flagged = [(r, f) for r in rows for f in r.get("ocr_flagged", [])]
    if flagged:
        parts.append("<h2>Pages that OCR of the rendered page flags</h2><div class='wrap'><table><thead><tr><th class='k'>ID</th>"
                     "<th class='k'>Page</th><th>Flags</th><th class='k'>Visible words missing</th><th class='k'>Words not visible</th>"
                     "<th class='k'>Order (OCR)</th><th>Paper</th></tr></thead><tbody>")
        for r, f in flagged:
            parts.append(f"<tr><td class='k'>{e(r['id'])}</td><td class='n'>{f['page']}</td><td>{e(', '.join(f['flags']))}</td>"
                         f"<td class='n'>{f['missing']}</td><td class='n'>{f['invisible']}</td>"
                         f"<td class='n'>{'—' if f['order_agreement'] is None else format(f['order_agreement'], '.2f')}</td>"
                         f"<td>{e(r['folder'].split('/')[-1])}</td></tr>")
        parts.append("</tbody></table></div>")
    parts.append("<h2>Every paper</h2><div class='wrap'><table><thead><tr><th class='k'>ID</th><th class='k'>Pages</th>"
                 "<th class='k'>Confirmed</th><th class='k'>To check</th><th class='k'>Little text</th><th class='k'>OCR</th>"
                 "<th class='k'>Verified by OCR</th><th class='k'>OCR flags</th>"
                 "<th class='k'>Result</th><th>Paper</th></tr></thead><tbody>")
    for r in rows:
        parts.append(f"<tr><td class='k'>{e(r['id'])}</td><td class='n'>{r['pages']}</td><td class='n'>{r['confirmed']}</td>"
                     f"<td class='n'>{len(r['unconfirmed'])}</td><td class='n'>{len(r['too_little_text'])}</td>"
                     f"<td class='n'>{len(r['ocr_pages'])}</td>"
                     f"<td class='n'>{r.get('ocr_verified', 0)}</td><td class='n'>{len(r.get('ocr_flagged', []))}</td>"
                     f"<td class='{'bad' if r['errors'] else 'ok'}'>{'FAIL' if r['errors'] else 'pass'}</td>"
                     f"<td>{e(r['folder'].split('/')[-1])}</td></tr>")
    parts.append("</tbody></table></div></body></html>\n")
    target = free_name(C.ROOT / path if not path.startswith("/") else Path(path))
    PT.write_atomic(target, "".join(parts))
    print(f"report: {target.relative_to(C.ROOT) if C.ROOT in target.parents else target}")


def free_name(path: Path) -> Path:
    """The path itself if it is free, else the next version: NAME-2026-09-28.html, NAME-V2-2026-09-28.html, …
    A report in Docs/ is never overwritten."""
    if not path.exists():
        return path
    m = re.match(r"^(.*?)(?:-V(\d+))?-(\d{4}-\d{2}-\d{2})$", path.stem)
    base, date = (m.group(1), m.group(3)) if m else (path.stem, "")
    n = 2
    while True:
        candidate = path.with_name(f"{base}-V{n}{'-' + date if date else ''}{path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", help="a manifest of the corpus form (default: the corpus manifest)")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--json", default=str(C.OUT / "extraction-audit.json"))
    ap.add_argument("--report", help="also write a printable HTML report to this path (relative to the workspace)")
    args = ap.parse_args()
    papers = C.load_manifest(args.manifest)
    if args.ids:
        wanted = {i.upper() for i in args.ids}
        papers = [p for p in papers if p["id"].upper() in wanted]
    rows = []
    for p in papers:
        try:
            rows.append(audit(p))
        except Exception as exc:  # noqa: BLE001 - an audit that cannot run is a failed audit
            rows.append({"id": p["id"], "folder": p["folder"], "pages": p["pages"], "unconfirmed": [], "confirmed": 0,
                         "possibly_incomplete": [], "too_little_text": [], "ocr_pages": [], "characters": 0,
                         "ocr_verified": 0, "ocr_flagged": [], "sections": None, "sections_numbering_runs_on": None,
                         "errors": [f"the audit could not run: {type(exc).__name__}: {exc}"]})
        if rows[-1]["errors"]:
            print(f"{p['id']}  FAIL  {'; '.join(rows[-1]['errors'][:4])}  — {p['folder']}")
    bad = [r for r in rows if r["errors"]]
    pages = sum(r["pages"] for r in rows)
    differ = sum(1 for r in rows for x in r["errors"] if "not what PyMuPDF gives" in x)
    out = {"date": time.strftime("%Y-%m-%d %H:%M"), "papers": len(rows), "with_problems": len(bad), "pages": pages,
           "pages_identical": sum(r["pages"] for r in rows if not any("PDF is not in" in x or "missing" in x
                                                                      or "could not run" in x for x in r["errors"])) - differ,
           "characters": sum(r["characters"] for r in rows),
           "pages_confirmed": sum(r["confirmed"] for r in rows),
           "pages_unconfirmed": sum(len(r["unconfirmed"]) for r in rows),
           "pages_too_little_text": sum(len(r["too_little_text"]) for r in rows),
           "pages_possibly_incomplete": sum(len(r["possibly_incomplete"]) for r in rows),
           "pages_ocr": sum(len(r["ocr_pages"]) for r in rows),
           "manifest": str(args.manifest or C.MANIFEST),
           "pages_ocr_verified": sum(r["ocr_verified"] for r in rows),
           "pages_ocr_flagged": sum(len(r["ocr_flagged"]) for r in rows),
           "pages_possibly_incomplete_cleared_by_ocr": sum(1 for r in rows for u in r["possibly_incomplete"] if u.get("ocr_clear")),
           "papers_sectioned": sum(1 for r in rows if r["sections"]),
           "papers_sections_numbering_runs_on": sum(1 for r in rows if r["sections_numbering_runs_on"]),
           "rows": rows}
    C.OUT.mkdir(parents=True, exist_ok=True)
    PT.write_atomic(Path(args.json), json.dumps(out, indent=1, ensure_ascii=False))
    if args.report:
        report(out, args.report)
    print(f"{'PASS' if not bad else 'FAIL'}: {out['papers'] - len(bad)} of {out['papers']} papers pass; {pages} pages, "
          f"{out['pages_identical']} extracted again and identical; reading order confirmed on {out['pages_confirmed']}, "
          f"too little text on {out['pages_too_little_text']}, to check by eye {out['pages_unconfirmed']}; "
          f"possibly incomplete {out['pages_possibly_incomplete']} (OCR finds nothing visible missing on "
          f"{out['pages_possibly_incomplete_cleared_by_ocr']}); OCR {out['pages_ocr']}; verified against OCR of the rendered page "
          f"{out['pages_ocr_verified']}, flagged by it {out['pages_ocr_flagged']}; sectioned {out['papers_sectioned']} papers, "
          f"numbering runs on in {out['papers_sections_numbering_runs_on']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
