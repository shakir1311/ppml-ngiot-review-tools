#!/usr/bin/env python3
"""Break the verified full text of a paper into its sections — a step of the extraction pipeline (run_extraction.sh, after
verify_ocr.py and before check_extraction.py).

The author, 12 October 2026: "verify ... 100% correctly extracted full text broken down into sections for each pdf - taking into
account the two column formats of e.g IEEE ... all of this is now baked into our paper extraction pipeline".

Headings are read from the PDF itself. A line is a heading when its words carry a heading's numbering (I., II. … or 1, 2, 2.1 …;
A., B. … under a Roman section) or are a standard heading (Abstract, Introduction, Conclusion, Acknowledgment, References,
Appendix, Declarations …), it is short, it is not a caption, and its type sets it apart from the body text: bold, larger,
capitals or small capitals, or italic for a lettered subsection (the spans PyMuPDF gives for the line). Numbering must run on
within its level: a numbered line out of step is body text (a list item), and a number that is skipped is reported. IEEE's
run-in "Abstract—" and "Index Terms—" open sections of their own; deeper run-in headings ("1) Title:") stay inside their
section. On a page read by OCR, which has no type to read, the numbering and capitals decide.

The text cut is text/full.txt — the reading text the pipeline verified, two columns in column order, with OCR or the consensus
reading where they stand in — so every character of it is in exactly one section (checked), and each section keeps the pages
it runs over. Writes text/sections.json and text/sections.md, and records in metadata.json the sections found, whether the
numbering runs on, whether the cut lost or added anything, and how far the headings agree with the PDF's outline (bookmarks)
where it has one. Prints numbers and verdicts only, never the text of a paper.

    sections.py [--manifest PATH] [--ids ID ...] [--folders DIR ...]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

import corpus as C
import page_text as PT

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII"]
STANDARD = {"abstract", "introduction", "relatedwork", "relatedworks", "background", "preliminaries", "systemmodel",
            "methodology", "methods", "results", "discussion", "conclusion", "conclusions", "conclusionandfuturework",
            "conclusionsandfuturework", "conclusionandfuturedirections", "futurework", "acknowledgment", "acknowledgments",
            "acknowledgement", "acknowledgements", "references", "bibliography", "appendix", "appendices", "declarations",
            "funding", "dataavailability", "dataavailabilitystatement", "authorcontributions", "conflictofinterest",
            "conflictsofinterest", "competinginterests", "declarationofcompetinginterest", "ethicsstatement",
            "ethicsapproval", "creditauthorshipcontributionstatement", "abbreviations", "nomenclature", "keywords",
            "indexterms", "biographies", "authorbiographies"}
CAPTION = re.compile(r"^(table|tab\.|fig\.?|figure|algorithm|listing|scheme|eq\.?|equation|step|note|theorem|lemma|definition|"
                     r"proof|remark|corollary|proposition|example)\b", re.I)
RUN_IN = re.compile(r"^\s*(Abstract|ABSTRACT|Index Terms|INDEX TERMS|Keywords|KEYWORDS|Key words)(?:\s*[—–:\-.]\s*|\s+(?=[A-Z0-9]))")
key = lambda t: re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", t or "").lower())
BOLD_FONT = r"bold|black|heavy|semibold|demi|medi(um)?\b|cmbx|sfbx|lmroman\d*-bold|-bd\b|bd$|,b$|-b$|bx\d"   # CMBX, NimbusRomNo9L-Medi …


def tidy(t: str) -> str:
    """One heading line as printed: spaces closed up, and small capitals ("I. I NTRODUCTION") read as one word."""
    t = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t)).strip()
    return re.sub(r"\b([A-Z]) (?=[A-Z]{2,}\b)", r"\1", t)


def ocr_roman(t: str) -> str:
    """Roman numerals as OCR misreads them at the head of a line ("Il.", "Ill", "lV.") put right."""
    m = re.match(r"^([IlV1|]{1,4})(\.?)\s+([A-Z][A-Z].*)$", t)
    if m:
        r = m.group(1).replace("l", "I").replace("1", "I").replace("|", "I")
        if r in ROMAN:
            return f"{r}. {m.group(3)}"
    return t


def parse(t: str, ocr: bool = False) -> tuple | None:
    """(kind, number, title, level) of a line that has the form of a heading, or None."""
    t = tidy(t)
    if ocr:
        t = ocr_roman(t)
    if not t or len(t.split()) > 18 or CAPTION.match(t) or t.endswith((",", ";")):
        return None
    m = RUN_IN.match(t)
    if m:
        return ("run-in", "", m.group(1).title().replace("Index terms", "Index Terms"), 1)
    m = re.match(r"^([IVXL]{1,5})\.\s+(\S.*)$", t)
    if m and m.group(1) in ROMAN:
        return ("roman", m.group(1), m.group(2), 1)
    m = re.match(r"^([A-Z])\.\s+(\S.*)$", t)
    if m:
        return ("letter", m.group(1), m.group(2), 2)
    m = re.match(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+((?:[^\W\d_]|\d+[^\W\d_]).*)$", t)   # a letter of any script, or 5G, 3D
    if m and not re.search(r"\.\s+\S+\s+\S+\s+\S+.*\.$", m.group(2)):          # not a numbered sentence
        return ("arabic", m.group(1), m.group(2), m.group(1).count(".") + 1)
    m = re.match(r"^(Appendix|APPENDIX)(?:\s+([A-Z0-9]))?\b[.:]?\s*(.*)$", t)
    if m:
        return ("standard", m.group(2) or "", ("Appendix " + (m.group(2) or "")).strip() + (f" {m.group(3)}" if m.group(3) else ""), 1)
    if key(t) in STANDARD:
        return ("standard", "", t, 1)
    m = re.match(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?([A-Z].*)$", t)                 # "1Introduction": no space after the number
    if m and key(m.group(2)) in STANDARD:
        return ("arabic", m.group(1), m.group(2), m.group(1).count(".") + 1)
    return None


def line_styles(page) -> list[dict]:
    """Every text line of a page with its type: dominant size, bold, italic, capitals, small capitals."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            spans = [s for s in ln["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = "".join(s["text"] for s in ln["spans"])
            chars = sum(len(s["text"].strip()) for s in spans)
            size = max(spans, key=lambda s: len(s["text"].strip()))["size"]
            share = lambda test: sum(len(s["text"].strip()) for s in spans if test(s)) / max(1, chars)
            bold = share(lambda s: (s["flags"] & 16) or re.search(BOLD_FONT, s["font"], re.I)) >= 0.6
            italic = share(lambda s: (s["flags"] & 2) or re.search(r"ital|oblique|cmti|slant", s["font"], re.I)) >= 0.6   # "A." upright, title italic
            letters = [c for c in text if c.isalpha()]
            caps = bool(letters) and sum(c.isupper() for c in letters) >= 0.9 * len(letters)
            sizes = {round(s["size"], 1) for s in spans if any(c.isalpha() for c in s["text"])}
            out.append({"text": text, "size": size, "bold": bool(bold), "italic": bool(italic), "caps": caps,
                        "small_caps": caps and len(sizes) > 1, "chars": chars, "bbox": ln["bbox"]})
    return out


