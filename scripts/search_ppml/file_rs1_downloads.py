#!/usr/bin/env python3
"""File the full texts of the R-S1 candidates (supplementary regulation search; groups A, B and C pre-screened INCLUDE or UNSURE)
that the author downloaded on 8 October 2026, and extract each with the corpus pipeline.

Only the PDFs named in the mapping file are opened (matched beforehand by file name; the Downloads folder also holds private
documents). Each must carry the record's title on its first two pages; the DOI is checked where the PDF prints it, and the
phrases that mark an unedited copy (version_notes.MARKERS) are recorded. A match is copied to
corpus/ppmlcorpus/check-rs1/<RS1-id>/<RS1-id>.pdf with PROVENANCE.json (source file and SHA-256, filed file and SHA-256, pages,
version), then scripts/extract_paper.py and scripts/ocr_scanned.py run on the folder. Nothing in Downloads is moved or deleted.

Usage: scripts/.venv/bin/python scripts/search_ppml/file_rs1_downloads.py <mapping.json>     ({"RS1-043": "<file name>", …})
"""
import datetime, hashlib, json, pathlib, re, shutil, subprocess, sys, unicodedata

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'paper_ppml'))
from version_notes import MARKERS                                    # noqa: E402

DL = pathlib.Path('/Volumes/Stuff/Downloads')
DEST = ROOT / 'corpus' / 'ppmlcorpus' / 'check-rs1'
SCR = ROOT / 'search-ppml' / 'evidence' / 'regulation-search' / 'screening'
PY = ROOT / 'scripts' / '.venv' / 'bin' / 'python'
norm = lambda s: re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s or '').lower())
sha = lambda f: hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()


def records():
    out = {}
    for f in (SCR / 'input.jsonl', SCR / 'B' / 'input.jsonl', SCR / 'D' / 'input.jsonl'):
        for l in f.read_text(encoding='utf-8').splitlines():
            if l.strip():
                r = json.loads(l)
                out[r['n']] = r
    return out


def main(mapping):
    recs = records()
    m = json.loads(pathlib.Path(mapping).read_text(encoding='utf-8'))
    DEST.mkdir(parents=True, exist_ok=True)
    for rid, name in sorted(m.items()):
        r, src = recs[rid], DL / name
        doc = pymupdf.open(src)
        first = re.sub(r'\s+', ' ', ''.join(doc[i].get_text() for i in range(min(2, doc.page_count))))
        if norm(r['title'])[:50] not in norm(first):
            print(f'{rid}: the PDF does not carry the title "{r["title"][:60]}" on its first pages; not filed')
            continue
        doi_ok = r['doi'].lower() in first.lower()
        marks = [mk for mk in MARKERS if re.search(mk, first.lower())]
        d = DEST / rid
        out = d / f'{rid}.pdf'
        if out.exists():
            print(f'{rid}: already filed')
            continue
        d.mkdir()
        shutil.copy2(src, out)
        prov = {'id': rid, 'record_row': int(rid.split('-')[1]), 'search': 'Scopus R-S1 (supplementary regulation search, 7 October 2026)',
                'pre_screen': f"group {r['group']}", 'doi': r['doi'], 'doi_on_first_pages': doi_ok, 'title': r['title'], 'year': r['year'],
                'venue': r['venue'], 'source_file': name, 'source_sha256': sha(src), 'file': out.name, 'sha256': sha(out), 'pages': doc.page_count,
                'version_note': ('not the final version: ' + ', '.join(marks)) if marks else 'no unedited-copy marker on the first pages',
                'how': 'downloaded by the author on 8 October 2026 (open access or Abertay access via LibKey); filed by Claude Code',
                'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
        (d / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding='utf-8')
        subprocess.run([str(PY), str(ROOT / 'scripts' / 'extract_paper.py'), str(out), '--quiet'], check=True)
        subprocess.run([str(PY), str(ROOT / 'scripts' / 'ocr_scanned.py'), str(d)], check=False, capture_output=True)
        print(f"{rid}: filed ({doc.page_count} pages; DOI on first pages: {doi_ok}; {prov['version_note']})")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
