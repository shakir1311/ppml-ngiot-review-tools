#!/usr/bin/env python3
"""File the full texts of the S-ZK records the author included at title and abstract, and extract each with the corpus pipeline.

The author, 12 October 2026: "all these are downloaded except a few which are not available for me so exclude them. some of them
are whole books so carve out relevant chapter ... And run the extraction pipeline on them . and dont upload any of them to
claude" / "and add all them to corpus".

Only the PDFs named in the mapping file are opened (matched beforehand by file name, DOI-derived name or ISBN; the Downloads
folder also holds private documents). A book is carved to its chapter with the outline (table of contents) by the record's
title (paper_ppml/carve_chapters.chapter_range); a chapter found only by a title search is reported for a look. Every filed PDF
must carry the record's title on its first two pages; whether it prints the DOI and any phrase that marks an unedited copy
(paper_ppml/version_notes.MARKERS) are recorded. A match is written to corpus/ppmlcorpus/check-szk/SZK-<n>/SZK-<n>.pdf with
PROVENANCE.json (source file and SHA-256, filed file and SHA-256, pages, pages taken from a book, version), then
scripts/extract_paper.py and scripts/ocr_scanned.py run on the folder, several papers at a time. The folders are listed in
corpus/ppmlcorpus/check-szk/MANIFEST-S-ZK.json in the form of the corpus manifest, so that the rest of the extraction
pipeline runs on them like any corpus paper: scripts/verify_ocr.py --manifest <it> --tesseract --apply (every page against
local OCR of its render) and scripts/check_extraction.py --manifest <it> (the audit), or all steps with
scripts/run_extraction.sh --manifest <it>. Nothing in Downloads is moved or deleted,
and nothing a paper says is printed: the output is verdicts, counts and page numbers.

Usage: scripts/.venv/bin/python scripts/search_ppml/file_szk_downloads.py <mapping.json> [--ids 501990 ...] [--jobs N]
       mapping: {"<S-ZK number>": {"file": "<file name in Downloads>", "book": false}, ...}
       optional per entry: "pages": "a-b" with "pages_note" (a book's chapter set by hand, e.g. to leave out an index that
       follows the last chapter); "accept_by_doi": true with "why" (a page-image PDF whose text layer holds only the
       publisher's stamp: the DOI on the first page identifies it, and the title is checked again on the OCR text);
       "ocr_threshold": N (OCR every page with fewer than N characters of text layer; see ocr_scanned.STANDS_IN_RATIO)
"""
import argparse, concurrent.futures, csv, datetime, hashlib, json, pathlib, re, shutil, subprocess, sys, unicodedata

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'paper_ppml'))
from version_notes import MARKERS                                    # noqa: E402
from carve_chapters import chapter_range                             # noqa: E402

csv.field_size_limit(10 ** 9)
DL = pathlib.Path('/Volumes/Stuff/Downloads')
DEST = ROOT / 'corpus' / 'ppmlcorpus' / 'check-szk'
SZK = ROOT / 'search-ppml' / 'evidence' / 'szk-search'
LOGS = SZK / 'fulltext' / 'logs'
PY = ROOT / 'scripts' / '.venv' / 'bin' / 'python'
norm = lambda s: re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s or '').lower())
sha = lambda f: hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()


def first_pages(doc):
    return re.sub(r'\s+', ' ', ''.join(doc[i].get_text() for i in range(min(2, doc.page_count))))


