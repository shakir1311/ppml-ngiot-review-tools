#!/usr/bin/env python3
"""File the published version of an included study whose corpus copy is a preprint or an unedited early-access copy, and
make the review rest on it (7 October 2026: the author downloaded O078, Ad Hoc Networks, and n3102, Scientific Reports).

1. The PDF must carry the study's title and DOI (refs.json) on its first two pages and none of the phrases that mark an
   unedited copy (version_notes.MARKERS); otherwise nothing is filed.
2. It is filed as corpus/searchcorpus/_published-versions/<id>/<id>-published/<id>-published.pdf, beside the copy already
   in the corpus (which stays: the eligibility decision and the first notes were made on it), with PROVENANCE.json (the
   source file and its SHA-256, the DOI, the title, how and when), and extracted with extract_paper.py and ocr_scanned.py.
3. search-ppml/evidence/PUBLISHED-VERSIONS.json maps the id to that folder, so that check_sheets.py, the claims audit and the
   review viewer read the published text from then on.
4. The quotations of the extraction record (search-ppml/evidence/sheets/<id>.json) are re-anchored to the published pages
   (reanchor_published.py); a quotation found on no page is listed, to be replaced by the published wording.

Usage: scripts/.venv/bin/python scripts/paper_ppml/file_published.py <id> <path to the published PDF>
"""
import datetime, hashlib, json, pathlib, re, shutil, subprocess, sys, unicodedata

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = ROOT / 'scripts' / '.venv' / 'bin' / 'python'
EV = ROOT / 'search-ppml' / 'evidence'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from version_notes import MARKERS                                    # noqa: E402

sha = lambda f: hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()
norm = lambda s: re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s or '').lower())


def main(cid, pdf):
    pdf = pathlib.Path(pdf)
    ref = json.loads((ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json').read_text(encoding='utf-8'))[cid]
    title = re.search(r'“([^”]+)”', ref['ieee']).group(1).rstrip(',')
    doc = pymupdf.open(pdf)
    first = re.sub(r'\s+', ' ', ''.join(doc[i].get_text() for i in range(min(2, doc.page_count))))
    if norm(title)[:50] not in norm(first):
        sys.exit(f'{cid}: the PDF does not carry the title "{title[:60]}" on its first pages — nothing filed')
    if ref.get('doi') and ref['doi'].lower() not in first.lower():
        sys.exit(f'{cid}: the PDF does not carry the DOI {ref["doi"]} on its first pages — nothing filed')
    if any(re.search(m, first.lower()) for m in MARKERS):
        sys.exit(f'{cid}: the PDF is itself marked as not final — nothing filed')
    dest = ROOT / 'corpus' / 'searchcorpus' / '_published-versions' / cid / f'{cid}-published'
    out = dest / f'{cid}-published.pdf'
    if out.exists():
        sys.exit(f'{cid}: {out.relative_to(ROOT)} exists — nothing changed')
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf, out)
    prov = {'id': cid, 'doi': ref.get('doi'), 'title': title, 'role': 'published version of the copy held in the corpus',
            'source_file': pdf.name, 'source_sha256': sha(pdf), 'file': out.name, 'sha256': sha(out), 'pages': doc.page_count,
            'how': 'downloaded by the author on 7 October 2026; filed by Claude Code (file_published.py)',
            'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
    (dest / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding='utf-8')
    subprocess.run([str(PY), str(ROOT / 'scripts' / 'extract_paper.py'), str(out), '--quiet'], check=True)
    subprocess.run([str(PY), str(ROOT / 'scripts' / 'ocr_scanned.py'), str(dest)], check=False, capture_output=True)
    pv = EV / 'PUBLISHED-VERSIONS.json'
    m = json.loads(pv.read_text(encoding='utf-8'))
    m[cid] = str(dest.relative_to(ROOT))
    pv.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{cid}: filed and extracted ({doc.page_count} pages) -> {dest.relative_to(ROOT)}; registered in {pv.relative_to(ROOT)}')
    subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('reanchor_published.py')), cid], check=False)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
