#!/usr/bin/env python3
"""Check every quotation in a policy document against the saved copy of its source.

    verify_policy_quotes.py <document.html>

The document marks each quotation as  <q data-src="ID" [data-page="N" | data-page="N-M"]>…</q>  and lists each source
as an element with  id="ID"  and  data-text="<path>"  (relative to the document). The path is either

  - a saved web page (.html): its visible text is compared, or
  - a saved page text (.txt, e.g. text read in Chrome): compared as it is, or
  - an extract_paper.py folder of a PDF: text/full.txt is compared, or, when the quotation carries data-page,
    only the text of those pages (text/pages/page_NNNN.txt), so the page cited is checked as well.

Text is compared after Unicode normalisation (NFKC), straight quotes and hyphens, removal of zero-width and soft
hyphen characters, and collapsed whitespace; for PDFs a line-end hyphenation ("non- recoverable") also matches
the joined form. Prints one line per failure and a summary; exits 1 if any quotation is not found.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

# hyphen, non-breaking hyphen, figure dash, en dash, em dash, horizontal bar, minus sign
DASHES = dict.fromkeys([0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212], "-")
# curly single and double quotation marks
QUOTES = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'}
# zero-width space / non-joiner / joiner, word joiner, byte-order mark, soft hyphen
INVISIBLE = dict.fromkeys([0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD], None)
INLINE = {"a", "abbr", "b", "cite", "code", "em", "font", "i", "mark", "q", "s", "small", "span", "strong", "sub", "sup",
          "u"}


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(DASHES).translate(QUOTES).translate(INVISIBLE)
    return re.sub(r"\s+", " ", text).strip()


class TextOf(HTMLParser):
    """Visible text of a page: everything outside script/style/noscript; block (not inline) tags become spaces."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "template"):
            self.skip += 1
        if tag not in INLINE:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template") and self.skip:
            self.skip -= 1
        if tag not in INLINE:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


class Document(HTMLParser):
    """Collect the quotations (<q data-src>) and the source list (elements with data-text) of the document."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: dict[str, str] = {}
        self.quotes: list[dict] = []
        self.open_quotes: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "data-text" in a and "id" in a:
            self.sources[a["id"]] = a["data-text"]
        if tag == "q" and "data-src" in a:
            self.open_quotes.append({"src": a["data-src"], "page": a.get("data-page"), "text": "",
                                     "line": self.getpos()[0]})

    def handle_endtag(self, tag):
        if tag == "q" and self.open_quotes:
            self.quotes.append(self.open_quotes.pop())

    def handle_data(self, data):
        for quote in self.open_quotes:
            quote["text"] += data


def page_numbers(spec: str) -> list[int]:
    first, _, last = spec.partition("-")
    return list(range(int(first), int(last or first) + 1))


def source_text(path: Path, pages: str | None, cache: dict) -> str:
    key = (path, pages)
    if key not in cache:
        if path.suffix == ".html":
            parser = TextOf()
            parser.feed(path.read_text(encoding="utf-8", errors="replace"))
            text = normalise("".join(parser.parts))
        elif path.suffix == ".txt":
            text = normalise(path.read_text(encoding="utf-8", errors="replace"))
        else:
            files = ([path / "text" / "pages" / f"page_{n:04d}.txt" for n in page_numbers(pages)] if pages
                     else [path / "text" / "full.txt"])
            text = normalise(" ".join(f.read_text(encoding="utf-8") for f in files))
            text += " || " + re.sub(r"(\w)- (\w)", r"\1\2", text) + " || " + re.sub(r"(\w)- (\w)", r"\1-\2", text)
        cache[key] = text
    return cache[key]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    doc_path = Path(sys.argv[1]).resolve()
    doc = Document()
    doc.feed(doc_path.read_text(encoding="utf-8"))

    cache: dict = {}
    failures = 0
    per_source: dict[str, int] = {}
    for quote in doc.quotes:
        src = quote["src"]
        per_source[src] = per_source.get(src, 0) + 1
        if src not in doc.sources:
            print(f"line {quote['line']}: unknown source id {src!r}")
            failures += 1
            continue
        path = (doc_path.parent / doc.sources[src]).resolve()
        if not path.exists():
            print(f"line {quote['line']}: source file missing for {src}: {path}")
            failures += 1
            continue
        needle = normalise(quote["text"])
        if needle not in source_text(path, quote["page"], cache):
            where = f" on page(s) {quote['page']}" if quote["page"] else ""
            print(f"line {quote['line']}: NOT FOUND in {src}{where}: “{needle[:110]}”")
            failures += 1

    print(f"{len(doc.quotes) - failures}/{len(doc.quotes)} quotations found verbatim in their sources "
          f"({', '.join(f'{k} {v}' for k, v in sorted(per_source.items()))})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