def file_one(n, entry, r):
    """copy (or carve) and check one report; returns the provenance, or None with the reason printed"""
    rid = f'SZK-{n}'
    d = DEST / rid
    out = d / f'{rid}.pdf'
    if out.exists():
        print(f'{rid}: already filed')
        return json.loads((d / 'PROVENANCE.json').read_text(encoding='utf-8'))
    src = DL / entry['file']
    doc = pymupdf.open(src)
    carved = None
    if entry.get('book') and entry.get('pages'):
        a, b = map(int, entry['pages'].split('-'))
        part = pymupdf.open()
        part.insert_pdf(doc, from_page=a - 1, to_page=b - 1)
        carved = {'source_pages': doc.page_count, 'pages_taken_from_source': f'{a}-{b}', 'found_by': entry.get('pages_note', 'set by hand')}
        doc = part
    elif entry.get('book'):
        rng = chapter_range(doc, r['title'])
        if not rng:
            print(f'{rid}: the chapter is not found in the book {src.name} ({doc.page_count} pages); not filed')
            return None
        a, b, how = rng
        part = pymupdf.open()
        part.insert_pdf(doc, from_page=a - 1, to_page=b - 1)
        carved = {'source_pages': doc.page_count, 'pages_taken_from_source': f'{a}-{b}', 'found_by': how}
        doc = part
    first = first_pages(doc)
    by_doi = entry.get('accept_by_doi') and norm(r['doi']) in norm(first)
    if norm(r['title'])[:50] not in norm(first) and not by_doi:
        print(f'{rid}: the PDF does not carry the record\'s title on its first two pages; not filed')
        return None
    marks = [mk for mk in MARKERS if re.search(mk, first.lower())]
    d.mkdir(parents=True)
    if carved:
        doc.save(out, garbage=3, deflate=True)
    else:
        shutil.copy2(src, out)
    prov = {'id': rid, 'szk_number': int(n), 'record_of_2_october': int(n) - 500000,
            'search': 'S-ZK: the searches of 2 October 2026 with ledger and zero-knowledge terms (Scopus S1, S2, X5; IEEE Xplore and '
                      'ScienceDirect for S1)',
            'screening': 'included at title and abstract by the author, 12 October 2026 (Claude suggested a decision, the author decided)',
            'doi': r['doi'], 'doi_on_first_pages': norm(r['doi']) in norm(first), 'title': r['title'], 'year': r['year'], 'venue': r['venue'],
            'source_file': src.name, 'source_sha256': sha(src), 'file': out.name, 'sha256': sha(out), 'pages': doc.page_count,
            **({'carved_from_book': carved} if carved else {}),
            **({'identified_by': 'the DOI on the first page (' + entry.get('why', '') + ')'} if by_doi else {}),
            'version_note': ('not the final version: ' + ', '.join(marks)) if marks else 'no unedited-copy marker on the first pages',
            'how': 'downloaded by the author on 12 October 2026; filed by Claude Code (file names and the record only; no text read)',
            'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
    (d / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f"{rid}: filed ({doc.page_count} pages{'; carved from a book of ' + str(carved['source_pages']) + ' pages, pages ' + carved['pages_taken_from_source'] + ', ' + carved['found_by'] if carved else ''}; "
          f"DOI on first pages: {prov['doi_on_first_pages']}; {prov['version_note']})")
    return prov


def extract(rid, ocr_threshold=None):
    """the corpus pipeline on one folder; output to a log (never printed), the exit codes returned"""
    d = DEST / rid
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f'{rid}.log', 'w', encoding='utf-8') as log:
        a = subprocess.run([str(PY), str(ROOT / 'scripts' / 'extract_paper.py'), str(d / f'{rid}.pdf'), '--quiet'], stdout=log, stderr=log)
        if a.returncode:                                     # once more, as extract_corpus.py does
            a = subprocess.run([str(PY), str(ROOT / 'scripts' / 'extract_paper.py'), str(d / f'{rid}.pdf'), '--quiet', '--force'],
                               stdout=log, stderr=log)
        b = subprocess.run([str(PY), str(ROOT / 'scripts' / 'ocr_scanned.py'), str(d)]
                           + (['--threshold', str(ocr_threshold), '--force'] if ocr_threshold else []), stdout=log, stderr=log)
    return rid, a.returncode, b.returncode


def manifest():
    """the S-ZK folders in the form of the corpus manifest (corpus.py), for the extraction audit"""
    papers = []
    for d in sorted(DEST.glob('SZK-*')):
        p = json.loads((d / 'PROVENANCE.json').read_text(encoding='utf-8'))
        papers.append({'id': p['id'], 'corpus': 'ppmlcorpus', 'group': 'check-szk', 'folder': d.relative_to(ROOT / 'corpus').as_posix(),
                       'pdf': p['file'], 'pages': p['pages'], 'sha256': p['sha256']})
    (DEST / 'MANIFEST-S-ZK.json').write_text(json.dumps({'root': 'corpus', 'count': len(papers), 'papers': papers}, indent=1),
                                             encoding='utf-8')
    return papers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mapping')
    ap.add_argument('--ids', nargs='*')
    ap.add_argument('--jobs', type=int, default=4)
    args = ap.parse_args()
    rec = {r['n']: r for r in csv.DictReader(open(sorted(SZK.glob('SZK-RECORDS-*.csv'))[-1], encoding='utf-8'))}
    m = json.loads(pathlib.Path(args.mapping).read_text(encoding='utf-8'))
    ids = [n for n in sorted(m) if not args.ids or n in args.ids]
    filed = []
    for n in ids:
        if file_one(n, m[n], rec[n]):
            filed.append(f'SZK-{n}')
    todo = [rid for rid in filed if not (DEST / rid / 'metadata.json').exists()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        thr = {f'SZK-{n}': m[n].get('ocr_threshold') for n in m}
        for rid, a, b in pool.map(lambda rid: extract(rid, thr.get(rid)), todo):
            print(f'{rid}: extraction {"ok" if a == 0 else "FAILED (exit " + str(a) + ")"}; OCR {"ok" if b == 0 else "exit " + str(b)}')
    papers = manifest()
    print(f'{len(filed)} of {len(ids)} filed; {len(todo)} extracted now; {len(papers)} in {DEST.relative_to(ROOT)}/MANIFEST-S-ZK.json')


if __name__ == '__main__':
    main()
