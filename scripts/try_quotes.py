#!/usr/bin/env python3
"""Try quotations against a paper's page text before they go into the notes — with the checker's own matching.

    try_quotes.py <paper folder | ID> <page> "<quotation>"         one quotation
    try_quotes.py <paper folder | ID> --file candidates.tsv          many: one per line, page<TAB>quotation
    try_quotes.py <paper folder | ID> --find "<words>"               on which page(s) the words are
    try_quotes.py <paper folder | ID> --split <page> "<passage>"     where the extracted text interrupts a passage

The page is given as in the notes: 7, p7, p7-8 or "p7, p12". Nothing is written; the paper folder is only read.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import check_notes as K
import corpus as C
import notes_format as N


def try_one(pages: K.Pages, page_spec: str, quote: str) -> bool:
    cited = N.pages_in("[" + page_spec + "]")
    if not cited:
        print(f"FAIL  {page_spec!r} is not a page citation | {quote[:90]}")
        return False
    good = True
    for fragment in N.fragments(quote):
        ok, remark = K.find_fragment(fragment, pages, cited)
        good &= ok
        print(f"{'ok  ' if ok else 'FAIL'}  p{','.join(map(str, cited)):<8} {remark:<46} | {fragment[:110]}")
    return good


def find(pages: K.Pages, text: str) -> bool:
    q = N.squash(text)
    hits = pages.where(q) if q else []
    print("on " + ", ".join(f"p{p}" for p in hits) if hits
          else "not in the paper as extracted (as a continuous run of words on one page)")
    return bool(hits)


def split(pages: K.Pages, page: int, passage: str) -> None:
    """Print the runs of consecutive words of the passage that are continuous in the extracted text of the page."""
    tokens = passage.split()
    i = 0
    while i < len(tokens):
        if N.squash(tokens[i]) and not pages.has(N.squash(tokens[i]), page):
            print(f"  not on p{page}: {tokens[i]}")
            i += 1
            continue
        j = i + 1
        while j < len(tokens) and pages.has(N.squash(" ".join(tokens[i:j + 1])), page):
            j += 1
        run = " ".join(tokens[i:j])
        print(f"  continuous ({len(N.words(run))} words): {run}")
        i = j


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paper", help="paper folder or paper ID")
    ap.add_argument("page", nargs="?")
    ap.add_argument("quotation", nargs="?")
    ap.add_argument("--file", type=Path)
    ap.add_argument("--find")
    ap.add_argument("--split", nargs=2, metavar=("PAGE", "PASSAGE"))
    args = ap.parse_args()
    pages = K.Pages(C.resolve(args.paper))
    if not len(pages):
        print("no per-page text in text/pages/ — run the extraction first")
        return 2
    if args.find:
        return 0 if find(pages, args.find) else 1
    if args.split:
        split(pages, N.pages_in("[" + args.split[0] + "]")[0], args.split[1])
        return 0
    if args.file:
        bad = total = 0
        for raw in args.file.read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.lstrip().startswith("#") or "\t" not in raw:
                continue
            page, quote = raw.split("\t", 1)
            total += 1
            bad += not try_one(pages, page.strip(), quote.strip().strip('"'))
        print(f"\n{total} quotations tried, {bad} failing")
        return 1 if bad else 0
    if not (args.page and args.quotation):
        ap.error("give a page and a quotation, or --file, --find or --split")
    return 0 if try_one(pages, args.page, args.quotation) else 1


if __name__ == "__main__":
    sys.exit(main())