def body_size(doc) -> float:
    sizes = collections.Counter()
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for s in ln["spans"]:
                    sizes[round(s["size"], 1)] += len(s["text"].strip())
    return sizes.most_common(1)[0][0] if sizes else 10.0


def styled(st: dict, kind: str, base: float, number: str = "") -> bool:
    larger = st["size"] >= base + 0.6
    if st["size"] < base - 1.0 and not (st["caps"] or st["small_caps"]):
        return False                                   # smaller than the text and not in capitals: a label in a figure
    if kind == "roman" and number in ("I", "V", "X", "L") and st["italic"]:
        return True                                    # perhaps the letter I, V, X or L of a lettered list: the numbering decides
    if kind == "letter" or (kind == "arabic" and st.get("level", 1) >= 2):
        return st["italic"] or st["bold"] or larger
    if kind == "run-in":
        return True
    return st["bold"] or larger or st["caps"] or st["small_caps"]


def style_of(sts: list[dict], kind: str, base: float, level: int, number: str = "") -> tuple[dict | None, bool]:
    """(the PDF line that carries a body line's text, whether it is set as a heading): of several lines with the same text on
    the page (a heading's words repeated in a figure or a table), the first one set as a heading, else the first."""
    for st in sts:
        if styled({**st, "level": level}, kind, base, number):
            return st, True
    return (sts[0], False) if sts else (None, False)


def page_bodies(folder: Path) -> list[tuple[int, str]]:
    """The page bodies of text/full.txt, exactly as written there."""
    full = PT.read_exact(folder / "text" / "full.txt")
    marks = list(C.PAGE_MARKER.finditer(full))
    return [(int(m.group(1)), full[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(full)]) for i, m in enumerate(marks)]


