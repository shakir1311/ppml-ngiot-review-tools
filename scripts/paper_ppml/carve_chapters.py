#!/usr/bin/env python3
"""Carve a chapter out of a downloaded book (or proceedings volume), so that the corpus keeps only the article.

The author, 5 October 2026: "in springer nature a few of them were books - we need to carve out the pdfs and only keep the
actual article". For each (record, book PDF): the chapter is found in the book's own outline (table of contents) by the
record's title; it runs to the page before the next entry of the same or a higher level. Without an outline entry, the
first page whose opening lines carry the title starts the chapter, and the chapter ends before the next page whose opening
lines carry another outline title or "References" of the next chapter — that case is reported for a look. A PDF of fewer
than 60 pages whose first pages carry the title is taken as the chapter itself and passed on unchanged.

The carved PDF is written to search-ppml/evidence/rescreen/carved/, with a sidecar <name>.carve.json (book file, its
SHA-256, the PDF pages taken). file_rescreen_downloads.py reads the sidecar and
records the book and the pages in PROVENANCE.json; the book itself is never filed.

Usage: scripts/.venv/bin/python scripts/paper_ppml/carve_chapters.py <record>=<book.pdf> [...]
"""
import csv, hashlib, json, pathlib, re, sys, unicodedata
import pymupdf

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
RS = ROOT / 'search-ppml' / 'evidence' / 'rescreen'
OUT = RS / 'carved'


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s or '').lower())


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def opening(doc, i, chars=600):
    return norm(doc[i].get_text()[:chars])


def chapter_range(doc, title):
    key = norm(title)[:40]
    toc = doc.get_toc(simple=True)                       # [level, title, page (1-based)]
    for j, (lvl, t, pg) in enumerate(toc):
        if key and key[:30] in norm(t) or norm(t)[:30] and norm(t)[:30] in key:
            end = doc.page_count
            for lvl2, _, pg2 in toc[j + 1:]:
                if lvl2 <= lvl and pg2 > pg:
                    end = pg2 - 1
                    break
            return pg, end, 'outline'
    starts = [i for i in range(doc.page_count) if key and key in opening(doc, i, 900)]
    if not starts:
        return None
    s = starts[0]
    others = [norm(t)[:30] for _, t, _ in toc if norm(t)[:30]]
    for i in range(s + 1, doc.page_count):
        op = opening(doc, i, 400)
        if any(o and o in op for o in others):
            return s + 1, i, 'title search (check)'
    return s + 1, doc.page_count, 'title search to the end (check)'


def main(pairs):
    recs = {r['n']: r for r in csv.DictReader(open(RS / 'RESCREEN-DECISIONS-2026-10-05.csv', encoding='utf-8'))}
    OUT.mkdir(exist_ok=True)
    for pair in pairs:
        n, book = pair.split('=', 1)
        book = pathlib.Path(book)
        r = recs[n]
        doc = pymupdf.open(book)
        first = norm(''.join(doc[i].get_text() for i in range(min(2, doc.page_count))))
        out = OUT / f'p{int(n):04d}-chapter.pdf'
        if doc.page_count < 60 and norm(r['title'])[:40] in first:
            doc.save(out)
            side = {'record': int(n), 'source_file': book.name, 'source_sha256': sha(book), 'pages_taken_from_source': f'1-{doc.page_count} (the file is the chapter itself)'}
            print(f'{n}: the file is the chapter itself ({doc.page_count} pages)')
        else:
            rng = chapter_range(doc, r['title'])
            if not rng:
                print(f'{n}: chapter "{r["title"][:60]}" not found in {book.name} ({doc.page_count} pages) — not carved')
                continue
            a, b, how = rng
            ch = pymupdf.open()
            ch.insert_pdf(doc, from_page=a - 1, to_page=b - 1)
            ch.save(out)
            side = {'record': int(n), 'source_file': book.name, 'source_sha256': sha(book), 'source_pages': doc.page_count,
                    'pages_taken_from_source': f'{a}-{b} (PDF pages of the book; found by {how})'}
            print(f'{n}: pages {a}-{b} of {doc.page_count} ({how}) -> {out.name}')
        (OUT / (out.name + '.carve.json')).write_text(json.dumps(side, indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1:])
