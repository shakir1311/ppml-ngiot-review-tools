#!/usr/bin/env python3
"""Write a compact digest of each paper's notes for the synthesis stage of the review.

The digest is a view of notes/NOTES.md as collected in corpus/_extraction/statements.csv:
header fields; for a secondary study the heading list of section 5 and section 4 (the review
method); sections 1, 3, 6.1-6.9, 7-10 and 14; and four items of section 15 (baselines, data, code,
statistics). Every statement is kept with its page citations; the quotations are removed (they stay
in the notes, where they can be checked). Nothing is added or reworded.

Usage: scripts/.venv/bin/python scripts/review/digest.py <out_dir>
"""
import csv, re, sys, pathlib, collections

csv.field_size_limit(10**9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
EXT = ROOT / 'corpus' / '_extraction'
KEEP = ['1', '3', '4', '6', '7', '8', '9', '10', '14', '15']
RIGOUR = ('Baselines and comparison', 'Data', 'Code and artefacts', 'Statistical treatment')
QUOTE = re.compile(r'\s*"[^"]*"')

def main(out_dir):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    papers = {r['id']: r for r in csv.DictReader(open(EXT / 'papers.csv', encoding='utf-8'))}
    by_id = collections.defaultdict(list)
    for s in csv.DictReader(open(EXT / 'statements.csv', encoding='utf-8')):
        by_id[s['id']].append(s)
    for pid, p in papers.items():
        rows = by_id[pid]
        lines = [f"# {pid} — {p['title']}", '']
        for k in ('authors', 'year', 'venue', 'doi', 'publication_type', 'document_type', 'research_type',
                  'evaluation_type', 'theme_primary', 'themes_secondary', 'codes', 'keywords_authors', 'pages'):
            lines.append(f"- {k}: {p[k]}")
        secondary = p['document_type'] in ('survey', 'systematic review')
        if secondary:
            heads = []
            for s in rows:
                if s['section'] == '5' and s['subsection'] and s['subsection'] not in heads:
                    heads.append(s['subsection'])
            lines += ['', '## 5. Headings of the paper (from the section-by-section digest)', '']
            lines += [f"- {h}" for h in heads]
        current = None
        for sec in KEEP:
            if sec == '4' and not secondary:
                continue
            for s in rows:
                if s['section'] != sec:
                    continue
                if sec == '6' and s['facet'] == '6.10':
                    continue
                if sec == '15' and not s['statement'].startswith(RIGOUR):
                    continue
                head = f"## {sec}. {s['section_title']}"
                if head != current:
                    lines += ['', head, '']
                    current = head
                sub = s['subsection'] if sec == '6' else ''
                text = QUOTE.sub('', s['statement']).strip()
                lines.append(f"- {('[' + sub.split(' ')[0] + '] ') if sub else ''}{text}")
        (out / f"{pid}.md").write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"{len(papers)} digests written to {out}")

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'digests')
