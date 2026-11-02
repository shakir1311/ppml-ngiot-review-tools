"""Self-test on generated PDFs whose text is known: two columns in column order, columns laid down the wrong way round in the PDF
(another reading must stand in), sections, the harder heading rules (a letter on a line of its own, a heading's words repeated in
a figure, a heading wrapped after a comma), an outline, a scanned page read by OCR, a table and a figure saved as images, folder
handling, and the window opened (off screen).

    python -m pdftextextractor.selftest [--quick] [--keep DIR]
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

from . import ocr as O
from . import pipeline as P

SENT = [
    "Federated learning keeps the raw data on each device while a server combines the model updates of many participants.",
    "Privacy protection matters because the updates themselves can reveal sensitive information about the training records.",
    "A ledger records every round so that the participants can audit the process without trusting a single operator.",
    "Poisoning attacks change the training data or the updates so that the global model behaves badly on chosen inputs.",
    "Secure aggregation hides each update from the server while still allowing the sum of all updates to be computed.",
    "The evaluation measures accuracy, communication cost and the time each device needs to finish one training round.",
    "Results show that the proposed design keeps accuracy close to the plain baseline while protecting every update.",
    "Future work will test the design on real devices connected over wireless networks with limited bandwidth.",
]


ORDINAL = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"]
WORDS = sorted({w for s in SENT for w in re.findall(r"[a-z]{4,}", s.lower())})


def paragraph(k: int, n: int = 4) -> str:
    """A paragraph that begins with words of its own (so that its place in the text can be found) and goes on with sentences in
    which every word after the first few is drawn at random (seeded): like a paper, no line repeats another."""
    import random
    rnd = random.Random(1000 + k * n)
    out = [f"This {ORDINAL[k % 12]} paragraph opens the passage."]
    for j in range(n):
        head = SENT[(k + j) % len(SENT)].split()[:3]
        out.append(" ".join(head + [rnd.choice(WORDS) for _ in range(14)]) + ".")
    return " ".join(out)


def two_column(path: Path) -> list[str]:
    """A two-column paper with Roman sections and lettered subsections; -> the paragraphs in reading order."""
    import pymupdf
    doc = pymupdf.open()
    order, k = [], 0
    blocks = [("title", "Privacy and Checking in Federated Learning"), ("abstract", "Abstract: " + paragraph(11, 2)),
              ("h1", "I. INTRODUCTION"), ("p", None), ("p", None), ("h1", "II. METHOD"), ("h2", "A. Data Sources"), ("p", None),
              ("h2", "B. Model Design"), ("p", None), ("p", None), ("h1", "III. RESULTS"), ("p", None), ("p", None),
              ("h1", "IV. CONCLUSION"), ("p", None), ("h1", "REFERENCES"), ("ref", "[1] A. Author, A study of learning, 2024.")]
    page = doc.new_page(width=612, height=792)
    page.insert_textbox(pymupdf.Rect(50, 40, 562, 80), blocks[0][1], fontname="tibo", fontsize=18, align=1)
    cols = [pymupdf.Rect(50, 90, 296, 740), pymupdf.Rect(316, 90, 562, 740)]
    col, y = 0, 90
    for kind, text in blocks[1:]:
        if kind == "p":
            text = paragraph(k)
            k += 1
            order.append(text)
        if kind == "abstract":
            order.append(text)
        font, size = {"h1": ("tiro", 10), "h2": ("tiit", 10), "ref": ("tiro", 8)}.get(kind, ("tiro", 10))
        if kind == "h1":
            text = text.upper()
        while True:
            if y < cols[col].y1 - 14:
                r = pymupdf.Rect(cols[col].x0, y, cols[col].x1, cols[col].y1)
                need = page.insert_textbox(r, text, fontname=font, fontsize=size, align=1 if kind == "h1" else 3)
                if need >= 0:
                    y += r.height - need + 8
                    break
            col += 1                                       # it did not fit (nothing was written): the next column
            if col == 2:
                page = doc.new_page(width=612, height=792)
                col = 0
            y = cols[col].y0 if page.number == 0 else 50
            if page.number > 0:
                cols = [pymupdf.Rect(50, 50, 296, 740), pymupdf.Rect(316, 50, 562, 740)]
    doc.save(path)
    return order


def reversed_columns(path: Path) -> list[str]:
    """A two-column page whose PDF lays the right column down before the left one, as some publishers' files do on some pages:
    the text in the PDF's own order reads the columns the wrong way round. -> the paragraphs in reading order."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    left, right = [paragraph(k) for k in range(3)], [paragraph(k) for k in range(3, 6)]
    for (x0, x1), paras in (((316, 562), right), ((50, 296), left)):     # the right column first
        y = 60
        for text in paras:
            r = pymupdf.Rect(x0, y, x1, 740)
            need = page.insert_textbox(r, text, fontname="tiro", fontsize=10, align=3)
            y += r.height - need + 10
    doc.save(path)
    return left + right


