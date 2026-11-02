#!/usr/bin/env python3
"""Collect the themes of every brief thematic note (template ppml-2, scripts/NOTES-PPML-PROTOCOL-V2.md) into one table,
so that the downloaded papers can be analysed by theme from their notes and summaries alone.

For each paper folder under corpus/ whose notes/NOTES.md is a ppml-2 note: the header (id, kind, year, title), the theme
tags (layers, angles, settings, mechanisms, threats claimed and tested) and the eight labelled lines of notes/SUMMARY.md.
Writes corpus/_extraction/NOTES-THEMES.csv and prints how often each tag occurs, by kind of study.

Usage: python3 scripts/paper_ppml/notes_themes.py
"""
import collections, csv, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_notes_simple import THEMES, SUMMARY_LINES, themes_of          # noqa: E402
import notes_format as N                                                  # noqa: E402


def summary_lines(path):
    s = path.read_text(encoding='utf-8') if path.exists() else ''
    out = {}
    for lab in SUMMARY_LINES:
        m = re.search(r'\*\*' + re.escape(lab) + r'\.\*\*\s*(.*)', s)
        out[lab] = m.group(1).strip() if m else ''
    return out


def main():
    rows = []
    for notes in sorted((ROOT / 'corpus').rglob('notes/NOTES.md')):
        head, _ = N.parse_header(notes.read_text(encoding='utf-8'))
        if head.get('template') != 'ppml-2':
            continue
        th = themes_of(notes)
        sm = summary_lines(notes.parent / 'SUMMARY.md')
        rows.append({'id': head.get('id'), 'kind': head.get('kind'), 'year': head.get('year'), 'title': head.get('title'),
                     'folder': str(notes.parent.parent.relative_to(ROOT)),
                     **{k: '; '.join(th.get(k, [])) for k in THEMES}, **{f'summary_{k.lower().replace(" ", "_")}': v for k, v in sm.items()}})
    out = ROOT / 'corpus' / '_extraction' / 'NOTES-THEMES.csv'
    out.parent.mkdir(exist_ok=True)
    if rows:
        with open(out, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f'{len(rows)} ppml-2 notes -> {out.relative_to(ROOT)}')
    for key in THEMES:
        c = collections.Counter((r['kind'], v) for r in rows for v in r[key].split('; ') if v)
        if c:
            print(f'{key}: ' + ', '.join(f'{v} {n}' + (f' ({k})' if k else '') for (k, v), n in sorted(c.items(), key=lambda x: -x[1])))


if __name__ == '__main__':
    main()
