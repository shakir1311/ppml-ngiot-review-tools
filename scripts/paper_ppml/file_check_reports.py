#!/usr/bin/env python3
"""File the full texts the author downloaded after the independent second screening (5 October 2026), and the
published version of S026, and extract each one with the corpus pipeline.

The author: "here are the ones you needed for download - one of them is a full book so carve out relevant pdf from the
book and just keep the chapter in corpus. one of them was not downloadable - remove that".

- Records left uncertain by the second screening (search-ppml/evidence/checks/CHECKS-RESULT-2026-10-05.json) go to
  corpus/ppmlcorpus/check/p<record>/: 5351, 574, 1628, and 5129, a chapter cut out of the downloaded book (only the
  chapter's pages are kept; the book is not filed).
- 1101 could not be downloaded: recorded as not retrieved (search-ppml/evidence/checks/NOT-RETRIEVED-2026-10-05.json).
- The published version of S026 (IEEE COMST 2026) goes to corpus/searchcorpus/_published-versions/S026/, beside the
  preprint already in the corpus.
The first pages of each filed PDF must carry the start of the record's title, otherwise nothing is filed. PROVENANCE.json
records the source file and its SHA-256, the page range taken (for the chapter), the filed file's SHA-256 and the time.
Then extract_paper.py and ocr_scanned.py run on the folder (scripts/.venv).

Usage: scripts/.venv/bin/python scripts/paper_ppml/file_check_reports.py
"""
import csv, datetime, hashlib, json, pathlib, re, shutil, subprocess, unicodedata
import pymupdf

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
DL = pathlib.Path('/Volumes/Stuff/Downloads')
PY = ROOT / 'scripts' / '.venv' / 'bin' / 'python'
HOW = 'downloaded by the author through institutional access on 5 October 2026; filed by Claude Code'
CHECK = ROOT / 'corpus' / 'ppmlcorpus' / 'check'
# record number -> (downloaded file, pages to keep as 1-based inclusive range or None for all)
FILES = {
    5351: ('1-s2.0-S1383762124000250-main.pdf', None),
    574: ('Cloud-Edge_Collaborative_Large_Model_Services_Challenges_and_Solutions.pdf', None),
    1628: ('1-s2.0-S1574013721000885-main.pdf', None),
    5129: ('978-981-96-3077-6.pdf', (462, 474)),          # chapter 28 of the book; p475 opens the next part
}
S026 = ('Zero-Knowledge_Proof-Based_Verifiable_Decentralized_Machine_Learning_in_Communication_Network_A_Comprehensive_Survey (2).pdf',
        'Zero-Knowledge Proof-Based Verifiable Decentralized Machine Learning in Communication Network', '10.1109/COMST.2025.3561657')
NOT_RETRIEVED = {1101: 'not downloadable through the author\'s institutional access (the author, 5 October 2026)'}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s).lower())


def file_one(src, dest, name, title, pages, prov):
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / name
    if pages:
        book = pymupdf.open(src)
        doc = pymupdf.open()
        doc.insert_pdf(book, from_page=pages[0] - 1, to_page=pages[1] - 1)
        doc.save(out)
        doc.close()
    else:
        shutil.copy2(src, out)
    doc = pymupdf.open(out)
    first = ''.join(doc[i].get_text() for i in range(min(2, doc.page_count)))
    if norm(title)[:40] not in norm(first):
        out.unlink()
        return f'{name}: the first pages do not carry the title "{title[:60]}" — not filed'
    prov.update({'source_file': src.name, 'source_sha256': sha(src), 'file': out.name, 'sha256': sha(out), 'pages': doc.page_count,
                 'how': HOW, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')})
    if pages:
        prov['pages_taken_from_source'] = f'{pages[0]}-{pages[1]} (PDF pages of the book)'
    (dest / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding='utf-8')
    subprocess.run([str(PY), str(ROOT / 'scripts' / 'extract_paper.py'), str(out), '--quiet'], check=True)
    subprocess.run([str(PY), str(ROOT / 'scripts' / 'ocr_scanned.py'), str(dest)], check=False, capture_output=True)
    return f'{name}: filed and extracted ({doc.page_count} pages)'


def main():
    rows = {int(r['n']): r for r in csv.DictReader(open(ROOT / 'search-ppml' / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8'))}
    for n, (name, pages) in FILES.items():
        pid = f'p{n:04d}'
        r = rows[n]
        print(file_one(DL / name, CHECK / pid, f'{pid}.pdf', r['title'], pages,
                       {'id': pid, 'record': n, 'doi': r['doi'], 'title': r['title'], 'role': 'full text sought after the second screening'}))
    name, title, doi = S026
    print(file_one(DL / name, ROOT / 'corpus' / 'searchcorpus' / '_published-versions' / 'S026', 'S026-published.pdf', title, None,
                   {'id': 'S026', 'doi': doi, 'title': title, 'role': 'published version of the preprint held in the corpus'}))
    nr = ROOT / 'search-ppml' / 'evidence' / 'checks' / 'NOT-RETRIEVED-2026-10-05.json'
    nr.write_text(json.dumps({str(n): {'title': rows[n]['title'], 'doi': rows[n]['doi'], 'why': why} for n, why in NOT_RETRIEVED.items()},
                             indent=1, ensure_ascii=False), encoding='utf-8')
    print('not retrieved:', list(NOT_RETRIEVED))


if __name__ == '__main__':
    main()