def with_outline(path: Path) -> None:
    import pymupdf
    doc = pymupdf.open()
    heads = [("1 Introduction", 1), ("2 Related Work", 1), ("2.1 Privacy", 2), ("2.2 Verification", 2), ("3 Conclusion", 1)]
    toc, y, page = [], 60, doc.new_page()
    for i, (h, lvl) in enumerate(heads):
        if y > 650:
            page, y = doc.new_page(), 60
        page.insert_text((72, y), h, fontname="hebo", fontsize=13 if lvl == 1 else 11)
        toc.append([lvl, h, page.number + 1])
        y += 20
        need = page.insert_textbox(pymupdf.Rect(72, y, 540, y + 200), paragraph(i, 3), fontname="tiro", fontsize=10)
        y += 200 - need + 16
    doc.set_toc(toc)
    doc.save(path)


def scanned(path: Path) -> str:
    """A page that is only an image of text; -> the text."""
    import pymupdf
    src = pymupdf.open()
    page = src.new_page()
    text = paragraph(3, 6)
    page.insert_textbox(pymupdf.Rect(72, 72, 540, 700), text, fontname="tiro", fontsize=12)
    pix = page.get_pixmap(dpi=200)
    doc = pymupdf.open()
    p2 = doc.new_page()
    p2.insert_image(p2.rect, pixmap=pix)
    doc.save(path)
    return text


def table_figure(path: Path) -> None:
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(72, 50, 540, 120), paragraph(5, 2), fontname="tiro", fontsize=10)
    x0, y0, w, h = 100, 160, 130, 24
    for r in range(4):
        for c in range(3):
            rect = pymupdf.Rect(x0 + c * w, y0 + r * h, x0 + (c + 1) * w, y0 + (r + 1) * h)
            page.draw_rect(rect, color=(0, 0, 0), width=0.8)
            page.insert_text((rect.x0 + 6, rect.y0 + 16), ["Method", "Accuracy", "Cost"][c] if r == 0 else f"{(r * 7 + c * 3) % 50}.{r}",
                             fontname="tiro", fontsize=10)
    page.insert_text((100, y0 + 4 * h + 16), "Table 1. Accuracy and cost of the methods.", fontname="tiro", fontsize=9)
    shape = page.new_shape()
    for i in range(6):
        shape.draw_circle((180 + i * 50, 420), 18)
        if i:
            shape.draw_line((180 + (i - 1) * 50 + 18, 420), (180 + i * 50 - 18, 420))
    shape.finish(color=(0.1, 0.3, 0.7), width=1.5)
    shape.draw_rect(pymupdf.Rect(140, 380, 470, 470))
    shape.finish(color=(0, 0, 0), width=0.6)
    shape.commit()
    page.insert_text((140, 488), "Fig. 1. The participants and the ledger.", fontname="tiro", fontsize=9)
    page.insert_textbox(pymupdf.Rect(72, 510, 540, 700), paragraph(6, 3), fontname="tiro", fontsize=10)
    doc.save(path)


