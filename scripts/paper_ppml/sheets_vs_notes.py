#!/usr/bin/env python3
"""Do the evidence sheets agree with the notes and summaries they say they come from?  Step 1: the mechanical check.

For every answer of every evidence sheet (search-ppml/evidence/sheets/<id>.json) and every quotation it gives as evidence:
  - is the quotation in the study's SUMMARY.md or NOTES.md (exactly, or its first eight words)?
  - if it is in the notes, does the notes line that carries it cite the same page as the sheet?
The answer's own `located_via` ("summary", "notes", "full text") says where the reader took it from; an answer said to come
from the summary or notes whose quotations are not there is a broken link. Answers taken from the full text are listed as
such (nothing in the notes to compare with; the author checks them against the PDF).

Reads only records — the sheets, notes and summaries — never a paper.
Writes search-ppml/evidence/sheets-vs-notes/MECHANICAL.json and MECHANICAL.csv, and one packet per study
(packets/<id>.md: summary, notes and sheet side by side) for step 2, the reading of each answer against the notes.

Usage: python3 scripts/paper_ppml/sheets_vs_notes.py
"""
import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
OUT = ROOT / 'search-ppml' / 'evidence' / 'sheets-vs-notes'
PAPERS = ROOT / 'notes-verifier' / 'data' / 'papers.json'     # the cited works and where their notes are
GUIDE = ROOT / 'search-ppml' / 'evidence' / 'EXTRACTION-GUIDE.md'

PAGE_CITE = re.compile(r'\[p\d[^\]\n]{0,40}\]')


def norm(text):
    text = unicodedata.normalize('NFKC', text or '')
    text = text.translate({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x2010: '-', 0x2011: '-', 0x2013: '-',
                           0x2014: '-', 0x00AD: None, 0x200B: None})
    text = re.sub(r'(\w)- (\w)', r'\1\2', text)
    text = text.replace('…', ' ').replace('...', ' ').replace('*', '').replace('`', '')   # Markdown emphasis is not text
    return re.sub(r'\s+', ' ', text).strip().lower()


def longest_shared_run(a_words, b_words):
    """Length (in words) of the longest run of consecutive words that two texts share."""
    from difflib import SequenceMatcher
    m = SequenceMatcher(None, a_words, b_words, autojunk=False).find_longest_match(0, len(a_words), 0, len(b_words))
    return m.size


def find(quote, text):
    """How the quotation occurs in text: 'exact'; 'first words' (its first eight words); 'overlap' (the two share a
    run of at least eight consecutive words — typically the sheet quotes a little more or less of the same sentence);
    or '' (not there)."""
    q, t = norm(quote).strip(' ".\''), norm(text)
    if not q:
        return ''
    if q in t:
        return 'exact'
    words = q.split()
    if len(words) >= 8 and ' '.join(words[:8]) in t:
        return 'first words'
    need = min(8, len(words))
    if need >= 5 and longest_shared_run(words, t.split()) >= need:
        return 'overlap'
    return ''


def pages_on_lines(quote, notes_text):
    """The pages cited on the notes lines that carry the quotation."""
    q = norm(quote).strip(' ".\'')
    words = q.split()
    head = ' '.join(words[:8])
    need = min(8, len(words))
    pages = set()
    for line in notes_text.splitlines():
        ln = norm(line)
        if head and (head in ln or (need >= 5 and longest_shared_run(words, ln.split()) >= need)):
            for c in PAGE_CITE.finditer(line):
                pages.update(int(n) for n in re.findall(r'\d+', c.group(0)))
    return sorted(pages)


def question_titles():
    titles = {}
    for m in re.finditer(r'^\| ([PS][1-8]) \| \*\*(.+?)\*\*', GUIDE.read_text(encoding='utf-8'), re.M):
        titles[m.group(1)] = m.group(2).rstrip('.')
    return titles


