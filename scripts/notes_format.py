#!/usr/bin/env python3
"""Parser for notes/NOTES.md as defined in NOTES-PROTOCOL.md: header, sections, statements, page citations, quotations."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

TEMPLATE = 2
SECTIONS = {
    1: "What the paper is about", 2: "The issue it addresses",
    3: "Aims, questions and contributions stated by the authors", 4: "Approach and method",
    5: "Section-by-section digest", 6: "Topic facets", 7: "Results and findings",
    8: "Limitations stated by the authors", 9: "Future directions stated by the authors",
    10: "Open issues and challenges identified for the field",
    11: "Inventory of figures, tables, algorithms and equations", 12: "Definitions, taxonomies and terminology",
    13: "Positioning and key sources", 14: "Theme", 15: "Rigour and reporting", 16: "Reader's observations",
    17: "Coverage log",
}
DIGEST, FACET_SECTION, INVENTORY, RIGOUR_SECTION, OBSERVATIONS, COVERAGE = 5, 6, 11, 15, 16, 17
FACETS = {
    "6.1": "Setting: IoT, edge and network", "6.2": "Learning approach", "6.3": "Privacy mechanisms",
    "6.4": "Trust, blockchain and ledger", "6.5": "Threats, attacks and adversary model",
    "6.6": "Defences, verification and robustness", "6.7": "Cost and performance", "6.8": "Evaluation evidence",
    "6.9": "Regulation, standards and ethics", "6.10": "Other topics the paper treats",
}
RIGOUR = ["Aims or questions", "Method description", "Evaluation type", "Baselines and comparison", "Data",
          "Code and artefacts", "Statistical treatment", "Validity and limitations", "Ethics and consent",
          "Funding and interests", "Publication record"]
HEADER_FIELDS = ["template", "id", "source", "title", "authors", "year", "venue", "doi", "publication_type",
                 "document_type", "research_type", "evaluation_type", "pages_total", "body_pages", "references_pages",
                 "theme_primary", "themes_secondary", "codes"]
CHOICES = {
    "publication_type": ["journal article", "conference paper", "workshop paper", "magazine article", "preprint",
                         "book or book chapter", "thesis", "technical report or white paper",
                         "standard, regulation or guideline"],
    "document_type": ["survey", "systematic review", "tutorial", "primary research — system or scheme",
                      "primary research — empirical study", "position or magazine article", "standard or guideline"],
    "research_type": ["secondary study", "solution proposal", "validation research", "evaluation research",
                      "experience report", "conceptual or philosophical paper", "opinion or position paper",
                      "normative document"],
    "evaluation_type": ["none", "formal proof", "security analysis", "informal argument", "complexity or cost analysis",
                        "simulation", "emulation", "experiment on datasets", "prototype or testbed",
                        "real deployment or field study", "measurement of real systems",
                        "testing of real devices or software", "user study", "case study", "literature synthesis"],
}
QUOTE_REQUIRED = {1, 2, 3, 8, 9, 10, 14}
CITE = re.compile(r"\[\s*p\.?\s*\d+[^\]]*\]")
QUOTE = re.compile(r'"([^"\n]{3,}?)"|“([^”\n]{3,}?)”')
LABEL = re.compile(r"^\s*([A-Za-z][^:\[\]\"“”]{1,70}?):\s")
ABSENT = re.compile(r"^\s*(?:[A-Za-z][^:\[\]\"“”]{1,70}?:\s+)?"
                    r"(not addressed|not covered|not stated|not applicable|not reported|none stated|none\b|"
                    r"no (?:figures?|tables?|algorithms?|equations?|listings?|appendix|appendices|definitions?|"
                    r"taxonom(?:y|ies))\b)", re.I)
IMAGE = re.compile(r"\[\s*p\.?\s*\d+[^\]]*\b(?:image|render)\b[^\]]*\]", re.I)
OMISSION = re.compile(r"\s*(?:…|\.\.\.|\[…\]|\[\.\.\.\])\s*")
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


@dataclass
class Statement:
    section: int
    subsection: str
    line: int
    text: str
    pages: list[int] = field(default_factory=list)
    quotes: list[tuple[str, list[int]]] = field(default_factory=list)   # (quotation, pages of the citation before it)
    absent: bool = False
    image: bool = False      # a citation of the page image, [p6, image]
    image_only: bool = False  # every citation is of the page image: there is no text to quote
    label: str = ""          # the words before the first colon, e.g. "Code and artefacts"

    @property
    def facet(self) -> str:
        return self.subsection.split()[0] if self.section == FACET_SECTION and self.subsection else ""


def pages_in(citation: str) -> list[int]:
    """'[p7–9, p12]' -> [7, 8, 9, 12]"""
    out: list[int] = []
    body = citation.strip("[]")
    for part in re.split(r"[,;]", body):
        nums = [int(n) for n in re.findall(r"\d+", part)]
        if not nums:
            continue
        if len(nums) >= 2 and re.search(r"\d\s*[–—-]\s*p?\.?\s*\d", part) and nums[0] <= nums[1] <= nums[0] + 60:
            out.extend(range(nums[0], nums[1] + 1))
        else:
            out.extend(nums)
    return out


def parse_range(value: str) -> list[int]:
    if not value or str(value).strip().lower() in ("none", "n/a", "-", ""):
        return []
    return pages_in("[" + re.sub(r"(?<![\dp])(\d)", r"p\1", str(value), count=1) + "]")


def squash(text: str) -> str:
    """Lower-case letters and digits only: case, punctuation, spacing, hyphenation and ligatures are ignored."""
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("­", "")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text).replace("­", "")
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.findall(r"[a-z0-9]+", text.lower())


def fragments(quotation: str) -> list[str]:
    """The parts of a quotation on either side of an omission mark; each part is tested on its own."""
    return [f for f in OMISSION.split(quotation) if f.strip()]


def number_of(token: str) -> int | None:
    """'12' -> 12, 'IV' -> 4; None when the token is neither."""
    if token.isdigit():
        return int(token)
    if not token or any(c not in ROMAN for c in token):
        return None
    total = 0
    for c, nxt in zip(token, token[1:] + " "):
        v = ROMAN[c]
        total += -v if nxt in ROMAN and ROMAN[nxt] > v else v
    return total


def as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").split(";") if v.strip()]


def parse_header(text: str) -> tuple[dict, int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 0
    head: dict = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return head, i + 1
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("["):
            try:
                head[key] = json.loads(val)
            except json.JSONDecodeError:
                head[key] = [v.strip().strip("\"'") for v in val.strip("[]").split(",") if v.strip()]
        else:
            head[key] = val.strip().strip('"').strip("'")
    return head, 0


def headings(path: Path) -> dict[int, str]:
    """Section number -> heading as written in the notes."""
    out: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(\d+)\.\s+(.*)$", line.rstrip())
        if m:
            out[int(m.group(1))] = m.group(2).strip()
    return out


def parse(path: Path) -> tuple[dict, list[Statement], dict[int, int], list[str]]:
    """-> header, statements, {section number: line of its heading}, structural problems"""
    text = path.read_text(encoding="utf-8")
    header, start = parse_header(text)
    problems: list[str] = []
    if not header:
        problems.append("no header block (--- … ---) at the top of the file")
    lines = text.splitlines()
    section, sub = 0, ""
    found: dict[int, int] = {}
    statements: list[Statement] = []
    current: Statement | None = None
    for no, raw in enumerate(lines[start:], start=start + 1):
        line = raw.rstrip()
        m = re.match(r"^##\s+(\d+)\.\s+(.*)$", line)
        if m:
            section, sub, current = int(m.group(1)), "", None
            found[section] = no
            continue
        if line.startswith("### "):
            sub, current = line[4:].strip(), None
            continue
        if line.startswith("# ") or not section:
            current = None
            continue
        if re.match(r"^\s*[-*]\s+", line):
            current = Statement(section, sub, no, re.sub(r"^\s*[-*]\s+", "", line))
            statements.append(current)
        elif current is not None and line.strip() and raw.startswith((" ", "\t")):
            current.text += " " + line.strip()
        else:
            current = None
    for s in statements:
        s.absent = bool(ABSENT.match(s.text))
        s.image = bool(IMAGE.search(s.text))
        s.image_only = s.image and len(IMAGE.findall(s.text)) == len(CITE.findall(s.text))
        m = LABEL.match(s.text)
        s.label = m.group(1).strip() if m else ""
        cites = [(m.start(), pages_in(m.group(0))) for m in CITE.finditer(s.text)]
        s.pages = sorted({p for _, ps in cites for p in ps})
        for q in QUOTE.finditer(s.text):
            before = [ps for pos, ps in cites if pos < q.start()]
            after = [ps for pos, ps in cites if pos > q.start()]
            s.quotes.append(((q.group(1) or q.group(2)).strip(), before[-1] if before else (after[0] if after else [])))
    for n in SECTIONS:
        if n not in found:
            problems.append(f"section {n} ({SECTIONS[n]}) is missing")
    for n in found:
        if n not in SECTIONS:
            problems.append(f"section {n} is not in the template (the template has sections 1 to {max(SECTIONS)})")
    order = [n for n, _ in sorted(found.items(), key=lambda kv: kv[1])]
    if order != sorted(order):
        problems.append("sections are out of order")
    subs = {s.facet for s in statements if s.facet}
    for f in FACETS:
        if f not in subs:
            problems.append(f"facet {f} ({FACETS[f]}) has no statement (write a 'Not addressed' line if the paper is silent)")
    labels = {squash(s.label) for s in statements if s.section == RIGOUR_SECTION}
    for item in RIGOUR:
        if squash(item) not in labels:
            problems.append(f"section {RIGOUR_SECTION} has no bullet that starts with '{item}:'")
    return header, statements, found, problems