def headings(path: Path) -> None:
    """A page whose headings test the harder rules: a letter set on a line of its own, a heading's words repeated smaller in a
    figure above it, and a heading wrapped after a comma (which only fills the gap between its neighbours)."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    y = 72

    def put(text: str, font: str = "tiro", size: float = 10) -> None:
        nonlocal y
        page.insert_text((72, y), text, fontname=font, fontsize=size)
        y += size + 6
    body = iter(f"the {ORDINAL[k]} line of the text goes on about the ledger and the rounds of training." for k in range(12))
    put("I. INTRODUCTION", "tibo"); put(next(body)); put(next(body))
    put("A.", "tiit"); put("Threat Model", "tiit"); put(next(body))
    put("B. Trust Model", "tiit"); put(next(body))
    put("II. DESIGN", "tibo"); put("Key Rounds", size=6)         # a label in a figure with the words of the next heading
    put("A.", "tiit"); put("Key Rounds", "tiit"); put(next(body))
    put("B. Keys, Ledgers,", "tiit"); put("and Proofs", "tiit"); put(next(body))
    put("C. Links", "tiit"); put(next(body))
    put("D. Costs", "tiit"); put(next(body))
    put("III. CONCLUSION", "tibo"); put(next(body))
    doc.save(path)


def run(quick: bool, keep: str | None) -> int:
    results, ok = [], True

    def check(name, cond):
        nonlocal ok
        results.append((name, bool(cond)))
        ok &= bool(cond)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(keep) if keep else Path(tmp)
        inp, out = base / "in", base / "out"
        inp.mkdir(parents=True, exist_ok=True)
        order = two_column(inp / "two_column.pdf")
        reversed_order = reversed_columns(inp / "reversed_columns.pdf")
        with_outline(inp / "outline.pdf")
        scan_text = scanned(inp / "scanned.pdf")
        table_figure(inp / "table_figure.pdf")
        # rules that need no OCR: lines OCR joined across the gutter, and titles
        L = O.Line
        left = [L(f"left {k}", 0.06, y, 0.48, y + 0.012, 1) for k, y in enumerate((0.30, 0.32, 0.36, 0.38))]
        right = [L(f"right {k}", 0.52, y, 0.94, y + 0.012, 1) for k, y in enumerate((0.30, 0.32, 0.36, 0.38))]
        across = L("across", 0.06, 0.34, 0.94, 0.352, 1)
        joined = O.column_order(left + right + [across], O.joined_by_layout([(0.335, 0.355)]))
        real = O.column_order(left + right + [across], O.joined_by_layout([]))
        check("a line OCR joined across the gutter stays in its column; a full-width line cuts the page into bands",
              [l.text for l in joined][:5] == ["left 0", "left 1", "across", "left 2", "left 3"]
              and [l.text for l in real][:5] == ["left 0", "left 1", "right 0", "right 1", "across"])
        from . import title as TI
        check("titles: a wrongly mapped glyph, run-together words and an author line are not titles; a title with commas is",
              TI.suspicious("Membership Inference A¢acks on Machine Learning")
              and TI.suspicious("InternetofThreats Asurveyofpracticalsecurityvulnerabilities")
              and TI.suspicious("Priya Rachakonda, Madhuri Siddula∗, Vanlin Sathya")
              and not TI.suspicious("Security, Privacy, and Trust in Edge Computing")
              and TI.from_file_name("O037 - [17] Carlini_2022_Membership_Inference") == "Carlini 2022 Membership Inference")
        from . import sections as SE
        import pymupdf
        headings(base / "headings.pdf")                    # kept out of the input folder: a page for the section rules alone
        hd = pymupdf.open(base / "headings.pdf")
        hs = SE.sections_of(hd, [p.get_text() for p in hd])
        check(f"headings: a letter on a line of its own, words repeated in a figure, a heading wrapped after a comma "
              f"({[s['number'] for s in hs['sections'] if s['number']]})",
              [s["number"] for s in hs["sections"] if s["number"]] == ["I", "A", "B", "II", "A", "B", "C", "D", "III"]
              and hs["numbering_runs_on"] and hs["lossless"])
        check("headings: a title opening with 5G or a Greek letter, a number run onto 'Introduction'; '5G …' alone is no heading",
              SE.parse("3.1 5G Networks")[:2] == ("arabic", "3.1") and SE.parse("3.2 Σ-Protocols")[:2] == ("arabic", "3.2")
              and SE.parse("1Introduction")[:2] == ("arabic", "1") and SE.parse("5G Networks") is None)
        engines = [e.name for e in O.engines()]
        check(f"an OCR engine is available ({', '.join(engines) or 'none'})", engines)
        (out / "outline").mkdir(parents=True, exist_ok=True)              # a folder the app did not make, with the paper's name
        (out / "outline" / "my notes.txt").write_text("kept", encoding="utf-8")
        for pdf in P.pdfs_in(inp):
            P.process_pdf(pdf, out, use_ocr=True)
        P.process_pdf(inp / "scanned.pdf", out, use_ocr=True)              # extracted again: replaces its own earlier folder
        check("output: a folder the app did not make is left alone (the paper goes to 'outline (2)')",
              (out / "outline" / "my notes.txt").exists() and (out / "outline (2)" / "report.json").exists())
        check("output: extracting a paper again replaces its own earlier folder",
              (out / "scanned" / "report.json").exists() and not (out / "scanned (2)").exists())
        P.write_index(out)

        def F(name: str) -> Path:                                  # the folder of the paper extracted from that file
            return next(r.parent for r in out.glob("*/report.json") if json.loads(r.read_text(encoding="utf-8"))["file"] == name)
        two = F("two_column.pdf")
        check(f"folders are named by the paper's title ('{two.name}'), its PDF copy too",
              two.name == "Privacy and Checking in Federated Learning" and (two / f"{two.name}.pdf").exists()
              and json.loads((two / "report.json").read_text(encoding="utf-8"))["title_from"] == "first page")
        tc = (two / "full_text.txt").read_text(encoding="utf-8")
        flat = re.sub(r"\s+", " ", re.sub(r"-\n", "", tc))
        pos = [flat.find(p[:60]) for p in order]
        check("two columns: every paragraph found", all(p >= 0 for p in pos))
        check("two columns: paragraphs in reading order (column by column)", pos == sorted(pos))
        sec = json.loads((two / "sections.json").read_text(encoding="utf-8"))
        nums = [s["number"] for s in sec["sections"] if s["number"]]
        check(f"sections: I, II, A, B, III, IV found ({nums})", nums[:6] == ["I", "II", "A", "B", "III", "IV"])
        check("sections: lossless and numbering runs on", sec["lossless"] and sec["numbering_runs_on"])
        rep = json.loads((two / "report.json").read_text(encoding="utf-8"))
        check(f"two columns: confidence high ({rep['confidence']:.1%})", rep["confidence"] >= 0.95)
        rv = json.loads((F("reversed_columns.pdf") / "report.json").read_text(encoding="utf-8"))
        flat_r = re.sub(r"\s+", " ", re.sub(r"-\n", "", (F("reversed_columns.pdf") / "full_text.txt").read_text(encoding="utf-8")))
        pos_r = [flat_r.find(p[:60]) for p in reversed_order]
        check(f"columns laid down the wrong way round: another reading stands in ({rv['page_results'][0]['source']})",
              rv["page_results"][0]["source"] != "text layer")
        check("columns laid down the wrong way round: paragraphs in reading order", all(p >= 0 for p in pos_r) and pos_r == sorted(pos_r))
        sec2 = json.loads((F("outline.pdf") / "sections.json").read_text(encoding="utf-8"))
        check("outline: sections from the PDF's outline", sec2["mode"] == "outline" and sec2["numbering_runs_on"])
        scan = json.loads((F("scanned.pdf") / "report.json").read_text(encoding="utf-8"))
        got = (F("scanned.pdf") / "full_text.txt").read_text(encoding="utf-8").lower()
        want = re.findall(r"[a-z]{4,}", scan_text.lower())
        share = sum(1 for w in want if w in got) / len(want)
        check(f"scanned page: read by OCR ({scan['page_results'][0]['source']})", scan["page_results"][0]["source"].startswith("OCR"))
        check(f"scanned page: {share:.0%} of its words recovered", share >= 0.95)
        tf = json.loads((F("table_figure.pdf") / "report.json").read_text(encoding="utf-8"))
        check(f"table saved as an image ({len(tf['tables'])})", tf["tables"] and (F("table_figure.pdf") / tf["tables"][0]["file"]).exists())
        check(f"figure saved as an image ({len(tf['figures'])})", tf["figures"] and (F("table_figure.pdf") / tf["figures"][0]["file"]).exists())
        check("a paper already extracted (the same file) is recognised, to be skipped", P.finished_folder(inp / "two_column.pdf", out) == two)
        from . import parallel as PAR                       # two papers at once, each in a process of its own
        events = []
        PAR.run([inp / "two_column.pdf", inp / "reversed_columns.pdf"], base / "out-parallel", True, 2,
                lambda kind, name, payload: events.append((kind, name)), lambda: False)
        par = next(r.parent for r in (base / "out-parallel").glob("*/report.json")
                   if json.loads(r.read_text(encoding="utf-8"))["file"] == "two_column.pdf")
        check(f"two papers at once, in processes of their own ({sum(k == 'done' for k, _ in events)} done)",
              sum(k == "done" for k, _ in events) == 2
              and (par / "full_text.txt").read_text(encoding="utf-8") == (two / "full_text.txt").read_text(encoding="utf-8"))
        check("index of papers written", len(json.loads((out / "index.json").read_text(encoding="utf-8"))) == 5)
        if not quick or os.environ.get("PTE_GUI_TEST"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            from PySide6.QtWidgets import QApplication
            from .gui import Window
            app = QApplication.instance() or QApplication([])
            w = Window()
            w.out.setText(str(out))
            w.load_papers()
            w.papers.setCurrentRow(0)
            w.show_page(0)
            check("window: a paper opens with its page, text and sections", w.paper is not None and w.page_text.toPlainText()
                  and w.sec_tree.topLevelItemCount() > 0)
            w.close()
            del app
    for name, good in results:
        print(("ok   " if good else "FAIL ") + name)
    print(f"self-test: {sum(g for _, g in results)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    sys.exit(run("--quick" in sys.argv, keep))
