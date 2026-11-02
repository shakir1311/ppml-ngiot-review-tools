#!/usr/bin/env python3
"""Apply the sentence corrections that bring summaries and notes into line with the corrected evidence sheets
(search-ppml/evidence/sheet-fix/align/results/<key>.json, made from align/packets/ by summary_notes_flags.py).

A change is applied only if its "old" sentence is the sentence the packet numbered n (S… in SUMMARY.md, N… in NOTES.md);
it is found in the file by walking the numbered sentences in order (so a repeated cite line such as "[p8]" is replaced
at its own place). Before a file is first changed its untouched original is kept in
notes-verifier/history/<key>/SUMMARY-original.md / NOTES-original.md (as the Notes Verifier does), and the version before
this pass as <NAME>-before-align-<time>.md. Every applied change goes to align/APPLIED.jsonl.

Usage: python3 scripts/paper_ppml/apply_align_fixes.py [--apply] [key ...]   (without --apply: checks only)
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sheets as cs

ROOT = cs.ROOT
ALIGN = ROOT / 'search-ppml' / 'evidence' / 'sheet-fix' / 'align'
HISTORY = ROOT / 'notes-verifier' / 'history'

# the same splitting as summary_notes_flags.py (kept here so that this script needs no model)
SPLIT = re.compile(r'(?<=[.!?;])\s+(?=[A-Z(\[])')
ABBREVIATION = re.compile(r'(?:\b(?:Fig|Figs|Eq|Eqs|Sec|Secs|Ref|Refs|Tab|No|Nos|vs|al|e\.g|i\.e|cf|approx)\.)$', re.I)
QUOTE_ONLY = re.compile(r'^[\s\-*]*(\[p\d+\]\s*"[^"]*"?\s*)+$')


def sentences(text, least=5):
    out = []
    for line in text.splitlines():
        parts = []
        for s in SPLIT.split(line):
            if parts and ABBREVIATION.search(parts[-1]):
                parts[-1] += ' ' + s
            else:
                parts.append(s)
        out += parts
    return [s.strip() for s in out if len(s.split()) >= least]


def numbered(name, text):
    if name == 'SUMMARY.md':
        return sentences(text, least=1)
    return [s for s in sentences(text) if not QUOTE_ONLY.match(s)]


def same(a, b):
    return ' '.join(str(a).split()) == ' '.join(str(b).split())


def positions(text, listed):
    """Where each numbered sentence starts in the text (None if it cannot be found in order)."""
    out, cursor = [], 0
    for sentence in listed:
        i = text.find(sentence, cursor)
        out.append(None if i < 0 else i)
        if i >= 0:
            cursor = i + len(sentence)
    return out


def replace_at(text, i, old, new):
    """The text with old (starting at i) replaced; a removed sentence takes its following spaces, and an emptied line goes."""
    j = i + len(old)
    if new:
        return text[:i] + new + text[j:]
    while j < len(text) and text[j] == ' ':
        j += 1
    if j == len(text) or text[j] == '\n':                           # last on its line: take the space before it
        while i > 0 and text[i - 1] == ' ':
            i -= 1
    start = text.rfind('\n', 0, i) + 1
    end = text.find('\n', j)
    end = len(text) if end < 0 else end
    if not (text[start:i] + text[j:end]).strip():                   # the line held only this sentence
        return text[:start] + text[min(end + 1, len(text)):]
    return text[:i] + text[j:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('keys', nargs='*')
    a = ap.parse_args()
    keys = a.keys or sorted(p.stem for p in (ALIGN / 'results').glob('*.json'))
    totals = {'changes': 0, 'applied': 0, 'rejected': 0, 'open': 0}
    log = (ALIGN / 'APPLIED.jsonl').open('a', encoding='utf-8') if a.apply else None
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    for key in keys:
        res = json.loads((ALIGN / 'results' / f'{key}.json').read_text(encoding='utf-8'))
        totals['open'] += len(res.get('open') or [])
        for name, field, letter in (('SUMMARY.md', 'summary', 'S'), ('NOTES.md', 'notes', 'N')):
            items = res.get(field) or []
            if not items:
                continue
            path = cs.folder_of(key) / 'notes' / name
            original = path.read_text(encoding='utf-8')
            listed = numbered(name, original)
            at = positions(original, listed)
            edits, done = [], []
            for it in items:
                totals['changes'] += 1
                n = int(str(it.get('n', '')).lstrip(letter) or 0)
                problem = None
                if not 1 <= n <= len(listed):
                    problem = f'{letter}{n} does not exist'
                elif not same(listed[n - 1], it.get('old', '')):
                    problem = f'{letter}{n} is not the sentence given as "old"'
                elif at[n - 1] is None:
                    problem = f'{letter}{n} cannot be located in {name}'
                elif same(it.get('new', ''), listed[n - 1]):
                    problem = 'no change'
                elif any(e[0] == at[n - 1] for e in edits):
                    problem = f'{letter}{n} is changed twice'
                if problem:
                    totals['rejected'] += 1
                    print(f'  {key} {letter}{n}: NOT applied — {problem}')
                    continue
                edits.append((at[n - 1], listed[n - 1], str(it.get('new', '')).strip()))
                done.append(it)
            text = original
            for i, old, new in sorted(edits, reverse=True):                # from the end, so earlier places stay put
                text = replace_at(text, i, old, new)
            if not done:
                continue
            print(f'{key} {name}: {len(done)} sentence(s)')
            if not a.apply:
                continue
            hist = HISTORY / key
            hist.mkdir(parents=True, exist_ok=True)
            stem = name.split('.')[0]
            if not (hist / f'{stem}-original.md').exists():
                (hist / f'{stem}-original.md').write_text(original, encoding='utf-8')
            (hist / f'{stem}-before-align-{stamp}.md').write_text(original, encoding='utf-8')
            path.write_text(text, encoding='utf-8')
            totals['applied'] += len(done)
            for it in done:
                log.write(json.dumps({'key': key, 'file': name, **it, 'on': datetime.datetime.now().isoformat(
                    timespec='seconds')}, ensure_ascii=False) + '\n')
    if log:
        log.close()
    print('\n' + ' · '.join(f'{k} {v}' for k, v in totals.items()) + ('' if a.apply else '  (check only: nothing written)'))


if __name__ == '__main__':
    main()
