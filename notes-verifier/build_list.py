#!/usr/bin/env python3
"""Build the Notes Verifier's paper list: every work cited in the newest version of the PPML review, with its reference
number as printed, and where its PDF, notes and summary are.

    notes-verifier/.venv/bin/python notes-verifier/build_list.py        (run.sh does this when data/papers.json is missing)

Reads only the paper's own files (the bibliography file it is built from and the newest .docx for the numbering) and the
corpus index — never a paper. Writes notes-verifier/data/papers.json. The PDF named for a study is its highlighted copy
(corpus/ppmlcorpus/highlighted/INDEX.csv) where one exists, else the PDF in the study's folder.
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REFS = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json'
PAPER_DIR = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
INDEX = ROOT / 'search-ppml' / 'CORPUS-INDEX-2026-10-04.csv'
PUBLISHED = ROOT / 'search-ppml' / 'evidence' / 'PUBLISHED-VERSIONS.json'
HIGHLIGHTED = ROOT / 'corpus' / 'ppmlcorpus' / 'highlighted' / 'INDEX.csv'      # the highlighted copies (15 Oct 2026)
OUT = HERE / 'data' / 'papers.json'


def newest_version():
    versions = []
    for f in PAPER_DIR.glob('Privacy Preserving Machine Learning in NextGeneration IoT - V*.docx'):
        m = re.search(r' - V(\d+)\.docx$', f.name)
        if m:
            versions.append((int(m.group(1)), f))
    if not versions:
        sys.exit(f'No paper version found in {PAPER_DIR}')
    return max(versions)


def reference_numbers(docx):
    text = subprocess.run(['pandoc', '--sandbox', '-t', 'plain', '--wrap=none', str(docx)],
                          capture_output=True, text=True, check=True).stdout
    text = text[text.rfind('\nReferences\n'):]
    numbers = {}
    for n, entry in re.findall(r'^\[(\d+)\] (.+)$', text, flags=re.M):
        m = re.search(r'doi: (\S+?)\.?$', entry)
        if m:
            numbers[m.group(1).lower()] = int(n)
        elif 'General Data Protection Regulation' in entry:
            numbers['gdpr2016'] = int(n)
        elif 'Guidelines 02/2025' in entry:
            numbers['edpb2026'] = int(n)
    return numbers


def label(ieee):
    """'Ferrag et al. (2023) — Edge Learning for 6G-Enabled …' from an IEEE-style reference."""
    m = re.match(r'(.+?),\s*“(.+?),?”', ieee)
    if not m:
        return ieee[:90]
    authors, title = m.groups()
    first = re.sub(r'\s+(and\s+.*|et al\.?)$', '', authors.split(',')[0].strip())
    surname = first.split()[-1] if first.split() else first
    years = re.findall(r'\b((?:19|20)\d{2})\b', ieee)
    etal = ' et al.' if (',' in authors or ' and ' in authors or 'et al' in authors) else ''
    return f'{surname}{etal} ({years[-1] if years else "n.d."}) — {title.rstrip(",")}'


def main():
    version, docx = newest_version()
    numbers = reference_numbers(docx)
    refs = json.loads(REFS.read_text())
    index = {row['id']: row for row in csv.DictReader(INDEX.open())}
    published = {k: v for k, v in json.loads(PUBLISHED.read_text()).items() if k != 'about'}
    highlighted = ({r['corpus_id']: r['pdf'] for r in csv.DictReader(HIGHLIGHTED.open(encoding='utf-8'))}
                   if HIGHLIGHTED.exists() else {})

    papers = []
    for key, ref in refs.items():
        if ref.get('corpus_id') in published:                 # the version cited (and its re-anchored notes)
            folder = ROOT / published[ref['corpus_id']]
        elif ref.get('folder'):
            folder = ROOT / ref['folder']
        else:
            folder = (ROOT / index[ref['corpus_id']]['pdf']).parent
        pdfs = sorted(folder.glob('*.pdf'))
        hl = highlighted.get(ref.get('corpus_id') or '')
        if hl and (ROOT / hl).exists():                       # the copy with the sheet's quotations highlighted
            pdfs = [ROOT / hl]
        n = numbers.get((ref.get('doi') or '').lower()) or numbers.get(key)
        if key == 'page2021':
            n = numbers.get('10.1136/bmj.n71', n)
        papers.append({
            'key': key, 'n': n, 'label': label(ref.get('ieee', key)), 'role': ref.get('role', ''),
            'folder': str(folder.relative_to(ROOT)),
            'pdf': str(pdfs[0].relative_to(ROOT)) if pdfs else '',
            'notes': str((folder / 'notes' / 'NOTES.md').relative_to(ROOT)),
            'summary': str((folder / 'notes' / 'SUMMARY.md').relative_to(ROOT)),
        })
    papers.sort(key=lambda p: (p['n'] is None, p['n'] or 0))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'paper_version': version, 'papers': papers}, indent=1, ensure_ascii=False))
    problems = [p['key'] for p in papers if not p['pdf'] or not (ROOT / p['notes']).exists()
                or not (ROOT / p['summary']).exists() or p['n'] is None]
    print(f'{len(papers)} cited works of V{version} -> {OUT.relative_to(ROOT)}'
          + (f'; check: {problems}' if problems else '; every work has a PDF, notes, a summary and a number'))


if __name__ == '__main__':
    main()
