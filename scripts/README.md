# Extraction mechanism

Turns every paper under `corpus/` into a folder that holds the paper, everything extracted from it, and a set of
page-cited notes that can be checked against the paper. Built for a systematic literature review: the notes of all
papers collect into tables with one row per statement.

Two halves:

| Half | What it does | Who does it |
| --- | --- | --- |
| **Mechanical** | One folder per paper; text in reading order (whole and per page), the same pages as other engines read them, page renders, figures, tables, metadata; OCR where a page has no text layer; every page checked against local OCR of its render; an audit that extracts every page again | `run_extraction.sh` |
| **Reading** | Notes written from the full text, every statement with its page and the authors' words | A reader following `NOTES-PROTOCOL.md`, then `check_notes.py` |

Only standard tools read the PDFs: PyMuPDF, poppler (`pdftotext`), Apple PDFKit, Apple Vision (OCR), Tesseract (OCR)
and pymupdf4llm. The scripts here run them, compare what they return, and keep the evidence. No single converter is
trusted: three text engines read the text layer, two OCR engines read the rendered page, and a page is accepted when
they agree.

## Set up once

```bash
./scripts/setup_env.sh          # creates scripts/.venv (PyMuPDF, pymupdf4llm, pyobjc for PDFKit and Vision)
brew install poppler            # pdftotext
brew install tesseract          # the second OCR engine (verify_ocr.py, ocr_scanned.py)
```

## 1. Mechanical extraction

```bash
./scripts/run_extraction.sh               # papers not yet extracted
./scripts/run_extraction.sh --force       # everything, from scratch: each folder is emptied of earlier output first
./scripts/run_extraction.sh --text-only   # only the text of papers already extracted
./scripts/run_extraction.sh --manifest corpus/ppmlcorpus/check-szk/MANIFEST-S-ZK.json   # another set of papers
./scripts/run_extraction.sh --no-verify   # without the OCR verification (step 4 reads every page by OCR)
```

Runs `prepare_corpus.py` (folders and manifest), `extract_corpus.py` (one process per paper; a paper that fails is
run once more and then listed, the batch never stops), `ocr_scanned.py`, `verify_ocr.py` (every page against local
OCR of its render) and `check_extraction.py` (audit, with a printable report in `Docs/`). What is in scope is every PDF
under `corpus/` except the paths listed in `exclude.txt`. With `--manifest`, the steps run on another manifest of the
same form instead — a set of downloaded reports filed under `corpus/` (for instance by
`search_ppml/file_szk_downloads.py`, which writes such a manifest), without touching the corpus manifest.

Each paper folder then holds:

| Path | What it holds |
| --- | --- |
| `<Paper>.pdf` | The paper |
| `text/full.txt` | Whole paper in reading order; each page starts with `========== [ PAGE n / N ] ==========` |
| `text/pages/page_NNNN.txt` | One text file per page — PyMuPDF `get_text()`, in the order the PDF lays its text down |
| `text/variants/page_NNNN.poppler.txt`, `.pdfkit.txt` | The same page as `pdftotext` and as PDFKit read it |
| `text/pages_ocr/page_NNNN.txt` | OCR text of a page that has no text layer, or whose text layer is only a stamp over a page image |
| `text/variants/page_NNNN.tesseract.txt` | Tesseract's reading of a page read by OCR (the second OCR engine) |
| `text/variants/page_NNNN.graphics-ocr.txt` | Text drawn as graphics in a figure (labels as outlines), read by OCR: not in the text layer |
| `ocr_check.json` | The OCR verification of every page (`verify_ocr.py`) |
| `text/sections.json`, `text/sections.md` | The verified full text broken down into its sections, with the pages each runs over (`sections.py`) |
| `PROVENANCE.json` | For a downloaded report: the file it was filed from, both SHA-256s, the pages taken from a book |
| `text/full_layout.txt`, `text/full.md` | Layout-preserving text (tables keep their columns); Markdown with headings and tables |
| `images/pages/page_NNNN.png` | A render of every page |
| `images/figures/`, `images/embedded/`, `images/crops/` | Cropped figures; embedded images; enlargements made while reading |
| `tables/` | Detected tables as CSV and Markdown |
| `metadata.json`, `README.md` | Extraction metadata — for every page its SHA-1 and the verdict on its reading order — and a summary |
| `notes/NOTES.md`, `notes/check.json` | **The notes** (reading half) and the result of their last check |

