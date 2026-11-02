#!/usr/bin/env python3
"""File the PDFs of the studies the author included in the PPML review that were not yet in the corpus (4 October 2026),
into corpus/ppmlcorpus/surveys/<id>/ (all six are surveys), and extract each one as the corpus papers are.

The author: "i am done with screening and inclusion - exclusion. a few new papers that are now included are available in
/Volumes/Stuff/Downloads - add those new papers to corpus and extract them like the way we used to do earlier."

Each PDF is identified by the record of search-ppml/MERGED-RECORDS-2026-10-04.csv it belongs to; the id is p + the record
number. The first page of the filed PDF must carry the start of the record's title, otherwise nothing is filed.
PROVENANCE.json records the source file and its SHA-256, the filed file's SHA-256 and the time. Then extract_paper.py and
ocr_scanned.py run on the folder (scripts/.venv).

Usage: scripts/.venv/bin/python scripts/search_ppml/file_included.py
"""
import csv, datetime, hashlib, json, pathlib, re, shutil, subprocess, unicodedata
import pymupdf

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
DL = pathlib.Path('/Volumes/Stuff/Downloads')
OUT = ROOT / 'corpus' / 'ppmlcorpus' / 'surveys'
PY = ROOT / 'scripts' / '.venv' / 'bin' / 'python'
HOW = 'downloaded by the author through institutional access on 4 October 2026; filed by Claude Code'
FILES = {   # record number -> downloaded file (DOI in the file name, or the title)
    13: 'TSP_CMES_30084.pdf',
    86: 's41060-026-01067-z.pdf',
    156: 'applsci-16-00277-v2.pdf',
    259: 's10462-025-11434-0.pdf',
    435: 's42979-026-04725-y.pdf',
    1162: 'A_Survey_of_Security_Protection_Methods_for_Deep_Learning_Model.pdf',
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s).lower())


def main():
    rows = {int(r['n']): r for r in csv.DictReader(open(ROOT / 'search-ppml' / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8'))}
    for n, name in FILES.items():
        pid = f'p{n:04d}'
        src = DL / name
        if not src.exists():
            print(f'{pid}: {name} not found')
            continue
        dest = OUT / pid
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f'{pid}.pdf'
        shutil.copy2(src, out)
        doc = pymupdf.open(out)
        first = ''.join(doc[i].get_text() for i in range(min(2, doc.page_count)))
        title = rows[n]['title']
        if norm(title)[:40] not in norm(first):
            out.unlink()
            print(f'{pid}: the first pages do not carry the title "{title[:60]}" — not filed')
            continue
        prov = {'id': pid, 'record': n, 'doi': rows[n]['doi'], 'title': title, 'how': HOW, 'source_file': name, 'source_sha256': sha(src),
                'file': out.name, 'sha256': sha(out), 'pages': doc.page_count,
                'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
        (dest / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding='utf-8')
        subprocess.run([str(PY), str(ROOT / 'scripts' / 'extract_paper.py'), str(out), '--quiet'], check=True)
        subprocess.run([str(PY), str(ROOT / 'scripts' / 'ocr_scanned.py'), str(dest)], check=False, capture_output=True)
        print(f'{pid}: filed and extracted ({doc.page_count} pages)')


if __name__ == '__main__':
    main()