def main():
    papers = {p['key']: p for p in json.loads(PAPERS.read_text())['papers']}
    titles = question_titles()
    (OUT / 'packets').mkdir(parents=True, exist_ok=True)
    rows, by_study = [], {}
    for sheet_path in sorted(SHEETS.glob('*.json')):
        sheet = json.loads(sheet_path.read_text(encoding='utf-8'))
        key = sheet['id']
        paper = papers.get(key)
        if paper is None:
            continue                                   # a sheet for a work not cited in the current version
        summary = (ROOT / paper['summary']).read_text(encoding='utf-8')
        notes = (ROOT / paper['notes']).read_text(encoding='utf-8')
        study = {'key': key, 'n': paper['n'], 'kind': sheet.get('kind'), 'answers': {}}
        for q, ans in sheet['answers'].items():
            items = []
            for ev in ans.get('evidence') or []:
                in_s, in_n = find(ev.get('quote', ''), summary), find(ev.get('quote', ''), notes)
                note_pages = pages_on_lines(ev.get('quote', ''), notes) if in_n else []
                items.append({'page': ev.get('page'), 'quote': ev.get('quote', ''), 'in_summary': in_s, 'in_notes': in_n,
                              'notes_pages': note_pages,
                              'page_agrees': (ev.get('page') in note_pages) if note_pages else None})
            via = ans.get('located_via', '')
            found = [it for it in items if it['in_summary'] or it['in_notes']]
            if not items:
                status = 'no quotation'
            elif via in ('summary', 'notes') and not found:
                status = 'broken link'                 # said to come from the notes/summary, but its words are not there
            elif via in ('summary', 'notes') and len(found) < len(items):
                status = 'partly linked'
            elif any(it['page_agrees'] is False for it in items):
                status = 'page differs'
            elif via in ('summary', 'notes'):
                status = 'linked'
            else:
                status = 'full text' if not found else 'full text (also in notes)'
            study['answers'][q] = {'title': titles.get(q, ''), 'located_via': via, 'status': status, 'evidence': items}
            rows.append({'key': key, 'n': paper['n'], 'q': q, 'located_via': via, 'status': status,
                         'quotes': len(items), 'found_in_notes_or_summary': len(found),
                         'page_mismatches': sum(1 for it in items if it['page_agrees'] is False)})
        by_study[key] = study
        write_packet(key, paper, sheet, study, summary, notes)

    (OUT / 'MECHANICAL.json').write_text(json.dumps(by_study, indent=1, ensure_ascii=False))
    with (OUT / 'MECHANICAL.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    c = Counter(r['status'] for r in rows)
    print(f'{len(by_study)} sheets, {len(rows)} answers:', dict(c.most_common()))
    print('quotations:', sum(r['quotes'] for r in rows), '| found in notes or summary:',
          sum(r['found_in_notes_or_summary'] for r in rows), '| page mismatches:', sum(r['page_mismatches'] for r in rows))


def write_packet(key, paper, sheet, study, summary, notes):
    """Everything a reader needs to judge the sheet against the notes, in one file — and nothing from the paper itself
    beyond the quotations the sheet and notes already hold."""
    out = [f"# {key} — [{paper['n']}] {paper['label']}", '',
           'Judge each sheet answer ONLY against the SUMMARY and NOTES below. Do not open any other file.', '',
           '## SUMMARY (notes/SUMMARY.md)', '', summary.strip(), '', '## NOTES (notes/NOTES.md)', '', notes.strip(), '',
           '## EVIDENCE SHEET', '']
    for q, ans in sheet['answers'].items():
        m = study['answers'][q]
        out += [f"### {q} — {m['title']}", f"located_via: {ans.get('located_via', '')}  |  mechanical check: {m['status']}", '',
                'Answer:', ans.get('answer', '').strip(), '']
        if ans.get('values'):
            out += ['Values: ' + json.dumps(ans['values'], ensure_ascii=False), '']
        for it in m['evidence']:
            where = ', '.join(x for x in (('summary: ' + it['in_summary']) if it['in_summary'] else '',
                                          ('notes: ' + it['in_notes']) if it['in_notes'] else '') if x) or 'not in notes or summary'
            out.append(f"- Evidence [p{it['page']}] \"{it['quote']}\"  — {where}"
                       + (f"; notes cite p{it['notes_pages']}" if it['notes_pages'] else ''))
        out.append('')
    (OUT / 'packets' / f'{key}.md').write_text('\n'.join(out), encoding='utf-8')


if __name__ == '__main__':
    main()
