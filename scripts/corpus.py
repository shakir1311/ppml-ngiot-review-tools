#!/usr/bin/env python3
"""Shared helpers for the extraction mechanism: where the corpus is, which PDFs are in scope,
which folder belongs to a paper, and the manifest that gives every paper a stable ID.

Layout assumed (nothing else is assumed about folder depth or naming):

    <workspace>/corpus/<corpus-name>/.../<Paper>/<Paper>.pdf      one folder per paper
    <workspace>/corpus/_extraction/MANIFEST.json                  the manifest
    <workspace>/scripts/exclude.txt                               paths left out of scope
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
CORPUS = ROOT / "corpus"
OUT = CORPUS / "_extraction"
MANIFEST = OUT / "MANIFEST.json"
EXCLUDED = OUT / "EXCLUDED.json"          # papers taken out of the corpus: their IDs are never given again
EXCLUDE_FILE = SCRIPTS / "exclude.txt"
PREFIX = {"surveycorpus": "S", "newcorpus": "N", "oldcorpus": "O", "supervisorcorpus": "V"}
PAGE_MARKER = re.compile(r"=+ \[ PAGE (\d+) / (\d+)[^\]]*\] =+")


def read_exact(path: Path) -> str:
    """The text of a file exactly as written, without the translation of carriage returns that Python does by default."""
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        return fh.read()


def safe_stem(name: str) -> str:
    """Same rule as extract_paper.py: a folder name that still reads like the paper title."""
    cleaned = name.replace("/", "-").replace(":", " -").strip()
    return cleaned.rstrip(". ") or "paper"


def exclusions() -> list[str]:
    if not EXCLUDE_FILE.exists():
        return []
    return [l.strip().strip("/") for l in EXCLUDE_FILE.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def is_excluded(path: Path, rules: list[str] | None = None) -> bool:
    rel = path.relative_to(CORPUS).as_posix()
    parts = set(path.relative_to(CORPUS).parts)
    for rule in (exclusions() if rules is None else rules):
        if "/" in rule:
            if rel == rule or rel.startswith(rule + "/"):
                return True
        elif rule in parts:
            return True
    return False


def find_pdfs() -> list[Path]:
    """Every in-scope PDF under corpus/, sorted by path."""
    rules = exclusions()
    out = []
    for p in CORPUS.rglob("*.pdf"):
        if p.name.startswith("._") or OUT in p.parents or is_excluded(p, rules):
            continue
        out.append(p)
    return sorted(out, key=lambda p: p.as_posix().lower())


def paper_dir(pdf: Path) -> Path:
    """The folder that holds a paper and everything extracted from it."""
    return pdf.parent if pdf.parent.name == safe_stem(pdf.stem) else pdf.parent / safe_stem(pdf.stem)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path | str | None = None) -> list[dict]:
    """The papers of the corpus manifest, or of another manifest of the same form (e.g. a set of downloaded reports filed
    under corpus/, such as corpus/ppmlcorpus/check-szk/MANIFEST-S-ZK.json)."""
    m = Path(path) if path else MANIFEST
    return json.loads(m.read_text(encoding="utf-8"))["papers"] if m.exists() else []


def save_manifest(papers: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"root": "corpus", "count": len(papers), "papers": papers}, indent=1, ensure_ascii=False),
                        encoding="utf-8")


def load_excluded() -> list[dict]:
    return json.loads(EXCLUDED.read_text(encoding="utf-8"))["papers"] if EXCLUDED.exists() else []


def by_id(pid: str) -> dict:
    for p in load_manifest():
        if p["id"].lower() == pid.lower():
            return p
    raise SystemExit(f"no paper with id {pid!r} in {MANIFEST}")


def folder_of(entry: dict) -> Path:
    return CORPUS / entry["folder"]


def entry_of(folder: Path) -> dict | None:
    """The manifest entry of a paper folder, or None when the folder is not in the manifest."""
    folder = folder.resolve()
    for p in load_manifest():
        if folder_of(p).resolve() == folder:
            return p
    return None


def resolve(arg: str) -> Path:
    """A paper folder given as a path or as a paper ID (S007)."""
    p = Path(arg)
    if p.is_dir():
        return p.resolve()
    return folder_of(by_id(arg))


def pdf_of(folder: Path) -> Path:
    """The paper itself: the PDF named in the manifest, else the only PDF in the folder."""
    entry = entry_of(folder)
    if entry and (folder / entry["pdf"]).exists():
        return folder / entry["pdf"]
    pdfs = [f for f in sorted(folder.glob("*.pdf")) if not f.name.startswith("._")]
    if not pdfs:
        raise SystemExit(f"no PDF in {folder}")
    return pdfs[0]


def page_versions(folder: Path) -> dict[int, list[str]]:
    """Page number -> every version of that page's text: the reading text, the other engines' readings
    (text/variants/), and the OCR text. A quotation is on a page when it is in any of them."""
    versions: dict[int, list[str]] = {n: [t] for n, t in page_texts(folder).items()}
    for sub in ("variants", "pages_ocr"):
        d = folder / "text" / sub
        for f in sorted(d.glob("page_*.txt")) if d.is_dir() else []:
            n = int(re.search(r"page_(\d+)", f.name).group(1))
            versions.setdefault(n, []).append(read_exact(f))
    return versions


def page_texts(folder: Path) -> dict[int, str]:
    """Page number -> text of that page, from text/pages/ (OCR text where a page had no text layer)."""
    pages: dict[int, str] = {}
    for f in sorted((folder / "text" / "pages").glob("page_*.txt")):
        pages[int(re.search(r"(\d+)", f.stem).group(1))] = read_exact(f)
    for f in sorted((folder / "text" / "pages_ocr").glob("page_*.txt")) if (folder / "text" / "pages_ocr").is_dir() else []:
        n = int(re.search(r"(\d+)", f.stem).group(1))
        if len(pages.get(n, "").strip()) < 100:
            pages[n] = read_exact(f)
    return pages
