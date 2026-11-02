#!/usr/bin/env python3
"""Check one paper's notes against the paper itself.

Tests, in the terms of NOTES-PROTOCOL.md: the header is complete and uses the agreed vocabulary; every section, facet
and rigour item is present; every statement carries a page citation; every quotation is, word for word, on the one
page cited before it; the sections that must quote do quote; every page of the body is cited at least once; every
figure, table and algorithm the text of the paper shows is in the inventory. Writes notes/check.json and prints PASS
or FAIL with what to correct.

A quotation is "on the page" when its words run on, in the same order and without a gap, in the text of that page
as any of the engines read it (text/pages, text/variants, text/pages_ocr). Case, punctuation, spacing and hyphenation
are ignored; the words are not.

    check_notes.py <paper folder | paper ID> [...]
    check_notes.py --all            every paper in the manifest that has notes; prints one line each
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import corpus as C
import notes_format as N

MIN_TESTED = 8           # a quotation with fewer letters and digits than this cannot be told from chance
OUTSIDE = r"(?:Extended\s+Data|Supplementary|Supplemental|Supporting|Additional|Appendix)"
CAPTION = re.compile(r"^[ \t]*(" + OUTSIDE + r"\s+)?(Fig\.|Figure|FIGURE|FIG\.|Table|TABLE|Algorithm|ALGORITHM)\s+(\d+|[IVXLC]+)\b", re.M)
KIND = {"fig": "Fig.", "tab": "Table", "alg": "Algorithm"}
LISTED = re.compile(r"(" + OUTSIDE + r"\s+)?(Fig(?:ure)?s?\.?|Tables?|Algorithms?|Alg\.)\s*(\d+|[IVXLC]+)\b"
                    r"(?:\s*(?:–|-|to|and|,)\s*(\d+|[IVXLC]+)\b)?", re.I)
FRONT_MATTER = re.compile(r"(?i)^(references|acknowledg|abstract|keywords|index terms|ccs concepts|acm reference|"
                          r"additional key|author|funding|conflict|data availability|declaration|appendix$|"
                          r"(table|fig\.?|figure|algorithm)\s+([ivxlc]+|\d+)\b)")


class Pages:
    """The text of every page as every engine read it, ready for matching."""

    def __init__(self, folder: Path):
        self.text = C.page_texts(folder)                      # the reading text, page by page
        self.versions: dict[int, list[str]] = {}
        for n, texts in C.page_versions(folder).items():
            forms = []
            for t in texts:
                forms.append(N.squash(t))
                bare = "\n".join(l for l in t.splitlines() if not re.fullmatch(r"\s*\d{1,4}\s*", l))
                forms.append(N.squash(bare))                  # without lines that hold only a number (line numbers)
            self.versions[n] = list(dict.fromkeys(forms))

    def __len__(self) -> int:
        return len(self.text)

    def __contains__(self, page: int) -> bool:
        return page in self.text

    def has(self, q: str, page: int) -> bool:
        return any(q in v for v in self.versions.get(page, []))

    def has_apart_from_numbers(self, q: str, page: int) -> bool:
        """The words run on in the page when numbers that stand in the page but not in the quotation — reference
        numbers set against a word, 'medicine1,2' — are passed over. Every number of the quotation must be there."""
        pattern = re.compile(r"\d*".join(re.escape(c) for c in q))
        return any(pattern.search(v) for v in self.versions.get(page, []))

    def where(self, q: str) -> list[int]:
        return [p for p in sorted(self.versions) if self.has(q, p)]


def find_fragment(fragment: str, pages: Pages, cited: list[int]) -> tuple[bool, str]:
    """Is the quoted fragment on the cited page?  -> (found, remark)"""
    q = N.squash(fragment)
    if len(q) < MIN_TESTED:
        return True, "too short to test"
    span = sorted(set(cited))
    on = [p for p in span if pages.has(q, p)]
    if on:
        return True, "exact"
    if len(q) <= 400 and any(pages.has_apart_from_numbers(q, p) for p in span):
        return True, "exact apart from reference numbers in the text"
    w = N.words(fragment)
    for p in span:                                            # does it run over the page break?
        for k in range(len(w) - 1, 0, -1):
            head, tail = "".join(w[:k]), "".join(w[k:])
            if len(head) >= MIN_TESTED and len(tail) >= MIN_TESTED and pages.has(head, p) and pages.has(tail, p + 1):
                return False, (f"the quotation runs over the page break: its first {k} words are on p{p}, the rest on "
                               f"p{p + 1} — write it as two quotations, each after its own page")
    elsewhere = pages.where(q)
    if elsewhere:
        return False, f"not on the cited page; the words are on p{', p'.join(map(str, elsewhere[:4]))}"
    k = len(w)
    while k > 0 and not pages.where("".join(w[:k])):
        k -= 1
    if k >= 4:
        at = pages.where("".join(w[:k]))
        return False, (f"these words do not run on in the paper: the first {k} words are on p{at[0]}, then the text "
                       f"there continues differently from \"{' '.join(fragment.split()[k:k + 6])}\" — quote the text exactly "
                       f"as printed, or end the quotation where the text is interrupted")
    return False, "these words are not in the paper as extracted — quote the text exactly as printed"


def captions(pages: Pages) -> dict[tuple[str, int], int]:
    """(kind, number) -> first page, for every caption that starts a line in the text of the paper."""
    out: dict[tuple[str, int], int] = {}
    for p in sorted(pages.text):
        text = pages.text[p]
        for m in CAPTION.finditer(text):
            before = text[:m.start()].rstrip().rsplit("\n", 1)[-1]
            if m.group(1) or re.search(OUTSIDE + r"\s*$", before):
                continue                      # extended data and supplementary items are numbered on their own
            num = N.number_of(m.group(3))
            if num:
                out.setdefault((KIND[m.group(2).lower()[:3]], num), p)
    return out


def inventory(statements: list[N.Statement]) -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    for s in statements:
        if s.section != N.INVENTORY:
            continue
        for m in LISTED.finditer(s.text.split("—")[0] if "—" in s.text[:80] else s.text[:80]):
            kind = KIND.get(m.group(2).lower()[:3])
            if m.group(1):
                kind = None                   # extended data and supplementary items are numbered on their own
            a, b = N.number_of(m.group(3)), N.number_of(m.group(4) or "")
            if kind and a:
                out.update((kind, i) for i in range(a, (b if b and a < b <= a + 60 else a) + 1))
    return out


def check_header(header: dict, folder: Path, total: int, err: list[str], warn: list[str]) -> list[int]:
    for f in N.HEADER_FIELDS:
        if f not in header or header[f] in ("", [], None) or "<" in str(header[f]):
            err.append(f"header field '{f}' is missing or still a placeholder")
    if str(header.get("template", "")) not in ("", str(N.TEMPLATE)):
        err.append(f"header says template {header.get('template')}; the protocol is at template {N.TEMPLATE}")
    for f, allowed in N.CHOICES.items():
        ok = {N.squash(a) for a in allowed}
        for v in N.as_list(header.get(f, "")):
            if N.squash(v) not in ok and not v.lower().startswith("other:"):
                err.append(f"header field '{f}': \"{v}\" is not one of {allowed} (or 'other: …')")
    entry = C.entry_of(folder)
    if entry:
        if str(header.get("id", "")).upper() != entry["id"].upper():
            err.append(f"header says id {header.get('id')}; the manifest gives this folder {entry['id']}")
        source = f"{entry['corpus']} / {entry['group']}"
        if N.squash(str(header.get("source", ""))) != N.squash(source):
            err.append(f"header field 'source' must be \"{source}\" (corpus and group from the manifest)")
    if str(header.get("pages_total", "")).isdigit() and int(header["pages_total"]) != total:
        err.append(f"header says {header['pages_total']} pages; the paper has {total}")
    body = [p for p in N.parse_range(header.get("body_pages", "")) if 1 <= p <= total]
    if not body:
        err.append("header field 'body_pages' does not give a page range")
    for f in ("keywords_authors", "appendix_pages", "read_on"):
        if f not in header:
            warn.append(f"header field '{f}' is not filled in (write none, or [] for no keywords printed)")
    return body


def check(folder: Path) -> dict:
    notes = folder / "notes" / "NOTES.md"
    result: dict = {"folder": folder.relative_to(C.CORPUS).as_posix() if C.CORPUS in folder.parents else str(folder),
                    "template": N.TEMPLATE, "passed": False, "errors": [], "warnings": []}
    if not notes.exists():
        result["errors"].append("notes/NOTES.md does not exist")
        return result
    pages = Pages(folder)
    if not len(pages):
        result["errors"].append("no per-page text in text/pages/ — run the extraction first")
        return result
    header, statements, found, problems = N.parse(notes)
    err, warn = result["errors"], result["warnings"]
    err.extend(problems)
    total = len(pages)
    body = check_header(header, folder, total, err, warn)
    for n, title in N.headings(notes).items():
        if n in N.SECTIONS and N.squash(title) != N.squash(N.SECTIONS[n]):
            warn.append(f"section {n} is headed \"{title}\"; the template has \"{N.SECTIONS[n]}\"")

    tested = failed = short = 0
    for s in statements:
        if s.section == N.COVERAGE:
            continue
        where = f"line {s.line} (section {s.section}{' ' + s.facet if s.facet else ''})"
        beyond = [p for p in s.pages if p < 1 or p > total]
        if beyond:
            err.append(f"{where}: cites page(s) {beyond} — the paper has {total} pages")
        if not s.pages and not s.absent:
            err.append(f"{where}: no page citation — \"{s.text[:90]}\"")
        checkable = 0
        for quote, cited in s.quotes:
            if not cited:
                err.append(f"{where}: quotation without a page citation before it — \"{quote[:70]}\"")
                continue
            if len(set(cited)) > 1:
                on = [p for p in sorted(set(cited)) if all(pages.has(N.squash(f), p) for f in N.fragments(quote))]
                err.append(f"{where}: the quotation follows a citation of several pages [{', '.join(f'p{p}' for p in sorted(set(cited)))}]"
                           f" — cite the one page it is on{' (p' + str(on[0]) + ')' if on else ''}: \"{quote[:60]}\"")
                continue
            if len(quote.split()) > 60:
                warn.append(f"{where}: a quotation of {len(quote.split())} words — keep quotations to about 40")
            for fragment in N.fragments(quote):
                ok, remark = find_fragment(fragment, pages, cited)
                if remark == "too short to test":
                    short += 1
                    continue
                tested += 1
                checkable += 1
                if not ok:
                    failed += 1
                    err.append(f"{where}: quotation not found on p{cited[0]} — \"{fragment[:80]}\" — {remark}")
        if s.section in N.QUOTE_REQUIRED and not s.absent and not s.image_only and not checkable:
            err.append(f"{where}: this section needs the authors' words quoted"
                       f"{' (the quotation given is too short to be checked)' if s.quotes else ''} — \"{s.text[:90]}\"")
        if s.absent and s.quotes and s.section in N.QUOTE_REQUIRED:
            warn.append(f"{where}: the line starts like an absence line but carries a quotation — if it reports what the "
                        f"paper says, start it differently")

    cited_pages = sorted({p for s in statements if s.section != N.COVERAGE for p in s.pages})
    uncited = [p for p in body if p not in cited_pages]
    blank = [p for p in uncited if len(pages.text.get(p, "").strip()) < 200 and len(max(pages.versions.get(p, [""]), key=len)) < 200]
    for p in blank:
        warn.append(f"p{p} is not cited and holds almost no text (blank or figure-only page) — confirm on the page render")
    real = [p for p in uncited if p not in blank]
    if real:
        err.append("body pages never cited: " + ", ".join(f"p{p}" for p in real) + " — every body page must be accounted for")

    per_section = {n: sum(1 for s in statements if s.section == n) for n in N.SECTIONS}
    for n, least in ((1, 3), (2, 2), (3, 1), (4, 2), (5, 5), (7, 1), (8, 1), (9, 1), (10, 1), (11, 1), (12, 1), (13, 1),
                     (14, 1), (15, len(N.RIGOUR)), (16, 1), (17, 4)):
        if per_section.get(n, 0) < least:
            err.append(f"section {n} ({N.SECTIONS[n]}) has {per_section.get(n, 0)} statement(s); at least {least} expected "
                       f"(an absence line counts)")
    content = [s for s in statements if s.section < N.COVERAGE and not s.absent]
    if body and len(content) / len(body) < 3:
        warn.append(f"{len(content)} statements for {len(body)} body pages — under three per page; check nothing was summarised away")

    listed = inventory(statements)
    for (kind, num), page in sorted(captions(pages).items()):
        if (kind, num) not in listed:
            err.append(f"{kind} {num} (caption on p{page}) is not in the inventory of section {N.INVENTORY}")
    for kind in KIND.values():
        nums = sorted(n for k, n in listed if k == kind)
        gaps = [n for n in range(1, (nums[-1] if nums else 0) + 1) if n not in nums]
        if gaps:
            warn.append(f"the inventory lists {kind} {nums[-1]} but not {kind} {', '.join(map(str, gaps[:8]))} — add what is "
                        f"missing, or say in the coverage log that the paper itself skips the number")

    unconfirmed = []
    meta_path = folder / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        unconfirmed = [p["page"] for p in meta.get("pages", []) if p.get("order_status") == "unconfirmed"]
        log = " ".join(s.text for s in statements if s.section == N.COVERAGE)
        named = set(N.pages_in("[" + " ".join(re.findall(r"p\.?\s*\d+(?:\s*[–-]\s*p?\.?\s*\d+)?", log)).replace(" p", ", p") + "]")) if log else set()
        missing = [p for p in unconfirmed if p not in named]
        if missing:
            err.append("pages whose reading order no second engine confirms must be read on the page render and named in the "
                       "coverage log (section 17): " + ", ".join(f"p{p}" for p in missing))
        hay = N.squash(" ".join(pages.text.values()))
        if "retracted" in hay and "retract" not in N.squash(notes.read_text(encoding="utf-8")):
            err.append("the paper carries the word RETRACTED; the notes do not mention a retraction (header venue, section 15 "
                       "'Publication record')")

    md = folder / "text" / "full.md"
    if md.exists() and found.get(N.DIGEST):
        digest = N.squash(" ".join(s.subsection + " " + s.text for s in statements if s.section == N.DIGEST))
        title = N.squash(str(header.get("title", "")))
        missing = []
        for line in C.read_exact(md).splitlines():
            m = re.match(r"^#{1,4}\s+(.*)$", line)
            if not m:
                continue
            h = re.sub(r"[*_`]", "", m.group(1)).strip()
            key = N.squash(re.sub(r"^[\dIVXivx.\s)-]+", "", h))
            if 6 <= len(key) <= 80 and key not in digest and key not in title and not FRONT_MATTER.match(h):
                missing.append(h[:70])
        for h in dict.fromkeys(missing):
            warn.append(f"heading in the paper not found in section {N.DIGEST}: \"{h}\"")
    result.update({
        "id": header.get("id"), "title": header.get("title"), "pages_total": total, "body_pages": len(body),
        "statements": len(statements), "statements_with_citation": sum(1 for s in statements if s.pages),
        "absence_lines": sum(1 for s in statements if s.absent),
        "image_evidence": sum(1 for s in statements if s.image),
        "quotations_tested": tested, "quotations_failed": failed, "quotations_too_short": short,
        "pages_cited": len(cited_pages), "body_pages_uncited": real, "pages_order_unconfirmed": unconfirmed,
        "statements_per_section": per_section, "passed": not err,
    })
    (folder / "notes" / "check.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("papers", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-warnings", type=int, default=25)
    args = ap.parse_args()
    if args.all:
        done = passed = 0
        for entry in C.load_manifest():
            d = C.folder_of(entry)
            if not (d / "notes" / "NOTES.md").exists():
                continue
            r = check(d)
            done += 1
            passed += r["passed"]
            print(f"{entry['id']}  {'PASS' if r['passed'] else 'FAIL'}  {r.get('statements', 0):4d} statements  "
                  f"{r.get('quotations_tested', 0):4d} quotations  {len(r['errors']):3d} errors  {entry['folder'][:70]}")
        total = len(C.load_manifest())
        print(f"\nnotes written for {done} of {total} papers; {passed} pass, {done - passed} fail")
        return 0 if done == passed else 1
    if not args.papers:
        ap.error("give a paper folder or ID, or --all")
    status = 0
    for a in args.papers:
        r = check(C.resolve(a))
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['folder']}")
        if "statements" in r:
            print(f"  {r['statements']} statements, {r['statements_with_citation']} with a page citation, "
                  f"{r['absence_lines']} absence lines, {r['image_evidence']} read on the page image; "
                  f"{r['quotations_tested']} quotations tested, {r['quotations_failed']} not found, "
                  f"{r['quotations_too_short']} too short to test; {r['pages_cited']} of {r['pages_total']} pages cited")
        for e in r["errors"]:
            print("  ERROR  ", e)
        for w in r["warnings"][:args.max_warnings]:
            print("  warning", w)
        if len(r["warnings"]) > args.max_warnings:
            print(f"  … and {len(r['warnings']) - args.max_warnings} more warnings in notes/check.json")
        status |= not r["passed"]
    return int(status)


if __name__ == "__main__":
    sys.exit(main())