def candidates(folder: Path, doc, meta: dict) -> list[dict]:
    """Heading candidates in reading order: (page, offset in the page body, kind, number, title, level)."""
    pm = {p["page"]: p for p in meta.get("pages", [])}
    base = body_size(doc)
    out = []
    for n, body in page_bodies(folder):
        ocr_page = bool(pm.get(n, {}).get("ocr_stands_in")) or len(PT.read_exact(folder / "text" / "pages" / f"page_{n:04d}.txt").strip()) < 100
        styles = {} if ocr_page else collections.defaultdict(list)
        if not ocr_page:
            for st in line_styles(doc[n - 1]):                       # figure areas are not used: a recorded figure's area
                styles[key(tidy(st["text"]))].append(st)               # may reach over a heading; captions are excluded anyway
        if ocr_page:
            out += tesseract_heads(folder, n, body)
        offset = 0
        lines = body.split("\n")
        for j, line in enumerate(lines):
            nxt = lines[j + 1] if j + 1 < len(lines) else ""
            if re.fullmatch(r"\s*(\d{1,2}(\.\d{1,2}){0,3}\.?|[IVXL]{1,5}\.|[A-Z]\.)\s*", line) and nxt.strip() \
                    and (parse(nxt, ocr_page) or ("standard",))[0] == "standard":   # not a page number in front of a numbered heading
                parsed = parse(line.strip() + " " + nxt.strip(), ocr_page)        # a number set on a line of its own
                if parsed and not ocr_page:
                    if style_of(styles.get(key(tidy(nxt)), []), parsed[0], base, parsed[3])[1]:
                        kind, num, title, level = parsed
                        out.append({"page": n, "offset": offset, "kind": kind, "number": num, "title": tidy(title), "level": level,
                                    "line": len(line)})
                        styles.pop(key(tidy(nxt)), None)          # its text is not a heading again on this page
                elif parsed and ocr_page and parsed[0] in ("roman", "arabic"):
                    out.append({"page": n, "offset": offset, "kind": parsed[0], "number": parsed[1], "title": tidy(parsed[2]),
                                "level": parsed[3], "line": len(line)})
                offset += len(line) + 1
                continue
            parsed = parse(line, ocr_page)
            if not parsed and not ocr_page and tidy(line).endswith((",", ";")):
                wrapped = parse(tidy(line)[:-1], ocr_page)               # a numbered heading wrapped after a comma: kept only
                st, ok = style_of(styles.get(key(tidy(line)), []), wrapped[0], base, wrapped[3], wrapped[1]) if wrapped else (None, False)
                if wrapped and wrapped[0] in ("roman", "letter", "arabic") and ok:
                    on = styles.get(key(tidy(nxt)), [])               # its second line, set in the same type, ends the title
                    whole = parse(tidy(line) + " " + tidy(nxt), ocr_page) if any(
                        (round(o["size"], 1), o["bold"], o["italic"]) == (round(st["size"], 1), st["bold"], st["italic"]) for o in on) else None
                    out.append({"page": n, "offset": offset, "kind": wrapped[0], "number": wrapped[1],
                                "title": tidy((whole or wrapped)[2]), "level": wrapped[3], "line": len(line), "styled": False,
                                "sig": None})                                    # to fill a gap
            if not parsed and not ocr_page and 1 <= len(tidy(line).split()) <= 12 and not CAPTION.match(tidy(line)) \
                    and not tidy(line).endswith((".", ",", ";", ":")) and tidy(line)[:1].isupper():
                st, ok = style_of(styles.get(key(tidy(line)), []), "standard", base, 1)
                if ok:
                    out.append({"page": n, "offset": offset, "kind": "typed", "number": "", "title": tidy(line), "level": 1,
                                "line": len(line), "styled": False,
                                "sig": (round(st["size"], 1), st["bold"], st["italic"], st["caps"] or st["small_caps"])})
            if parsed:
                kind, num, title, level = parsed
                ok, sig = False, None
                if ocr_page:
                    ok = kind in ("roman", "run-in", "standard") or (kind == "arabic" and level == 1 and tidy(title)[:1].isupper())
                else:
                    st, styled_ok = style_of(styles.get(key(tidy(line)), []), kind, base, level, num)
                    if kind == "run-in":
                        ok = True
                    elif st:
                        ok = styled_ok
                        sig = (round(st["size"], 1), st["bold"], st["italic"], st["caps"] or st["small_caps"])
                if ok or sig:
                    out.append({"page": n, "offset": offset, "kind": kind, "number": num, "title": tidy(title), "level": level,
                                "line": len(line), "styled": ok, "sig": sig})
            offset += len(line) + 1
    return out


def tesseract_heads(folder: Path, n: int, body: str) -> list[dict]:
    """Numbered headings that Tesseract reads on an OCR page, placed at the line of the reading text (Vision's) that carries
    the same title (the closest line whose words match at 0.8), so that a heading Vision misread is not lost."""
    import difflib
    f = folder / "text" / "variants" / f"page_{n:04d}.tesseract.txt"
    if not f.exists():
        return []
    lines, offs = body.split("\n"), [0]
    for ln in lines:
        offs.append(offs[-1] + len(ln) + 1)
    out = []
    for t in PT.read_exact(f).split("\n"):
        parsed = parse(t, True)
        if not parsed or parsed[0] not in ("roman", "arabic"):
            continue
        want = key(parsed[2])
        best = max(((difflib.SequenceMatcher(None, want, key(NUM_PREFIX.sub("", ocr_roman(tidy(ln))))).ratio(), j)
                    for j, ln in enumerate(lines) if ln.strip()), default=(0, -1))
        if best[0] >= 0.8:
            out.append({"page": n, "offset": offs[best[1]], "kind": parsed[0], "number": parsed[1], "title": tidy(parsed[2]),
                        "level": parsed[3], "line": len(lines[best[1]]), "from": "tesseract"})
    return out


