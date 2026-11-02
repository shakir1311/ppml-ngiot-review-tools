"""The title of a paper, which names its folder and its copy of the PDF: the largest type at the top of the first page (where
publishers set the title), else the title in the PDF's properties, else the file's own name.
"""
from __future__ import annotations

import collections
import re
import unicodedata

JUNK = re.compile(r"microsoft word|untitled|\.docx?\b|\.pdf\b|\.tex\b|^doi\b|^arxiv|^paper\b|^manuscript\b|^template\b|"
                  r"^research article$|^original article$|^review$|^article$", re.I)


def clean(text: str) -> str:
    """One line: spaces closed up, a word broken at a line end joined, footnote marks after the title dropped."""
    from .ocr import is_word
    t = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()

    def join(m):
        whole = m.group(1) + m.group(2)
        return whole if is_word(whole.lower()) else f"{m.group(1)}-{m.group(2)}"
    t = re.sub(r"([A-Za-z]+)- ([a-z]+)", join, t)
    return re.sub(r"[\s*†‡§¶∗]+$|(?<=[A-Za-z])\d{1,2}$", "", t).strip(" .,;")


def plausible(title: str | None) -> bool:
    if not title:
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", title)
    return 3 <= len(words) <= 40 and not JUNK.search(title) and sum(c.isalpha() for c in title) >= 0.6 * len(title.replace(" ", ""))


GARBLED = re.compile(r"[¢©®€£¥¤§¶\ufffd\ue000-\uf8ff]")          # glyphs a font mapped wrongly (a "tt" ligature read as "¢")


FUNCTION = {"of", "for", "the", "in", "on", "with", "a", "an", "to", "via", "using", "based", "towards", "toward", "through", "from",
            "by", "into", "over", "under", "against", "as", "at", "its", "their", "is", "are", "what", "how", "why", "when", "new", "or"}


def author_line(title: str) -> bool:
    """A line of authors: author marks (∗ † ‡), or a list of short capitalised names with none of the small words of a title."""
    if re.search(r"[∗†‡]", title):
        return True
    parts = [x.strip() for x in re.split(r",|;|\band\b", title) if x.strip()]
    if len(parts) < 3 or any(w.lower() in FUNCTION for w in re.findall(r"[A-Za-z]+", title)):
        return False
    names = sum(1 for x in parts if 1 <= len(x.split()) <= 4 and all(w[0].isupper() for w in x.split() if w[0].isalpha()))
    return names >= 0.8 * len(parts)


def suspicious(title: str) -> bool:
    """Not a title, though plausible in length: glyphs mapped wrongly, words run together without spaces, or an author line."""
    return bool(GARBLED.search(title)) or any(len(w) > 24 for w in re.findall(r"[A-Za-z]+", title)) or author_line(title)


def _key(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", t).lower())


def elsewhere(doc, title: str) -> bool:
    """A journal's name, not the title: the subject the PDF's properties give, or a short line (six words or fewer) printed at
    the top of two other pages too. A longer line that heads other pages is the paper's own title as its running head."""
    k = _key(title)[:30]
    if len(k) < 12:
        return False
    if k in _key((doc.metadata or {}).get("subject") or ""):
        return True
    if len(title.split()) > 6:              # a paper's full title is often its running head too; a journal's name is short
        return False
    hits = 0
    for page in list(doc)[1:6]:
        top = page.rect.height * 0.12
        head = " ".join(b[4] for b in page.get_text("blocks") if b[1] < top)
        hits += k in _key(head)
    return hits >= 2


def _line_text(spans: list) -> str:
    """A line's text with a space wherever the gap between two letters is a word's gap (a fifth of the type size or more),
    for titles a PDF draws without space characters."""
    out, last = [], None
    for span in spans:
        for ch in span.get("chars", []):
            c = ch["c"]
            if last is not None and c != " " and out and out[-1] != " " and ch["bbox"][0] - last > 0.2 * span["size"]:
                out.append(" ")
            out.append(c)
            last = ch["bbox"][2]
    return "".join(out)


def _page_lines(page) -> tuple[list, float]:
    lines, sizes = [], collections.Counter()
    for block in page.get_text("rawdict").get("blocks", []):
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if "".join(c["c"] for c in s.get("chars", [])).strip()]
            if not spans:
                continue
            for s in spans:
                sizes[round(s["size"], 1)] += len(s["chars"])
            lines.append((line["bbox"][1], line["bbox"][3], max(s["size"] for s in spans), _line_text(spans)))
    return lines, (sizes.most_common(1)[0][0] if sizes else 0.0)


def first_page_candidates(doc) -> list[str]:
    """Runs of lines in each type larger than the body text (2 pt or more) in the top 60 % of the first page, largest type first,
    each read down the page while its lines follow one another."""
    if doc.page_count == 0:
        return []
    page = doc[0]
    lines, body = _page_lines(page)
    top = [l for l in lines if l[0] < 0.6 * page.rect.height and l[2] >= body + 2 and re.search(r"[A-Za-z]{2,}", l[3])]
    out = []
    for big in sorted({round(l[2], 1) for l in top}, reverse=True):
        run, last = [], None
        for y0, y1, _size, text in sorted((l for l in top if abs(l[2] - big) <= 0.6), key=lambda l: l[0]):
            if last is not None and y0 - last > 2.2 * max(1.0, y1 - y0):
                break                                          # the next line in that type is not part of the title
            run.append(text)
            last = y1
        out.append(clean(" ".join(run)))
    return out


def from_first_page(doc) -> str | None:
    """The first candidate that is a title — four words or more preferred (a journal's name or "Research Article" is short),
    not an author line, not words run together, not a running head or the journal's name."""
    good = [t for t in first_page_candidates(doc) if plausible(t) and not suspicious(t) and not elsewhere(doc, t)]
    return next((t for t in good if len(t.split()) >= 4), good[0] if good else None)


def on_first_page(doc, title: str) -> bool:
    """Whether the first page holds the title's words (its first forty letters, in order): a title in the PDF's properties that
    is printed on the paper is the paper's own."""
    k = _key(title)[:40]
    return len(k) >= 15 and doc.page_count > 0 and k in _key(doc[0].get_text())


def from_file_name(stem: str) -> str:
    """The file's name as a title: a corpus ID, a running number or a year at its head, and underscores, taken off."""
    t = re.sub(r"^[A-Za-z]\d{3,4}\s*-\s*", "", stem)
    t = re.sub(r"^(\[\d{1,3}\]\s*|\d{1,3}\s*-\s*)", "", t)
    t = re.sub(r"^(19|20)\d{2}\s*-\s*", "", t)
    t = re.sub(r"[_]+", " ", t)
    return re.sub(r"\s+", " ", t).strip(" -") or stem


def title_of(doc, stem: str) -> tuple[str, str]:
    """-> (title, where it came from): the PDF's own title where it is printed on the first page ("properties"); else the
    first title-like run of large type on the first page ("first page"); else the PDF's own title ("properties"); else the
    file's name ("file name")."""
    meta = clean((doc.metadata or {}).get("title") or "")
    meta_ok = plausible(meta) and not suspicious(meta) and not elsewhere(doc, meta)   # some PDFs give the journal as title
    if meta_ok and on_first_page(doc, meta):
        return meta, "properties"
    t = from_first_page(doc)
    if t:
        return t, "first page"
    if meta_ok:
        return meta, "properties"
    return from_file_name(stem), "file name"
