# Shared primitives: the figure drawing, the Word look, the author checks and the Review Viewer

Imported by the paper scripts (`figures_static.py` draws every SVG figure; `paper_look.py` gives the Word files and the viewer one look; `annotate_author_checks.py` writes the copy with the author checks).

| Script | Purpose | Usage |
|---|---|---|
| `annotate_author_checks.py` | Mark the places in the review that the author must verify, rewrite in their own words, or spot-check. | `scripts/.venv/bin/python scripts/review/annotate_author_checks.py <built.docx> <out.docx> [--dry-run]` |
| `app_screenshot.py` | A screenshot of one of the review's desktop applications on its real data, for the READMEs of the public release (the author, 2 November 2026: "take screenshots of real apps with real data"). | `<the app's python> scripts/review/app_screenshot.py <app.py> <out.png> [--key STUDY] [--delay SECONDS] [-- app arguments]` |
| `build_links_table.py` | Build the table of links between the primary studies and earlier work, from each paper's notes/LINKS.json. | `scripts/.venv/bin/python scripts/review/build_links_table.py [DATE]      (default: today)` |
| `build_pdflinks_html.py` | Build a reading copy of the review as one HTML file in which every reference [n] links to its PDF in the corpus. | `scripts/.venv/bin/python scripts/review/build_pdflinks_html.py <in.docx> <out.html>` |
| `build_v14.py` | Build the V14 review: parse the text source (V14-part*.md), fill numbers, tables and figures from the coded records, resolve Harvard citations, and write document.json; then render it to .docx with render_docx.js. | `scripts/.venv/bin/python scripts/review/build_v14.py <out.docx>` |
| `build_v15.py` | Build the V15 review: parse the text source (_src/V15/V15-part*.md), fill numbers, tables and figures from the synthesis records in _src/V14, resolve numbered (IEEE-style) citations in order of first appearance, and write _src/V15/document.json; then render it to .docx with render_docx.js. | `scripts/.venv/bin/python scripts/review/build_v15.py <out.docx>` |
| `build_v16.py` | Build the V16 review: parse the text source (_src/V16/V16-part*.md), fill numbers, tables and figures from the synthesis records in _src/V14, resolve numbered (IEEE-style) citations in order of first appearance, and write _src/V16/document.json; then render it to .docx with render_docx.js. | `scripts/.venv/bin/python scripts/review/build_v15.py <out.docx>` |
| `build_v17.py` | Build the V17 review: parse the text source (_src/V17/V17-part*.md), fill numbers, tables and figures from the synthesis records in _src/V14, resolve numbered (IEEE-style) citations in order of first appearance, and write _src/V17/document.json; then render it to .docx with render_docx.js. | `scripts/.venv/bin/python scripts/review/build_v15.py <out.docx>` |
| `build_v18.py` | Build the V18 review: the V17 builder (build_v17.py) pointed at the V18 text (_src/V18/V18-part*.md), tables and figures (tables_v18.py, _src/V18/figures). | `scripts/.venv/bin/python scripts/review/build_v18.py <out.docx>` |
| `check_coding.py` | Check the synthesis records (myliteraturereviewpaper/_src/V14/coding/<ID>.json) against the coding guide: keys, types and vocabularies. | `scripts/.venv/bin/python scripts/review/check_coding.py [ID ...]` |
| `check_v16_class.py` | Check the V16 classification records of the closest surveys and of the blockchain-based approaches. | `scripts/.venv/bin/python scripts/review/check_v16_class.py surveys|approaches [ID ...]` |
| `check_v17_class.py` | Check the V16 classification records of the closest surveys and of the blockchain-based approaches. | `scripts/.venv/bin/python scripts/review/check_v17_class.py surveys|approaches [ID ...]` |
| `check_v18.py` | Lint the V18 text parts before they count as drafted (the rules of _src/V18/PLAN.md). | `scripts/.venv/bin/python scripts/review/check_v18.py [NN ...]      (default: every part)` |
| `digest.py` | Write a compact digest of each paper's notes for the synthesis stage of the review. | `scripts/.venv/bin/python scripts/review/digest.py <out_dir>` |
| `fetch_crossref.py` | Fetch the Crossref record of every corpus paper that prints a DOI, for the reference list of the review. | `scripts/.venv/bin/python scripts/review/fetch_crossref.py` |
| `figures_data.py` | Charts of the V14 review computed from the coded records: studies per year and per theme, privacy mechanisms, datasets and open challenges. | `scripts/.venv/bin/python scripts/review/figures_data.py` |
| `figures_static.py` | Diagrams of the review (V14) that do not depend on the coded data: PRISMA flow, storyline, reference architecture, research design. | `scripts/.venv/bin/python scripts/review/figures_static.py` |
| `figures_v15.py` | Figures of the V15 review, written to myliteraturereviewpaper/_src/V15/figures. | `scripts/.venv/bin/python scripts/review/figures_v15.py` |
| `figures_v16.py` | Figures of the V16 review, written to myliteraturereviewpaper/_src/V16/figures. | `scripts/.venv/bin/python scripts/review/figures_v15.py` |
| `figures_v17.py` | Figures of the V17 review, written to myliteraturereviewpaper/_src/V17/figures. | `scripts/.venv/bin/python scripts/review/figures_v17.py` |
| `figures_v18.py` | Figures of the V18 review, written to myliteraturereviewpaper/_src/V18/figures. | `scripts/.venv/bin/python scripts/review/figures_v18.py` |
| `links_packs.py` | Build the input pack for recording a paper's links to earlier work (LINKS-PROTOCOL.md). | `scripts/.venv/bin/python scripts/review/links_packs.py OUT_DIR [ID ...]      (default: every primary study)` |
| `links_review.py` | Citation Links: list the links to review for consistency with the final rules of LINKS-PROTOCOL.md. | `scripts/.venv/bin/python scripts/review/links_review.py [ID ...]` |
| `paper_look.py` | The look of the review: one set of numbers shared by the Review Viewer and every Word document the builds write. | `python3 scripts/review/paper_look.py <paper.md> <out.docx> [<resource dir>]   (renders an assembled text, e.g.` |
| `ref_links.py` | Map the numbered references of a corpus paper to corpus IDs. | `scripts/.venv/bin/python scripts/review/ref_links.py ID [ID ...]      (prints JSON)` |
| `references.py` | Harvard (Cite Them Right style) references and in-text citations for the review (V14). | `scripts/.venv/bin/python scripts/review/references.py   -> writes _src/V14/references.json` |
| `search_check.py` | Sensitivity check of the review's search strings against its included studies. | `scripts/.venv/bin/python scripts/review/search_check.py <screening.json> <out.json>` |
| `search_counts.py` | Run the review's four search strings (Table IV of V15) and record the date and number of hits per source. | `scripts/.venv/bin/python scripts/review/search_counts.py <out.json> [--arxiv-only]` |
| `summary_packs.py` | Assemble one input pack per paper, from which its short note (notes/SUMMARY.md) is written. | `scripts/.venv/bin/python scripts/review/summary_packs.py <out_dir> [ID ...]` |
| `tables_v14.py` | Statistics, tables and figure registry of the V14 review, computed from the coded records (myliteraturereviewpaper/_src/V14/coding/<ID>.json), the corpus records and the reference list. |  |
| `tables_v15.py` | Tables, statistics and figure registry of the V15 review. |  |
| `tables_v16.py` | Tables, statistics and figure registry of the V16 review. |  |
| `tables_v17.py` | Tables, statistics and figure registry of the V17 review. |  |
| `tables_v18.py` | Tables, statistics and figure registry of the V18 review. |  |

Generated by `scripts/paper_ppml/folder_readmes.py` from each script's header; edit the headers, not this file.
