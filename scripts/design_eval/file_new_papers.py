#!/usr/bin/env python3
"""Files the papers of the new designs from the author's downloads into each design's paper/ folder, carving a chapter out of a book where the download is a whole volume.

Each download is named in FILES (the author saved them in /Volumes/Stuff/Downloads; nothing else there is opened). A local
check confirms the download is the paper: its normalised title is found in the PDF's metadata title or on its first page
(only yes or no is reported). A whole book is carved: the chapter is found in the book's own outline by its title and runs
to the page before the next entry of the same or a higher level; its length is checked against the printed page range
Crossref gives. The paper is copied, or the carved chapter written, to paper/<Znn>/<Znn>.pdf (the folder the extraction pipeline fills), with paper/PROVENANCE.json (source
file, its SHA-256 and size, pages taken from a book). Writes design-evaluation/new-designs/MANIFEST-PAPERS.json for the
extraction pipeline (scripts/run_extraction.sh --manifest). The downloads are left as they are.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/file_new_papers.py
"""
import hashlib, json, pathlib, re, shutil, sys, unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, save_json, now   # noqa: E402

DL = pathlib.Path('/Volumes/Stuff/Downloads')
BASE = EVAL / 'new-designs'
FILES = {'Z01': '3770855.3817739.pdf', 'Z02': '978-3-031-94898-5.pdf',
         'Z03': 'Advancing_Blockchain-based_Federated_Learning_through_Verifiable_Off-chain_Computations.pdf',
         'Z04': 'RoFL_Robustness_of_Secure_Federated_Learning.pdf', 'Z05': 'zkDL_Efficient_Zero-Knowledge_Proofs_of_Deep_Learning_Training.pdf',
         'Z06': '3576915.3623202.pdf', 'Z07': '2611.10020v1.pdf', 'Z08': 'fdgth-08-1821129.pdf', 'Z09': 'main.pdf'}
BOOKS = {'Z02': {'printed_pages': (584, 594)}}    # Crossref, chapter 10.1007/978-3-031-94898-5_44


def norm(s):
    s = unicodedata.normalize('NFKC', s or '').lower()
    return re.sub(r'[^a-z0-9]', '', s)


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    import pymupdf
    designs = {json.load(open(d / 'design.json'))['id']: (d, json.load(open(d / 'design.json'))) for d in (BASE / 'designs').iterdir() if (d / 'design.json').exists()}
    papers = []
    for did, fname in FILES.items():
        folder, meta = designs[did]
        src = DL / fname
        title = meta.get('paper') or ''
        key = norm(title)[:60]
        (folder / 'paper' / did).mkdir(parents=True, exist_ok=True)
        out = folder / 'paper' / did / f'{did}.pdf'     # the pipeline extracts into the folder named after the PDF
        prov = {'source': str(src), 'source_sha256': sha(src), 'source_bytes': src.stat().st_size, 'filed': now()}
        doc = pymupdf.open(src)
        if did in BOOKS:
            toc = doc.get_toc()
            hit = next((i for i, (lvl, t, pg) in enumerate(toc) if norm(t).startswith(key[:40])), None)
            if hit is None:
                print(f'{did}: chapter not found in the outline: not filed')
                continue
            lvl, t, start = toc[hit]
            end = next((pg - 1 for (l2, t2, pg) in toc[hit + 1:] if l2 <= lvl), doc.page_count)
            want = BOOKS[did]['printed_pages'][1] - BOOKS[did]['printed_pages'][0] + 1
            n = end - start + 1
            part = pymupdf.open()
            part.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
            part.save(out)
            prov.update({'carved_from_book': True, 'book_pages_taken': [start, end], 'pages': n, 'printed_pages_crossref': list(BOOKS[did]['printed_pages']),
                         'length_agrees_with_crossref': n == want})
            check_doc = pymupdf.open(out)
            print(f'{did}: carved book pages {start}-{end} ({n} pages; Crossref says {want}: {"agrees" if n == want else "DIFFERS"})')
        else:
            shutil.copy2(src, out)
            check_doc = pymupdf.open(out)
            prov.update({'carved_from_book': False, 'pages': check_doc.page_count})
        first = norm(check_doc[0].get_text()) if check_doc.page_count else ''
        meta_title = norm((check_doc.metadata or {}).get('title', ''))
        prov['title_on_first_page'] = bool(key) and key[:50] in first
        prov['title_in_pdf_metadata'] = bool(key) and key[:50] in meta_title
        prov['pdf_sha256'] = sha(out)
        save_json(folder / 'paper' / 'PROVENANCE.json', prov)
        print(f"{did}: {out.relative_to(BASE)}  pages {check_doc.page_count}  title on first page: {prov['title_on_first_page']}  "
              f"in metadata: {prov['title_in_pdf_metadata']}")
        papers.append({'id': f'{did}-PAPER', 'corpus': 'design-evaluation', 'group': 'new-designs',
                       'folder': '../' + str((folder / 'paper' / did).relative_to(ROOT)), 'pdf': out.name,
                       'pages': check_doc.page_count, 'sha256': prov['pdf_sha256']})
    save_json(BASE / 'MANIFEST-PAPERS.json', {'root': 'corpus', 'count': len(papers),
              'about': 'The papers of the new designs, filed from the author\'s downloads; folders relative to corpus/ for the extraction pipeline.',
              'papers': papers})
    print(f'{len(papers)} papers filed; manifest design-evaluation/new-designs/MANIFEST-PAPERS.json')


if __name__ == '__main__':
    main()