def dedupe(cands: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in sorted(cands, key=lambda c: (c["page"], c["offset"])):
        k = (c["page"], c["offset"])
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def choose(cands: list[dict]) -> tuple[list[dict], dict]:
    """The reading of the headings with the fewest skipped numbers, then the most headings, among: the lines whose type sets them
    apart; those with the lines of the same type (signature) as headings already accepted at their level; and either with the
    top level kept to the type of the paper's other top-level headings (so that numbered list items set in bold are not taken
    for sections)."""
    styled_only = [c for c in cands if c.get("styled", True)]
    tries = []
    first, v = sequence(styled_only, cands)
    tries.append((first, v))
    sig_of = collections.defaultdict(collections.Counter)
    for h in first:
        if h.get("sig"):
            sig_of[(h["kind"], h["level"])][h["sig"]] += 1
    ref = {k: c.most_common(1)[0][0] for k, c in sig_of.items()}
    widened = [c for c in cands if c.get("styled", True) or (c.get("sig") and ref.get((c["kind"], c["level"])) == c["sig"])]
    tries.append(sequence(widened, cands))
    tops = collections.Counter(h["sig"] for h in first if h["level"] == 1 and h.get("sig") and h["kind"] in ("standard", "roman", "arabic"))
    std = collections.Counter(h["sig"] for h in first if h["kind"] == "standard" and h.get("sig"))
    top_sig = (std or tops).most_common(1)[0][0] if (std or tops) else None
    if top_sig:
        for base_set in (styled_only, widened):
            kept = [c for c in base_set if not (c["level"] == 1 and c["kind"] in ("roman", "arabic") and c.get("sig") and c["sig"] != top_sig)]
            tries.append(sequence(kept, cands))
    heads, verdict = max(tries, key=lambda t: len(t[0]) - 3 * len(t[1]["skipped"]))      # the score of the numbering search
    if verdict["scheme"] == "none":                    # no numbering: lines set exactly like the paper's standard headings
        std = collections.Counter(h["sig"] for h in heads if h["kind"] == "standard" and h.get("sig"))
        if std:
            sig = std.most_common(1)[0][0]
            typed = [c for c in cands if c["kind"] == "typed" and c["sig"] == sig]
            heads = sorted(heads + [{**c, "kind": "standard"} for c in typed], key=lambda c: (c["page"], c["offset"]))
            verdict = {**verdict, "headings_by_type": len(typed)}
    return heads, verdict


def roman_value(r: str) -> int:
    return ROMAN.index(r) + 1 if r in ROMAN else 0


def numeric(c: dict) -> tuple:
    if c["kind"] == "roman":
        return (roman_value(c["number"]),)
    if c["kind"] == "letter":
        return (ord(c["number"]) - 64,)
    if c["kind"] == "arabic":
        return tuple(int(x) for x in c["number"].split("."))
    return ()


def continues(cands: list[dict], i: int) -> bool:
    """Whether a later candidate of the same kind and depth carries the number after cands[i] (the run goes on)."""
    v = numeric(cands[i])
    return any(c["kind"] == cands[i]["kind"] and len(numeric(c)) == len(v) and numeric(c)[:-1] == v[:-1] and numeric(c)[-1] == v[-1] + 1
               for c in cands[i + 1:])


def value(c: dict) -> int:
    return roman_value(c["number"]) if c["kind"] == "roman" else int(c["number"].split(".")[0]) if c["kind"] == "arabic" else 0


def best_chain(tops: list[dict]) -> list[dict]:
    """The run of top-level numbers that scores best: one point a heading, three off for every number skipped (steps of one or
    two only), starting at 1 (or 2, with a skip). A longer run of numbered list items with skips loses to the sections."""
    best: list[tuple[float, int]] = []
    for i, c in enumerate(tops):
        v = value(c)
        score, prev = (1.0 if v == 1 else -2.0 if v == 2 else float("-inf")), -1
        for j in range(i):
            d = v - value(tops[j])
            if d in (1, 2) and best[j][0] > float("-inf"):
                cand = best[j][0] + 1 - (3 if d == 2 else 0)
                if cand > score:
                    score, prev = cand, j
        best.append((score, prev))
    if not best or max(b[0] for b in best) == float("-inf"):
        return []
    i = max(range(len(best)), key=lambda k: best[k][0])
    chain = []
    while i != -1:
        chain.append(tops[i])
        i = best[i][1]
    return chain[::-1]


def sequence(cands: list[dict], pool: list[dict] | None = None) -> tuple[list[dict], dict]:
    """The headings: the best run of top-level numbers (best_chain), subsections in step within their sections, unnumbered
    standard headings; then every gap between two accepted headings that exactly one line of `pool` with the missing number
    fills, by its place, is filled — whatever its type. -> (headings in reading order, verdicts)"""
    cands = [c for c in cands if c["kind"] != "typed"]
    pool = pool if pool is not None else cands
    for i, c in enumerate(pool):
        c["_pos"] = (c["page"], c["offset"])
    romans = sum(1 for c in cands if c["kind"] == "roman")
    arabic = sum(1 for c in cands if c["kind"] == "arabic" and c["level"] == 1)
    scheme = "roman" if romans >= 2 and romans >= arabic else "arabic" if arabic >= 2 else "none"
    top_kind = scheme if scheme != "none" else None
    tops = best_chain([c for c in cands if c["kind"] == top_kind and c["level"] == 1]) if top_kind else []
    top_ids = {id(c) for c in tops}
    keep, out_of_step = [], 0
    top, sub = 0, {}
    for c in sorted(cands, key=lambda c: (c["page"], c["offset"])):
        if c["kind"] in ("run-in", "standard"):
            keep.append(c)
            continue
        if id(c) in top_ids:
            top, sub = value(c), {}
            keep.append(c)
            continue
        if scheme == "roman" and c["kind"] == "roman" and top and len(c["number"]) == 1 \
                and roman_value(c["number"]) <= top and ord(c["number"]) - 64 == sub.get(top, 0) + 1:
            c = {**c, "kind": "letter", "level": 2}            # "I." after "H.": the letter I of a lettered list
        if scheme == "roman" and c["kind"] == "letter" and top:
            v = ord(c["number"]) - 64
            if v == sub.get(top, 0) + 1 or (v == sub.get(top, 0) + 2 and continues(cands, cands.index(c) if c in cands else 0)):
                sub[top] = v
                keep.append(c)
                continue
        elif scheme == "arabic" and c["kind"] == "arabic" and c["level"] >= 2 and top:
            parts = [int(x) for x in c["number"].split(".")]
            parent = tuple(parts[:-1])
            nxt = sub.get(parent, 0) + 1
            if parts[0] == top and (parts[-1] == nxt or (parts[-1] == nxt + 1 and continues(cands, cands.index(c)))) \
                    and (len(parts) == 2 or parent in sub):
                sub[parent] = parts[-1]
                sub[tuple(parts)] = 0
                keep.append(c)
                continue
        out_of_step += 1
    keep = fill_gaps(keep, pool, scheme)
    return keep, {"scheme": scheme, "numbering_runs_on": not skipped(keep, scheme), "skipped": skipped(keep, scheme),
                  "numbered_lines_taken_as_text": out_of_step}


def label(c: dict) -> tuple:
    """(level, parent label, number) of a numbered heading."""
    if c["kind"] == "roman":
        return (1, (), roman_value(c["number"]))
    if c["kind"] == "letter":
        return (2, ("top",), ord(c["number"]) - 64)
    if c["kind"] == "arabic":
        parts = [int(x) for x in c["number"].split(".")]
        return (len(parts), tuple(parts[:-1]), parts[-1])
    return (0, (), 0)


def skipped(heads: list[dict], scheme: str) -> list[str]:
    """The numbers skipped within each run of the headings (top level; subsections within each section)."""
    out, top, last = [], 0, {}
    for h in heads:
        if h["kind"] in ("run-in", "standard"):
            continue
        lvl, parent, v = label(h)
        if lvl == 1:
            if v != top + 1:
                out.append(f"{top + 1}..{v}" if h["kind"] == "arabic" else f"{ROMAN[top] if top < len(ROMAN) else top + 1}..{h['number']}")
            top, last = v, {}
        else:
            k = (top, parent)
            if v != last.get(k, 0) + 1:
                out.append(f"{'.'.join(map(str, parent)) if h['kind'] == 'arabic' else ROMAN[top - 1] if top else '?'}.{last.get(k, 0) + 1}..{h['number']}")
            last[k] = v
    return out


def fill_gaps(heads: list[dict], pool: list[dict], scheme: str) -> list[dict]:
    """Fill each skipped number with the one line of the pool that carries it between the two headings around the gap."""
    heads = sorted(heads, key=lambda c: (c["page"], c["offset"]))
    taken = {(c["page"], c["offset"]) for c in heads}
    changed = True
    while changed:
        changed = False
        nums = [h for h in heads if h["kind"] not in ("run-in", "standard")]
        for i, h in enumerate(nums):
            lvl, parent, v = label(h)
            prev = next((p for p in reversed(nums[:i]) if label(p)[0] == lvl and (lvl == 1 or label(p)[1] == parent)), None)
            lo = (prev["page"], prev["offset"]) if prev else (0, -1)
            if lvl > 1:                                        # within the same section
                head = next((p for p in reversed(nums[:i]) if label(p)[0] < lvl), None)
                lo = max(lo, (head["page"], head["offset"])) if head else lo
            want = (label(prev)[2] if prev and (lvl == 1 or (head and prev["_pos"] > head["_pos"])) else 0) + 1
            if v <= want:
                continue
            fits = [c for c in pool if (c["page"], c["offset"]) not in taken and lo < (c["page"], c["offset"]) < (h["page"], h["offset"])
                    and label({**c, "kind": "letter" if (h["kind"] == "letter" and c["kind"] == "roman" and len(c["number"]) == 1) else c["kind"]})
                    == (lvl, parent if h["kind"] == "arabic" else label(h)[1], want)
                    and (c["kind"] == h["kind"] or (h["kind"] == "letter" and c["kind"] == "roman"))]
            if len(fits) == 1:
                c = {**fits[0], "kind": h["kind"], "level": h["level"]}
                heads.append(c)
                taken.add((c["page"], c["offset"]))
                heads.sort(key=lambda c: (c["page"], c["offset"]))
                changed = True
                break
    return heads


def sub_keys(sub: dict) -> set:
    return {k for k in sub if isinstance(k, tuple)}


def split(folder: Path, heads: list[dict]) -> tuple[list[dict], bool]:
    """Cut the page bodies at the headings (in reading order); every character lands in exactly one section.
    -> (sections, lossless)"""
    bodies = page_bodies(folder)
    sections = [{"number": "", "title": "Front matter", "level": 0, "kind": "front", "chunks": []}]
    sections += [{"number": h["number"], "title": h["title"], "level": h["level"], "kind": h["kind"], "chunks": []} for h in heads]
    cuts = collections.defaultdict(list)
    for i, h in enumerate(heads):
        cuts[h["page"]].append((h["offset"], i + 1))
    cur = 0
    for n, body in bodies:
        pos = 0
        for off, idx in sorted(cuts[n]):
            if body[pos:off]:
                sections[cur]["chunks"].append({"page": n, "text": body[pos:off]})
            pos, cur = off, idx
        if body[pos:]:
            sections[cur]["chunks"].append({"page": n, "text": body[pos:]})
    lossless = "".join(c["text"] for s in sections for c in s["chunks"]) == "".join(b for _, b in bodies)
    sections = [s for s in sections if s["chunks"] or s["kind"] != "front"]
    for s in sections:
        pages = [c["page"] for c in s["chunks"]]
        s["pages"] = [min(pages), max(pages)] if pages else []
    return sections, lossless


def outline_agreement(doc, heads: list[dict]) -> dict:
    toc = [(lvl, t) for lvl, t, _ in doc.get_toc(simple=True) if lvl <= 3 and key(t)]
    if not toc:
        return {"outline_entries": 0}
    found = {key(f"{h['number']} {h['title']}") for h in heads} | {key(h["title"]) for h in heads}
    strip_num = lambda t: re.sub(r"^\s*([IVXL]+\.|[A-Z]\.|\d+(\.\d+)*\.?)\s+", "", t)
    matched = sum(1 for _, t in toc if key(t) in found or key(strip_num(t)) in found)
    return {"outline_entries": len(toc), "outline_matched": matched}


NUM_PREFIX = re.compile(r"^\s*((?:[IVXL]{1,5}|[A-Z]|\d{1,2}(?:\.\d{1,2}){0,3})[.)]?)\s+")


def inline_heading(body: str, want: list[str], after: int) -> int | None:
    """Where a heading begins inside a line of a page body: a reading that runs a heading into a line (PDFKit's, where it stands in
    for a page) still holds it, with its letters in order. Found only where it begins a sentence — at a line's start, after a
    full stop, colon or section number — with a capital or a digit, and is ten letters or more. -> its offset in the body."""
    flat, where = [], []
    for i, ch in enumerate(body):
        for c in key(ch):
            flat.append(c)
            where.append(i)
    flat = "".join(flat)
    for w in (w for w in want if len(w) >= 10):
        start = 0
        while (k := flat.find(w, start)) >= 0:
            start = k + 1
            i = where[k]
            if i <= after or not (body[i].isupper() or body[i].isdigit()):
                continue
            j = i - 1
            while j >= 0 and body[j] in " \t":
                j -= 1
            if j < 0 or body[j] in "\n.:?!":
                return i
            t0 = j                                         # a section number ("3.2", "IV.") just before the heading
            while t0 > 0 and not body[t0 - 1].isspace():
                t0 -= 1
            if re.fullmatch(r"(?:[IVXL]{1,5}|\d{1,2}(?:\.\d{1,2}){0,3})[.)]?", body[t0:j + 1]):
                j = t0 - 1
                while j >= 0 and body[j] in " \t":
                    j -= 1
                if j < 0 or body[j] in "\n.:?!":
                    return t0                              # the cut goes before the number
    return None


def okey(t: str) -> str:
    """An outline title or a line, for matching one with the other: "&" read as "and", then letters and digits only."""
    return key(re.sub(r"\s*&\s*", " and ", t or ""))


def like(line: str, wanted: set) -> bool:
    """A line (or lines joined) that is the heading an outline entry names: the same letters; or, for a title of fifteen letters
    or more, at least 90 % alike (a word or a mark printed otherwise than the outline gives it); or, for a title of thirty
    letters or more, the same first thirty letters."""
    import difflib
    if not line:
        return False
    for w in wanted:
        if line == w:
            return True
        if len(w) >= 15 and 0.75 * len(w) <= len(line) <= 1.3 * len(w) and difflib.SequenceMatcher(None, line, w).ratio() >= 0.9:
            return True
        if len(w) >= 30 and len(line) >= 30 and line[:30] == w[:30]:
            return True
    return False


def run_in(body: str, line_start: int, line: str, wanted: set) -> bool:
    """A short heading run into the start of its line: "Model. The …" — its letters, then a full stop, colon or dash."""
    for w in wanted:
        if 4 <= len(w) < 10:
            flat, where = [], []
            for i, ch in enumerate(line):
                for c in okey(ch):
                    flat.append(c)
                    where.append(i)
            if "".join(flat).startswith(w) and len(where) >= len(w):
                rest = line[where[len(w) - 1] + 1:].lstrip()
                if rest[:1] in (".", ":", "—", "–") or (rest[:1] == "-" and rest[1:2] == " "):
                    return True
    return False


def outline_heads(folder: Path, doc) -> tuple[list[dict], dict] | None:
    """The headings from the PDF's own outline (bookmarks), each found, in order, as a whole line — or a heading wrapped over two
    or three lines, its number perhaps on a line of its own — on its page of the verified text (or the next page); failing
    that, run into a line where it begins a sentence (inline_heading).
    -> (headings, verdict), or None when the PDF has no usable outline."""
    toc = [(lvl, t.strip(), pg) for lvl, t, pg in doc.get_toc(simple=True) if lvl <= 3 and key(t) and pg >= 1]
    if len(toc) < 3:
        return None
    top = min(lvl for lvl, _, _ in toc)
    bodies = dict(page_bodies(folder))
    heads, missing, not_printed, captions, last = [], [], [], [], (0, -1)
    whole = okey(" ".join(b for _, b in sorted(bodies.items())))
    if toc[0][2] == 1 and len(toc[0][1].split()) >= 6 and 1 in bodies:  # the article's title: the top of the paper, wherever else it is
        heads.append({"page": 1, "offset": 0, "kind": "outline", "number": "", "title": tidy(toc[0][1]),
                      "level": toc[0][0] - top + 1, "line": 0})         # repeated (a citation line, a running head)
        toc_rest = list(enumerate(toc))[1:]
    else:
        toc_rest = list(enumerate(toc))
    def first(near: tuple, test) -> tuple | None:
        """The first line after the last heading found, on the pages named in turn, that passes the test."""
        for n in near:
            if n not in bodies or (n, 10 ** 9) < last:
                continue
            lines = bodies[n].split("\n")
            offs = [0]
            for ln in lines:
                offs.append(offs[-1] + len(ln) + 1)
            for j in range(len(lines)):
                if (n, offs[j]) > last and test(n, lines, j, offs):
                    return (n, offs[j])
        return None

    for i, (lvl, title, pg) in toc_rest:
        want = {okey(title), okey(NUM_PREFIX.sub("", title))} - {""}
        spans = lambda lines, j: (tidy(" ".join(lines[j:j + k])) for k in (1, 2, 3, 4, 5))
        exact = lambda n, lines, j, offs: (okey(lines[j]).startswith(tuple(w for w in want if w in ("abstract", "keywords", "indexterms")))
                                           or any(okey(t) in want or okey(NUM_PREFIX.sub("", t)) in want for t in spans(lines, j)))
        near_ = lambda n, lines, j, offs: any(like(okey(t), want) or like(okey(NUM_PREFIX.sub("", t)), want) for t in spans(lines, j))
        runin = lambda n, lines, j, offs: run_in(bodies[n], offs[j], lines[j], want)
        here = (pg, pg + 1, pg - 1)
        hit = first(here, exact) or first(here, near_) or first(here, runin)       # the strictest test first, then looser ones
        if not hit:                                    # not a line of its own: run into a line by the reading that stands in
            for n in here:
                if n not in bodies or (n, 10 ** 9) < last:
                    continue
                off = inline_heading(bodies[n], [key(title), key(NUM_PREFIX.sub("", title))], last[1] if last[0] == n else -1)
                if off is not None:
                    hit = (n, off)
                    break
        if not hit:
            hit = first((pg + 2,), exact)                # the outline's page number two short
        if hit:
            m = NUM_PREFIX.match(title)
            heads.append({"page": hit[0], "offset": hit[1], "kind": "outline", "number": m.group(1).rstrip(".)") if m else "",
                          "title": tidy(NUM_PREFIX.sub("", title)) if m else tidy(title), "level": lvl - top + 1, "line": 0})
            last = hit
        elif CAPTION.match(tidy(title)):
            captions.append(i + 1)                    # a table's or figure's title the outline lists out of order: not a section
        elif not any(w[:20] in whole for w in want if len(w) >= 4):
            not_printed.append(i + 1)                 # the outline names a part this PDF does not print: nothing to find
        else:
            missing.append(i + 1)
    if missing and missing[0] == 1 and toc[0][2] == 1:
        missing = missing[1:]                          # the article's title, set over several lines: front matter, not a section
    if len(heads) < 0.6 * len(toc):
        return None
    tops = [h for h in heads if h["level"] == 1]
    if len(tops) == 1 and heads and heads[0] is tops[0] and len(heads) > 1:
        heads[0]["level"] = 0                          # the article's title: the sections are one level up
        for h in heads[1:]:
            h["level"] = max(1, h["level"] - 1)
    return heads, {"scheme": "outline", "numbering_runs_on": not missing, "skipped": [f"outline entry {i} not found" for i in missing],
                   "numbered_lines_taken_as_text": 0, "outline_entries_found": f"{len(heads)}/{len(toc)}",
                   "outline_entries_not_printed": not_printed, "outline_captions_set_aside": captions}


def process(folder: Path) -> dict:
    meta_path = folder / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    doc = pymupdf.open(C.pdf_of(folder))
    found = outline_heads(folder, doc)
    typed = None
    if not found or not found[1]["numbering_runs_on"]:          # the outline is missing or skips: the type and numbering too
        typed = choose(dedupe(candidates(folder, doc, meta)))
    use_outline = found is not None and (found[1]["numbering_runs_on"] or not typed[1]["numbering_runs_on"])
    if use_outline and typed and not found[1]["numbering_runs_on"] and len(typed[1]["skipped"]) < len(found[1]["skipped"]):
        use_outline = False                                     # neither runs on: the one that skips less
    heads, verdict = found if use_outline else typed
    sections, lossless = split(folder, heads)
    titles = {key(h["title"]) for h in heads}
    standard = {k: any(k in t for t in titles) for k in ("abstract", "introduction", "conclusion", "references")}
    out = {"source": "text/full.txt", "mode": "outline" if use_outline else "type and numbering", "scheme": verdict["scheme"],
           "numbering_runs_on": verdict["numbering_runs_on"],
           "skipped_numbers": verdict["skipped"], "numbered_lines_taken_as_text": verdict["numbered_lines_taken_as_text"],
           "lossless": lossless, "standard_sections": standard, **outline_agreement(doc, heads),
           **{k: verdict[k] for k in ("outline_entries_not_printed", "outline_captions_set_aside") if verdict.get(k)},
           "sections": [{"number": s["number"], "title": s["title"], "level": s["level"], "pages": s["pages"], "chunks": s["chunks"]}
                        for s in sections]}
    PT.write_atomic(folder / "text" / "sections.json", json.dumps(out, indent=1, ensure_ascii=False))
    md = []
    for s in sections:
        head = (f"{s['number']}. " if s["kind"] in ("roman", "letter") else f"{s['number']} " if s["number"] else "") + s["title"]
        if s["kind"] == "front":
            head = "Front matter"
        pages = f"p. {s['pages'][0]}" if s["pages"] and s["pages"][0] == s["pages"][1] else f"pp. {s['pages'][0]}–{s['pages'][1]}" if s["pages"] else ""
        md.append(f"{'#' * min(6, max(1, s['level'] + 1))} {head}  ({pages})\n")
        for c in s["chunks"]:
            md.append(f"[p. {c['page']}]\n{c['text'].strip()}\n")
    PT.write_atomic(folder / "text" / "sections.md", "\n".join(md) + "\n")
    summary = {k: out[k] for k in ("mode", "scheme", "numbering_runs_on", "skipped_numbers", "numbered_lines_taken_as_text", "lossless",
                                   "standard_sections", "outline_entries") if k in out}
    summary.update({"outline_matched": out.get("outline_matched"), "sections": len(sections),
                    "top_level": sum(1 for s in sections if s["level"] == 1), "subsections": sum(1 for s in sections if s["level"] >= 2)})
    meta["sections"] = summary
    PT.write_atomic(meta_path, json.dumps(meta, indent=2, ensure_ascii=False))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--folders", nargs="*", type=Path)
    args = ap.parse_args()
    folders = [f.resolve() for f in args.folders or []]
    if not folders:
        papers = C.load_manifest(args.manifest)
        if args.ids:
            wanted = {i.upper() for i in args.ids}
            papers = [p for p in papers if p["id"].upper() in wanted]
        folders = [C.folder_of(p) for p in papers]
    bad = 0
    for f in folders:
        try:
            s = process(f)
        except Exception as exc:  # noqa: BLE001 - one paper must not stop the others
            print(f"{f.name}: ERROR {type(exc).__name__}: {exc}")
            bad += 1
            continue
        flag = (not s["lossless"]) or (not s["numbering_runs_on"])
        bad += flag
        print(f"{f.name}: {s['sections']} sections ({s['top_level']} top level, {s['subsections']} sub); numbering {s['scheme']}, "
              f"runs on {s['numbering_runs_on']}{' (skipped ' + ', '.join(s['skipped_numbers']) + ')' if s['skipped_numbers'] else ''}; "
              f"lossless {s['lossless']}; standard {''.join(k[0].upper() if v else '-' for k, v in s['standard_sections'].items())}; "
              f"outline {s.get('outline_matched')}/{s.get('outline_entries')}")
    print(f"{'PASS' if not bad else 'CHECK'}: {len(folders)} papers; {bad} with a section numbering that skips or a cut that is not lossless")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