`corpus/_extraction/MANIFEST.json` lists every paper with a stable ID (`S###` survey corpus, `N###` new corpus,
`O###` old corpus) and its folder. `corpus/_extraction/EXCLUDED.json` lists papers taken out of the corpus (kept in
`corpus/_excluded/`); their IDs are never given again.

### Reading order, and how it is confirmed

The reading text is what PyMuPDF returns in the content order of the PDF. It is compared, page by page, with three
independent readings: `pdftotext`, PDFKit and `full.md`. The measure is the share of the page's eight-word runs that
also run on in the other reading: text read across two columns scores under 0.5, the same order with a caption or
footnote placed differently scores 0.8 and more. A page is **confirmed** at 0.80 with at least one witness.
A page that no witness confirms — nearly always a table, a figure with many labels or a list — is marked in
`full.txt` and must be read against its render; the notes checker insists that the coverage log names it.

Until 28 September 2026 the page text was sorted by position on the page. That reads a two-column page straight
across, line by line; it broke the text of 1,972 of 3,327 pages. That text, and everything extracted with the old
scripts, was removed on 28 September 2026; nothing of it is kept.

### OCR: pages without text, and every page verified

`ocr_scanned.py` OCRs every page without a text layer with Apple Vision, and — where Tesseract is installed — with
Tesseract as well: where both read the same span with as many words, and Vision's word is not a dictionary word while
Tesseract's similar word is, Tesseract's word is taken; Tesseract's whole reading is kept as a variant of the page. A page
whose text layer holds only a publisher's stamp or running head over a page image is OCR'd too and marked
`ocr_stands_in`: its OCR text then stands in for it in `full.txt`.

`verify_ocr.py` reads **every** page as a reader sees it: the page is rendered (300 dpi) and read by Apple Vision line
by line; lines inside figures (recorded figures, clusters of vector graphics, raster images smaller than most of the
page) are set aside for the first measure. Over the dictionary words of four letters or more it measures the words of
the running text that OCR sees and the reading text lacks (*missing*), the words of the reading text that OCR sees
nowhere on the page (*not visible*), the words inside figures that the text layer does not hold (labels drawn as
outlines, kept with `--apply` as a variant of the page), and the reading order against the OCR lines put in column order. Ligatures, mathematical letters and words
hyphenated at a line end are normalised first, and words whose letters are only spaced apart (small capitals) do not
count as missing. A page is flagged when more than 3 % of what OCR sees is missing (at least 10 words), when more than
10 % of the reading text is not visible (at least 20 words), when it is a page image whose text only OCR can give, or
when the prose of its reading text is not in OCR's order (below); with `--tesseract` a second engine must confirm a
missing or not-visible flag before it stands, and must agree with the OCR text of every page read by OCR. With `--apply`
it OCRs page images so that OCR stands in for them, and lets the reading whose prose is in OCR's order stand in for a
page (below). The record is `ocr_check.json` in the paper's folder; the audit reports it.

