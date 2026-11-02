#!/usr/bin/env python3
"""Step 1 of the extraction: give every in-scope PDF a folder of its own and write the manifest.

A PDF lying loose in a folder is moved into a new folder named after it, so that the paper, everything
extracted from it and its notes travel together. PDFs already in their own folder are left where they are.
Every paper gets a stable ID (S### survey corpus, N### new corpus, O### old corpus, V### supervisor corpus);
an ID, once given, is kept, and papers added later take the next free number. The ID of a paper that was taken
out of the corpus (corpus/_extraction/EXCLUDED.json) is never given to another paper.

    prepare_corpus.py [--dry-run]
"""
from __future__ import annotations

import argparse
import shutil
import sys

import pymupdf

import corpus as C


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="show what would be moved, change nothing")
    args = ap.parse_args()

    moved = 0
    for pdf in C.find_pdfs():
        target = C.paper_dir(pdf)
        if target == pdf.parent:
            continue
        dest = target / pdf.name
        if dest.exists():
            print(f"SKIP (target exists): {pdf.relative_to(C.CORPUS)}", file=sys.stderr)
            continue
        print(f"{'WOULD MOVE' if args.dry_run else 'MOVE'}: {pdf.relative_to(C.CORPUS)}")
        if not args.dry_run:
            target.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pdf), str(dest))
        moved += 1
    if args.dry_run:
        print(f"{moved} PDF(s) would be moved into a folder of their own")
        return 0

    known = {p["sha256"]: p for p in C.load_manifest()}
    retired = {p["sha256"]: p for p in C.load_excluded()}
    used: dict[str, int] = {}
    for p in list(known.values()) + list(retired.values()):
        used[p["id"][0]] = max(used.get(p["id"][0], 0), int(p["id"][1:]))
    papers = []
    for pdf in C.find_pdfs():
        sha = C.sha256_of(pdf)
        rel = pdf.parent.relative_to(C.CORPUS)
        corpus_name = rel.parts[0]
        prefix = C.PREFIX.get(corpus_name, corpus_name[:1].upper())
        if sha in known:
            pid = known[sha]["id"]
        elif sha in retired:
            pid = retired[sha]["id"]
            print(f"NOTE: {pid} was taken out of the corpus on {retired[sha].get('date')} ({retired[sha].get('reason')}) "
                  f"and is in scope again: {rel.as_posix()}", file=sys.stderr)
        else:
            used[prefix] = used.get(prefix, 0) + 1
            pid = f"{prefix}{used[prefix]:03d}"
        with pymupdf.open(str(pdf)) as doc:
            pages = doc.page_count
        papers.append({"id": pid, "corpus": corpus_name, "group": "/".join(rel.parts[1:-1]), "folder": rel.as_posix(),
                       "pdf": pdf.name, "pages": pages, "sha256": sha})
    papers.sort(key=lambda p: p["id"])
    C.save_manifest(papers)
    per = {}
    for p in papers:
        per[p["corpus"]] = per.get(p["corpus"], 0) + 1
    print(f"moved {moved}; manifest: {len(papers)} papers, {sum(p['pages'] for p in papers)} pages; {per}")
    print(f"written: {C.MANIFEST.relative_to(C.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
