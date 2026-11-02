#!/usr/bin/env python3
"""Check the short note of each paper (notes/SUMMARY.md) against scripts/SUMMARY-PROTOCOL.md, or against
scripts/SUMMARY-PROTOCOL-V2.md (15 October 2026) when the note carries the V2 labels (Fabric and cost … / What it treats …).

Tests: the title line and the line under it; the labels, in order; the length (150 to 250 words, V2: 150 to 230, below the
title and the line under it); at least two page citations under the results (V2: under the evidence or findings label);
that every ID named exists in the corpus; that the note mentions no section numbers, draft versions or template markup;
and (V2) none of the banned words of the writing rules. The 75 studies of the PPML review are found through
corpus/ppmlcorpus/included/INDEX.csv, the rest through the extraction manifest.

Usage: scripts/.venv/bin/python scripts/check_summary.py [ID ...]    (no IDs: every paper in the manifest)
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
import csv
MANIFEST = json.loads((ROOT / 'corpus' / '_extraction' / 'MANIFEST.json').read_text(encoding='utf-8'))
FOLDERS = {p['id']: ROOT / 'corpus' / p['folder'] for p in MANIFEST['papers']}
_INC = ROOT / 'corpus' / 'ppmlcorpus' / 'included' / 'INDEX.csv'
if _INC.exists():                                             # the included studies' own folders (published versions there)
    FOLDERS.update({r['corpus_id']: ROOT / r['folder'] for r in csv.DictReader(_INC.open(encoding='utf-8'))})
PRIMARY = ['In short', 'Problem', 'Approach', 'Results', 'Limits (authors)', 'Use in this review']
SECONDARY = ['In short', 'Scope and method', 'Main content', 'Findings and open issues', 'Limits (authors)',
             'Use in this review']
PRIMARY_V2 = ['In short', 'Fabric and cost', 'Privacy and the ledger', 'Threats, defences and evidence', 'Open problems (authors)']
SECONDARY_V2 = ['In short', 'Scope and method', 'What it treats', 'Findings and open issues (authors)']
OPTIONAL = ['For the PhD', 'Related']
BANNED = re.compile(r'\b(delv\w*|tapestr\w*|testament|paramount|leverag\w*|multifaceted|bolster\w*|furthermore|moreover|in conclusion)\b', re.I)
LABEL = re.compile(r'^\*\*([^*]+?)\.\*\*', re.M)
FORBIDDEN = [(re.compile(r'\bSections? [IVX]+\b|\bTables? [IVX]+\b|\bFig(?:ure|\.)? \d'), 'names a section, table or figure'),
             (re.compile(r'\bV1\d\b'), 'names a draft version'),
             (re.compile(r'\{\{|@[SNO]\d{3}'), 'template markup')]


def check(pid, path=None):
    """(problems, words) for the note of study pid: its notes/SUMMARY.md, or the file at `path` (a staged note)"""
    f = pathlib.Path(path) if path else FOLDERS[pid] / 'notes' / 'SUMMARY.md'
    if not f.exists():
        return ['no notes/SUMMARY.md'], 0
    text = f.read_text(encoding='utf-8')
    lines = [x for x in text.splitlines() if x.strip()]
    errs = []
    if len(lines) < 3 or not re.match(rf'^# {pid} · .+ \d{{4}} · .+', lines[0]):
        errs.append('title line is not "# <ID> · <author> <year> · <title>"')
    labels = LABEL.findall(text)
    v2 = any(x in ('Fabric and cost', 'What it treats') for x in labels)
    if v2:
        m = re.match(r'^\*(.+) · (design|survey) · included\*$', lines[1]) if len(lines) > 1 else None
        if not m:
            errs.append('second line is not "*<venue> · <design|survey> · included*"')
        want = SECONDARY_V2 if (m and m.group(2) == 'survey') else PRIMARY_V2
        if labels != want:
            errs.append(f'labels {labels} should be {want}')
    else:
        m = re.match(r'^\*(.+) · (primary|secondary) study · (included|excluded \([^)]*\)[^·]*) · theme: .+\*$', lines[1]) if len(lines) > 1 else None
        if not m:
            errs.append('second line is not "*<venue> · <primary|secondary> study · <status> · theme: <theme>*"')
        want = SECONDARY if (m and m.group(2) == 'secondary') else PRIMARY
        core = [x for x in labels if x not in OPTIONAL]
        if core != want:
            errs.append(f'labels {core} should be {want}')
        if [x for x in labels if x in OPTIONAL] != [x for x in OPTIONAL if x in labels]:
            errs.append('optional labels out of order')
        if labels and labels[-1] not in OPTIONAL + ['Use in this review']:
            errs.append('the note should end with Use in this review, For the PhD or Related')
    body = '\n'.join(lines[2:])
    words = len(re.sub(r'\[p[^\]]*\]|[*#`]|^- |\s[-–]\s', ' ', body, flags=re.M).split())
    lo, hi = (150, 230) if v2 else (150, 250)
    if not lo <= words <= hi:
        errs.append(f'{words} words ({lo} to {hi} required)')
    res = re.search(r'\*\*(?:Results|Findings and open issues(?: \(authors\))?|Threats, defences and evidence)\.\*\*(.*?)(?=\n\*\*[A-Z]|\Z)', text, re.S)
    if not res or len(re.findall(r'\[p\d', res.group(1))) < 2:
        errs.append('fewer than two page citations under the results')
    if v2:
        for w in sorted({x.lower() for x in BANNED.findall(body)}):
            errs.append(f'banned word: {w}')
        if re.search(r'\b(PhD|sheets?|readers?|draft)\b', body):
            errs.append('mentions the PhD, a sheet, a reader or a draft')
    for rx, why in FORBIDDEN:
        if rx.search(body):
            errs.append(f'{why}: "{rx.search(body).group(0)}"')
    for x in sorted(set(re.findall(r'\b[SNO]\d{3}\b', body)) - {pid}):
        if x not in FOLDERS:
            errs.append(f'names {x}, which is not in the corpus')
    return errs, words


def main(ids):
    bad = 0
    for pid in ids or list(FOLDERS):
        if pid not in FOLDERS:
            print(f'{pid} FAIL  not in the manifest')
            bad += 1
            continue
        errs, words = check(pid)
        print(f'{pid} {"FAIL" if errs else "PASS"}  {words} words' + ''.join(f'\n    - {e}' for e in errs))
        bad += bool(errs)
    print(f'{len(ids or FOLDERS) - bad} pass, {bad} fail')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