Why OCR and not more text engines: PyMuPDF, poppler, PDFKit (and pypdf, pdfminer) all read the same text layer and share
its faults — text hidden or placed outside the page, which the others return and PyMuPDF rightly drops; pages that are
images under a stamp; fonts without Unicode maps. OCR of the rendered page is the only independent view of what a
reader sees. On 12 October 2026 it showed that the text PyMuPDF drops at the page box on seven pages of four papers is
not visible on the page (so PyMuPDF's reading is the right one), and found a paper whose pages are images under a stamp.

### Reading order of the prose, and sections

The goal is the running text, in reading order: tables and figures are not checked against the prose (the author, 12 October
2026). `verify_ocr.py` judges the order of the prose on **every** page, whatever the engines agreed on: OCR's lines of running
prose (a quarter of the page wide or more, six words or more, mostly words of the language) are found in a reading by their
first forty letters, and the share that come in OCR's order is that reading's prose order — tables, captions and footnotes
between them do not count against it. Two independent orders of the page count: Vision's lines in column order, and
Tesseract's own layout analysis (blocks, paragraphs, lines), both measured on every page; a reading's prose
order is the better of the two, because Vision's column order alone misjudges pages whose lines cross the middle (a full-width
figure, table or abstract). Every reading the pipeline holds is judged — the text layer (PyMuPDF's content order), `pdftotext`'s,
PDFKit's and pdfminer's (pdfminer.six, read by `verify_ocr.py` with its own analysis of the layout and kept with `--apply` as
`text/variants/page_NNNN.pdfminer.txt`). The page's order is confirmed when its reading has at least 90 % of at least five prose lines in order. Where it
has less, or another reading is better by at least 0.05, the best reading with at least 95 % that neither lacks visible running
text nor holds text that is not visible stands in for the page (`reading_order_from: poppler`, `pdfkit` or `pdfminer`; of two readings
equally in order, the one also in order by OCR's other order, then the one in which more prose lines are found); a reading
that both orders put in order stands in for one that only one of them does. Where the two orders back different readings and
none satisfies both — a full-width figure or table between the columns, which can be read column by column or above it and
then below it — OCR does not settle the order, and the page is marked `ocr_orders_disagree` and named for a look. A page that
no reading puts in OCR's order is marked
`ocr_order_not_confirmed`: `full.txt` names it and the audit lists it to be read against the page render. A page with fewer
than five prose lines (a table, a figure, a title page) has too little prose for its order to matter.

Three refinements (13 October 2026), the same as in the PDF Text Extractor app, so the two judge pages alike:

- **Lines OCR joins across the gutter.** Vision sometimes reads a line of the left column and the line beside it in the right
  column as one line across the page; the column order took that for a full-width line and cut the page into bands, so a
  reading in the right order scored low. Such a line now stays with its column — decided from the text layer: only where the
  PDF has a line in each column side by side at that height (`side_by_side`, `ocr_scanned.joined_by_layout`). On a page without
  a text layer the neighbours decide (columns running on just above and just below it, `joined_by_neighbours`). A real
  full-width line (a wide equation, a caption) still cuts the page into bands.
- **The text layer re-ordered by the page's layout** (`reordered_page`, kept as `text/variants/page_NNNN.reordered.txt`): the
  text layer's own lines, every character as PyMuPDF holds it, sorted band by band, left column before right. It is a fifth
  reading for pages whose PDF lays the text down out of order. Its column order is the geometry OCR's column order uses too, so
  Tesseract's layout analysis alone judges it: it stands in (`reading_order_from: reordered`) where Tesseract has its prose in
  order (95 % or more) and the page's reading is neither in order by both OCR orders nor confirmed by Tesseract as well.
- **Table pages.** A page whose prose order is not confirmed, with fewer than fifteen prose lines, whose text-layer lines fall
  into three or more columns well apart (each a fifth of the lines or more) and are mostly short is a table, with or without
  rules (a borderless "key resources" table): the order of its cells is not prose, so it is not judged (`table_page`,
  "too little text") — tables are not the goal.
- **Scanned pages read again, sharper.** A page read by OCR whose two engines read its prose differently (under 95 % alike) is
  OCR'd again at 400 dpi; the sharper reading is kept only where the engines agree better, else everything is put back as it was.

Why every page and not only those the engines leave unconfirmed (12 October 2026): the engines' agreement does not show that
an order is right where they share it — a reading built on PyMuPDF's content order agrees with PyMuPDF however that order runs.
Testing a second extractor on the S-ZK papers showed pages that the engines "confirmed" whose prose OCR puts in another order
(a full-width figure or table between the columns), and that on those pages `pdftotext` or PDFKit — which analyse the layout
themselves — have the prose in OCR's order. Neither is always right: each is right on pages where the other is not.

`sections.py` breaks the verified `full.txt` into sections. With the PDF's own outline (bookmarks), every entry is found, in
order, on its page (or, where a reading that stands in for a page runs a heading into a line, where it begins a sentence there); without one, headings are read from the type (bold, larger, capitals or small capitals, italic for
subsections — judged by the share of characters) and the numbering: the best run of top-level numbers (a search that loses three
points for every skipped number, so that bold numbered list items do not become sections), subsections in step within their
section, a skipped number filled by the one line that carries it in the gap, nothing smaller than the body text unless in
capitals (figure labels). In a paper without numbering, lines set exactly like its standard headings ("Introduction",
"Conclusion") are headings too. Every character of `full.txt` is in exactly one section, and each keeps its pages; the audit
checks both.

Since 13 October 2026 (the same rules as the PDF Text Extractor app, `pdf-text-extractor/`, tested on its run over the 163
corpus papers, where the numbering now runs on in every paper): an outline entry is found by the strictest test first (the same
letters, "&" read as "and"), then a line at least 90 % alike, then a short heading run into the start of its line ("Model. The
…"), then run into a line where it begins a sentence, then two pages after the page the outline gives. An outline entry for a
table or figure that cannot be found in order is set aside, not counted as missing, and one whose words the PDF does not print
at all is recorded as not printed. When the outline does not run on, the type and numbering are read too, and the reading that
skips fewer numbers is used (`mode` in `sections.json`). A heading may have its number on a line of its own (letters too), a
title that opens with a number or a letter of any script ("5G …", "Σ-…"), its number run onto a standard heading
("1Introduction"), or its words repeated smaller in a figure on the same page (the line set as a heading counts); a numbered
line that ends with a comma is a heading wrapped over two lines, and is used only to fill the gap between its neighbours. The
earlier version is `history/sections-v8.py`.

### What the audit proves

`check_extraction.py` opens every PDF again and tests that: the PDF is the file registered in the manifest; every
page has its text, render and variants; **the text on disk is exactly what PyMuPDF gives for the page**; `full.txt`
holds every page in order; every page without a text layer has OCR text; nothing is left half-written; **the folder
holds nothing of unknown origin** — every file is one this mechanism writes, and the figures, images and tables on
disk are exactly those recorded in `metadata.json`. It lists the pages whose reading order is unconfirmed and the
pages where the reading text may lack text that both other engines hold — with, where `ocr_check.json` is present,
whether OCR sees any of it on the page — and the pages that the OCR verification flags. `--manifest PATH` audits another
manifest of the same form.

### Two traps this mechanism avoids

- **onnxruntime.** pymupdf4llm loads it, and its telemetry thread can abort a process as it exits (crash of
  28 Sep 2026). Only `markdown_pdf.py` loads pymupdf4llm, in a process of its own, with telemetry switched off, and it
  leaves without the exit-time teardown. Never import pymupdf4llm anywhere else.
- **Newline translation.** Maths fonts put carriage returns and other control characters into page text. Files are
  read and written byte for byte (`page_text.read_exact`, `write_atomic`); Python's default `read_text` changes them.

## 2. Reading: the notes

`NOTES-PROTOCOL.md` is the instruction the reader follows. In short: read the whole paper once, in reading order;
write `notes/NOTES.md` in the fixed template; every statement carries its PDF page as `[p7]`, followed by the
authors' exact words in quotation marks; nothing is scored against, or written towards, any research question.

The template (template 2) covers: what the paper is about · the issue it addresses · the authors' own aims,
questions and contributions · method · a section-by-section digest · ten topic facets (setting, learning, privacy
mechanisms, trust and ledger, threats, defences, cost, evaluation evidence, regulation, other topics) · results ·
**limitations** · **future directions** · **open issues** · inventory of figures and tables · definitions ·
positioning · **theme** · rigour and reporting (facts for the quality appraisal) · reader's observations ·
coverage log.

Helpers for the reader: `try_quotes.py` (are these words on that page; on which page are they; where is a passage
interrupted) and `crop_page.py` (part of a page, larger).

Every paper is read in the same way and to the same depth. `READER-TASK.md` is the task as a reader receives it;
`reading_queue.py` hands the papers out one by one and records in `corpus/_extraction/reading-log.json` which paper
was handed out when and whether its notes pass:

```bash
scripts/.venv/bin/python scripts/reading_queue.py next 12     # the next twelve papers to hand to readers
scripts/.venv/bin/python scripts/reading_queue.py status      # read, being read, waiting
```

## 3. Checking the notes

```bash
scripts/.venv/bin/python scripts/check_notes.py S007          # a paper ID or a paper folder
scripts/.venv/bin/python scripts/check_notes.py --all
```

A quotation passes only when its words run on, in order and without a gap, in the text of the one page cited before
it — as any of the engines read that page. Case, punctuation, spacing and hyphenation are ignored; the words are
not. Reference numbers that the paper sets against a word may be left out of a quotation; a number that belongs to
the sentence may not. The check also fails on a statement without a page, a section that must quote and does not, a body page never
cited, a figure or table missing from the inventory, a missing section, facet or rigour item, and a header that
departs from the agreed vocabulary.

## 4. Collecting the notes for the review

```bash
scripts/.venv/bin/python scripts/build_matrix.py
```

Writes to `corpus/_extraction/`:

| File | Rows |
| --- | --- |
| `papers.csv` | One per paper: record, publication, document and research type, evaluation type, theme, codes, counts, check result |
| `statements.csv` | One per statement: paper, section, facet, statement, pages, quotations — filter by section to pull, say, every stated limitation in the corpus with its page |
| `rigour.csv` | One per paper and item of the rigour section — the basis of the quality appraisal |
| `themes.csv` | One per paper and theme or code — the starting point for the codebook |
| `progress.md` | Which papers have notes and which pass |

## 5. Citation Links: what each study says about earlier work

A citation context analysis of the primary studies of the review. For every primary study, the links it states to
earlier work are recorded from its own words: whom it builds on, whom it measures itself against (in the same
setting) and with what result, whom it compares itself with without measuring, whom it criticises, and from whom it
sets itself apart. Every link quotes the study's text with its page; values are not read from tables or figures, and
the statements are not checked against the studies' data. The records let the review trace lines of work and tell
which gains can be stated and which results can only be set side by side.

The rules are `LINKS-PROTOCOL.md`; the brief an agent receives is `LINKS-TASK.md`. The work runs in small batches and
resumes where it stopped: a study is done only when its `notes/LINKS.json` passes the check.

```bash
scripts/.venv/bin/python scripts/links_queue.py status          # done, handed out, waiting
scripts/.venv/bin/python scripts/links_queue.py next 5          # hand out a batch; builds its packs
#   give LINKS-TASK.md, with the five IDs filled in, to one agent; wait for it to finish
scripts/.venv/bin/python scripts/links_queue.py done            # record which of the batch now pass
scripts/.venv/bin/python scripts/links_queue.py release ID ...  # a batch that stopped: put its open studies back
scripts/.venv/bin/python scripts/check_links.py --all           # at the end: every study
scripts/.venv/bin/python scripts/review/links_review.py         # links resting on hedged group wording, to review
#   each reviewed link: kept, retyped or removed, one line in corpus/_extraction/links-review-decisions.md
scripts/.venv/bin/python scripts/review/build_links_table.py    # Docs/LINKS-TABLE-<date>.html and .csv
```

Completed on 29 September 2026: all 73 studies pass, 364 links; the consistency review kept 45 of 50 flagged links
and removed 5. The table is `Docs/LINKS-TABLE-2026-09-29.html` (and `.csv`); the activity note is
`Docs/CITATION-LINKS-2026-09-29-V2.html`.

`review/ref_links.py` finds the corpus papers in a study's reference list (numbered "[12]" or "12." lists, and
author-year lists by title); `review/links_packs.py` builds the input pack per study in
`corpus/_extraction/links-packs/`; the record of the batches is `corpus/_extraction/links-log.json`.

## Files

| Script | Purpose |
| --- | --- |
| `run_extraction.sh` | Runs the mechanical half end to end |
| `prepare_corpus.py` | One folder per paper; manifest with stable IDs |
| `extract_corpus.py` | Runs `extract_paper.py` on every paper, each in its own process, with one retry |
| `extract_paper.py` | Extracts one PDF |
| `page_text.py` | The engines that read a page, the comparison of their readings, exact file reading and writing |
| `markdown_pdf.py` | `text/full.md` by pymupdf4llm, in a process of its own |
| `ocr_scanned.py` | OCR (Apple Vision, with Tesseract as a second engine) for pages without a text layer or named pages |
| `verify_ocr.py` | Every page against local OCR of its render: missing or invisible text, page images, reading order of the prose |
| `sections.py` | The verified full text broken down into sections (outline, or type and numbering); lossless |
| `check_extraction.py` | Audit of the mechanical extraction, the OCR verification included; printable report |
| `NOTES-PROTOCOL.md` | The reading protocol and the notes template |
| `READER-TASK.md` | The task as a reader receives it |
| `reading_queue.py` | Hands the papers out to readers and keeps the record of the reading |
| `notes_format.py` | Parser for the notes format; the agreed vocabulary |
| `check_notes.py` | Checks notes against the paper |
| `try_quotes.py`, `crop_page.py` | Helpers for the reader |
| `build_matrix.py` | Collects all notes into tables |
| `LINKS-PROTOCOL.md` | Citation Links: the rules for recording what a study says about earlier work |
| `LINKS-TASK.md` | Citation Links: the brief for one batch, as an agent receives it |
| `links_queue.py` | Citation Links: hands out batches, records which studies pass, resumes after an interruption |
| `check_links.py` | Citation Links: checks a study's `notes/LINKS.json` (pages, quotations, types, every corpus reference accounted for) |
| `review/ref_links.py` | Citation Links: the corpus papers in a study's reference list |
| `review/links_packs.py` | Citation Links: the input pack per study |
| `review/links_review.py` | Citation Links: lists links resting on hedged or unnamed-group wording, for the final consistency review |
| `review/build_links_table.py` | Citation Links: the printable table in `Docs/` and its CSV |
| `corpus.py` | Shared helpers: scope, folders, manifest, page text |
| `exclude.txt` | Paths left out of scope |
| `setup_env.sh` | Creates the Python environment |

Earlier scripts were removed on 28 September 2026.

## Evidence sheets of the PPML review (15 October 2026 onwards)

| Script | What it does |
|---|---|
| `scripts/paper_ppml/reframe_sheets.py` | Reframed the sheets for the three review questions of 15 October 2026 (`search-ppml/evidence/EXTRACTION-GUIDE-V2-2026-10-15.md`): added P1b, P3b and P6b to every design sheet from its page-cited notes and extracted pages; removed the tags and survey answers that no longer belong; originals in `notes-verifier/history/<id>/`; log `search-ppml/evidence/REFRAME-2026-10-15.jsonl`. `--dry-run` prints counts only. Run once; running again changes nothing. |
| `scripts/paper_ppml/check_sheets.py` | Checks every sheet against the V2 form: answers present, tags allowed, every quotation on its page; reports answers or tags no longer in the form. |
| `scripts/paper_ppml/apply_reframe_fixes.py` | Puts readers' findings (`search-ppml/evidence/reframe-fix/results/`) into the sheets after checking values and quotations; history kept; log `APPLIED.jsonl`. |
| `scripts/paper_ppml/install_summaries.py` | Installs re-cut short notes (`search-ppml/evidence/summaries-recut/out/`) as `notes/SUMMARY.md` after `check_summary.py` (protocol V2) and a check that every cited page is one the notes cite; history kept; log `INSTALLED.jsonl`. |
| `scripts/paper_ppml/summary_statements.py` | One statement per sentence of the re-cut notes for the local fact checker (`local-checker/run.sh`). |
| `scripts/SUMMARY-PROTOCOL-V2.md` | The short-note protocol of 15 October 2026: one template keyed to the three review questions, 150–220 words, page-cited, the writing rules; `check_summary.py` checks either protocol. |
| `scripts/paper_ppml/simplify_sheets.py` | Merged the sheets to one answer per review question (`EXTRACTION-GUIDE-V3-2026-10-15.md`: designs P1, P2, P3; surveys S1), remapping the Sheet Reviewer's record; history kept; log `SIMPLIFY-2026-10-15.jsonl`. `reframe_sheets.py` and `apply_reframe_fixes.py` are the earlier steps of the same day and are not run again. |

## The scripts of this folder

| Script | Purpose | Usage |
|---|---|---|
| `build_matrix.py` | Collect the notes of every paper into tables for the systematic review. |  |
| `check_extraction.py` | Audit of the mechanical extraction: every page of every paper is checked again, from the PDF itself. |  |
| `check_links.py` | Check the links a paper's notes record to earlier work (notes/LINKS.json), against LINKS-PROTOCOL.md. | `scripts/.venv/bin/python scripts/check_links.py ID [ID ...] | --all` |
| `check_notes.py` | Check one paper's notes against the paper itself. |  |
| `check_notes_simple.py` | Check the simple notes of one paper (scripts/NOTES-SIMPLE-PROTOCOL.md) against the paper itself. |  |
| `check_summary.py` | Check the short note of each paper (notes/SUMMARY.md) against scripts/SUMMARY-PROTOCOL.md, or against scripts/SUMMARY-PROTOCOL-V2.md (15 October 2026) when the note carries the V2 labels (Fabric and cost … / What it treats …). | `scripts/.venv/bin/python scripts/check_summary.py [ID ...]    (no IDs: every paper in the manifest)` |
| `corpus.py` | Shared helpers for the extraction mechanism: where the corpus is, which PDFs are in scope, which folder belongs to a paper, and the manifest that gives every paper a stable ID. |  |
| `crop_page.py` | Render part of a page at a higher resolution, to read a table, a figure or an equation closely. |  |
| `extract_corpus.py` | Run extract_paper.py on every paper in the manifest, or on the papers named, several at a time. |  |
| `extract_paper.py` | Extract one PDF into a self-contained, fully analysable folder. | `extract_paper.py <file.pdf> [--outdir DIR] [--dpi N] [--force] [--text-only] [--quiet]` |
| `fetch_policy_pages.py` | Save online policy pages into the workspace as evidence: raw HTML, a pandoc text copy, and a manifest line. |  |
| `html_to_docx.py` | Convert one of the Docs/ guideline pages (HTML) into a Word document with working links. | `scripts/.venv/bin/python scripts/html_to_docx.py <in.html> <out.docx>` |
| `links_queue.py` | Keeps track of which primary studies have had their links to earlier work recorded (LINKS-PROTOCOL.md), so that the work can run in small batches and resume after an interruption. |  |
| `markdown_pdf.py` | Markdown rendering of a PDF (headings, lists, tables) with pymupdf4llm and its layout engine. |  |
| `notes_format.py` | Parser for notes/NOTES.md as defined in NOTES-PROTOCOL.md: header, sections, statements, page citations, quotations. |  |
| `ocr_scanned.py` | OCR the pages of an extraction that carry no text layer. |  |
| `organise_papers.py` | Keep the two review papers in two folders of myliteraturereviewpaper/ (the author's request of 4 October 2026). | `python3 scripts/organise_papers.py` |
| `page_text.py` | The text of every page, taken from standard tools, and the evidence that its reading order is right. |  |
| `prepare_corpus.py` | Step 1 of the extraction: give every in-scope PDF a folder of its own and write the manifest. |  |
| `reading_queue.py` | Keeps track of which papers have been handed to a reader, so that every paper is read once and none is left out. |  |
| `run_extraction.sh` | The mechanical half of the extraction, for the whole corpus or for another manifest of the same form: 1. |  |
| `sections.py` | Break the verified full text of a paper into its sections — a step of the extraction pipeline (run_extraction.sh, after verify_ocr.py and before check_extraction.py). |  |
| `setup_env.sh` | Create the local Python environment used by the extraction scripts. |  |
| `try_quotes.py` | Try quotations against a paper's page text before they go into the notes — with the checker's own matching. |  |
| `verify_ocr.py` | Verify the reading text of every page against local OCR of the rendered page — what a reader sees on it. |  |
| `verify_policy_quotes.py` | Check every quotation in a policy document against the saved copy of its source. |  |

Generated by `scripts/paper_ppml/folder_readmes.py` from each script's header; edit the headers, not this file.
