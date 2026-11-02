#!/usr/bin/env python3
"""Settle, with the paper's extracted text, the points where an evidence sheet and the notes or summary disagree.

Runs locally. What it prints and writes holds only the records' own words (sheet, notes, readings), found or not found,
and page numbers — never the paper's text (workspace rule; the author's decision of 11 October 2026).

For every point the reading of 11 October flagged (status differs, conflicts or not-in-notes) in
search-ppml/evidence/sheets-vs-notes/verdicts/<id>.json:
  - the sheet's words and the notes' words for the point are looked up in the paper as whole passages (are they the
    paper's own wording, and on which pages?);
  - the checkable items in each side that the other side does not share — numbers, names (capitalised terms and
    acronyms) and quoted phrases — are looked up one by one, and so are the items the proposed fix would bring in;
  - the evidence quotations of the sheet answer are re-checked on their cited pages.
Outcome per point:
  'paper backs the notes'  every distinctive notes item is in the paper and no distinctive sheet item is;
  'paper backs the sheet'  the reverse;
  'both in the paper', 'neither in the paper', 'mixed', 'nothing checkable by words' — left to the author;
  for not-in-notes points: 'sheet holds more, in the paper' or 'sheet holds more, not checkable by words' (kept).

Writes search-ppml/evidence/sheets-vs-notes/PAPER-CHECK.json and PAPER-CHECK.csv (all points) when run on every study.
Usage: python3 scripts/paper_ppml/sheets_notes_vs_paper.py [id ...]
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sheets import norm, squash                     # the matching the quotation check uses

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / 'search-ppml' / 'evidence'
SHEETS = EV / 'sheets'
OUT = EV / 'sheets-vs-notes'
PAPERS = ROOT / 'notes-verifier' / 'data' / 'papers.json'
FLAGGED = ('differs', 'conflicts', 'not-in-notes')

NUMBER = re.compile(r'(?<![\w.])(\d{1,3}(?:[ ,  ]\d{3})+(?:\.\d+)?|\d+\.\d+|\d+)'
                    r'(\s?(?:%|×|x\b|ms\b|s\b|kB|KB|MB|GB|Mbps|dB|mJ|J\b|min\b|h\b))?')
STRUCTURE = re.compile(r'(?:fig\.?|figure|table|section|sec\.|algorithm|alg\.|eq\.?|equation|p|pp\.|page|v|step|'
                       r'phase|round|stage|ref\.|\[)\s*$', re.I)
NAME = re.compile(r'\b[A-Z][\w\-]*(?:\s+(?:of|for|the|in|on|over|with)?\s*[A-Z][\w\-]*)+')
ACRONYM = re.compile(r'\b[A-Za-z]*[A-Z][a-z]*[A-Z][A-Za-z0-9\-]*\b')
QUOTED = re.compile(r'[“"]([^”"]{8,200})[”"]|‘([^’]{8,200})’')
RECORD_WORDS = {'values', 'claimed', 'notes', 'sheet', 'tag', 'tags', 'fig', 'table', 'section', 'algorithm', 'drop', 'add',
                'keep', 'state', 'say', 'limit', 'reconcile', 'answer', 'hidden_from', 'on_chain'}
GROUP_SEP = re.compile(r'(?<=\d)[ ,  ](?=\d{3}(?!\d))')


def numbers(text):
    """Numbers worth looking up: with a decimal point, three or more digits, or a unit; not figure/section/page numbers."""
    out = {}
    for m in NUMBER.finditer(text):
        raw, unit = m.group(1), (m.group(2) or '').strip()
        if STRUCTURE.search(text[max(0, m.start() - 12):m.start()]):
            continue
        canon = GROUP_SEP.sub('', raw)
        if '.' in canon or len(canon) >= 3 or unit in ('%', '×', 'x'):
            out[canon] = (raw + (' ' + unit if unit else '')).strip()
    return out


def names(text):
    found = set()
    for m in NAME.finditer(text):
        words = m.group(0).split()
        while words and words[0].lower() in RECORD_WORDS:
            words = words[1:]
        if len(words) >= 2:
            found.add(' '.join(words))
    for m in ACRONYM.finditer(text):
        if m.group(0).lower() not in RECORD_WORDS and len(m.group(0)) >= 2:
            found.add(m.group(0))
    return found


def quoted(text):
    return {a or b for a, b in QUOTED.findall(text)}


def passages(text):
    """Stretches of six or more words, split where the records join or cut text."""
    parts = re.split(r'\s*(?:;|…|\.\.\.|\(|\)|: )\s*', text or '')
    return [p.strip(' .,"“”‘’\'') for p in parts if len(p.split()) >= 6]


class Paper:
    def __init__(self, folder: Path):
        self.pages = {}
        for sub in ('pages', 'pages_ocr'):
            for f in sorted((folder / 'text' / sub).glob('page_*.txt')):
                n = int(f.stem.split('_')[1])
                text = f.read_text(encoding='utf-8', errors='ignore')
                prev = self.pages.get(n, ('', '', ''))
                self.pages[n] = (prev[0] + ' ' + norm(text), prev[1] + squash(text),
                                 prev[2] + ' ' + GROUP_SEP.sub('', norm(text)))

    def find_words(self, words):
        sq = squash(words)
        if not sq:
            return []
        if len(sq) <= 5:                                   # short terms and acronyms: whole words only
            pat = re.compile(r'(?<![a-z0-9])' + re.escape(norm(words)) + r'(?![a-z0-9])')
            return [n for n, (t, _, _) in sorted(self.pages.items()) if pat.search(t)]
        return [n for n, (_, s, _) in sorted(self.pages.items()) if sq in s]

    def find_number(self, canon):
        pat = re.compile(r'(?<![\d.])' + re.escape(canon) + r'(?![\d])')
        return [n for n, (_, _, t) in sorted(self.pages.items()) if pat.search(t)]

    def quote_on_page(self, quote, page):
        p = self.pages.get(page)
        return bool(p) and (norm(quote) in p[0] or squash(quote) in p[1])


def items(text):
    return {'numbers': numbers(text), 'names': names(text), 'quoted': quoted(text)}


def distinctive(mine, other_text):
    """Items of one side that the other side's words do not contain."""
    other_sq, other_nums = squash(other_text), set(numbers(other_text))
    out = []
    for canon, shown in mine['numbers'].items():
        if canon not in other_nums:
            out.append(('number', shown, canon))
    for kind in ('names', 'quoted'):
        for x in sorted(mine[kind]):
            if squash(x) and squash(x) not in other_sq:
                out.append((kind[:-1] if kind == 'names' else 'quote', x, x))
    return out


NEGATION = re.compile(r'\b(no|not|never|none|nor|without|absent|neither)\b', re.I)


def negated(item, text):
    """Is the item named inside a clause that denies it ('No edge, fog or MEC tier is named')?"""
    i = text.find(item)
    if i < 0:
        return False
    start = max(text.rfind(c, 0, i) for c in '.;:')
    return bool(NEGATION.search(text[start + 1:i]))


def look_up(paper, found_items, text=''):
    res = []
    for kind, shown, key in found_items:
        pages = paper.find_number(key) if kind == 'number' else paper.find_words(key)
        res.append({'kind': kind, 'item': shown, 'pages': pages, 'negated': negated(shown, text)})
    return res


def supported(r):
    """An item backs its side when it is in the paper, or — for an item the side denies — when it is not."""
    return bool(r['pages']) != r.get('negated', False)


def judge(status, sheet_res, notes_res, sheet_pass, notes_pass):
    s_ok = [r for r in sheet_res if supported(r)]
    s_no = [r for r in sheet_res if not supported(r)]
    n_ok = [r for r in notes_res if supported(r)]
    n_no = [r for r in notes_res if not supported(r)]
    if status == 'not-in-notes':
        return 'sheet holds more, in the paper' if (s_ok or sheet_pass) else 'sheet holds more, not checkable by words'
    if not sheet_res and not notes_res:
        return 'nothing checkable by words'
    if n_ok and not n_no and s_no and not s_ok:
        return 'paper backs the notes'
    if s_ok and not s_no and n_no and not n_ok:
        return 'paper backs the sheet'
    if (s_ok or n_ok) and not s_no and not n_no:
        return 'both in the paper'
    if not s_ok and not n_ok:
        return 'neither in the paper'
    return 'mixed'


NOTE_QUOTE = re.compile(r'[“"]([^”"]{12,400})[”"]')
CITED = re.compile(r'\[p(\d+)')


def notes_support(point_notes, notes_text, paper):
    """The notes/summary lines the reading cites for a point, with each of their quotations checked on the paper."""
    words = norm(point_notes).split()
    out = []
    if len(words) < 4:
        return out
    from sheets_vs_notes import longest_shared_run
    need = min(6, len(words))
    for line in notes_text.splitlines():
        if longest_shared_run(words, norm(line).split()) < need:
            continue
        cited = [int(n) for n in CITED.findall(line)]
        quotes = []
        for m in NOTE_QUOTE.finditer(line):
            q = m.group(1)
            anywhere = paper.find_words(q)
            quotes.append({'quote': q, 'cited_pages': cited,
                           'on_cited_page': any(paper.quote_on_page(q, n) for n in cited), 'pages': anywhere})
        out.append({'line': line.strip(), 'cited_pages': cited, 'quotes': quotes})
    return out


def check_study(key, paper_meta):
    verdict_file = OUT / 'verdicts' / f'{key}.json'
    readings = json.loads(verdict_file.read_text(encoding='utf-8'))['answers']
    sheet = json.loads((SHEETS / f'{key}.json').read_text(encoding='utf-8'))
    paper = Paper(ROOT / paper_meta['folder'])
    notes_text = '\n'.join((ROOT / paper_meta[f]).read_text(encoding='utf-8') for f in ('summary', 'notes'))
    rows = []
    for q, reading in readings.items():
        if reading.get('verdict') not in FLAGGED:          # only the answers the reading flagged
            continue
        ans = sheet['answers'].get(q, {})
        quotes = [e for e in ans.get('evidence') or [] if isinstance(e, dict) and e.get('source') not in ('table', 'image')]
        quotes_ok = sum(paper.quote_on_page(e.get('quote', ''), e.get('page')) for e in quotes)
        for i, pt in enumerate(reading.get('points') or []):
            status = pt.get('status')
            if status not in FLAGGED:
                continue
            s_text, n_text, fix = pt.get('sheet') or '', pt.get('notes') or '', pt.get('fix') or ''
            s_items, n_items = items(s_text), items(n_text)
            sheet_res = look_up(paper, distinctive(s_items, n_text), s_text)
            notes_res = look_up(paper, distinctive(n_items, s_text), n_text) if status != 'not-in-notes' else []
            fix_res = look_up(paper, distinctive(items(fix), s_text), fix) if fix else []
            notes_quotes = notes_support(n_text, notes_text, paper) if status != 'not-in-notes' else []
            s_pass = [{'words': p, 'pages': paper.find_words(p)} for p in passages(s_text)]
            n_pass = [{'words': p, 'pages': paper.find_words(p)} for p in passages(n_text)]
            rows.append({
                'key': key, 'n': paper_meta['n'], 'q': q, 'point': i, 'verdict': reading.get('verdict'), 'status': status,
                'outcome': judge(status, sheet_res, notes_res, any(p['pages'] for p in s_pass), any(p['pages'] for p in n_pass)),
                'sheet': s_text, 'notes': n_text, 'fix': fix,
                'sheet_items': sheet_res, 'notes_items': notes_res, 'fix_items': fix_res,
                'sheet_passages': s_pass, 'notes_passages': n_pass, 'notes_quotes': notes_quotes,
                'answer_quotes_on_page': f'{quotes_ok}/{len(quotes)}'})
    return rows


def show(res):
    return '; '.join(f"{r['item']} ({'p' + ','.join(map(str, r['pages'][:6])) if r['pages'] else 'not found'})" for r in res)


def main(ids):
    papers = {p['key']: p for p in json.loads(PAPERS.read_text())['papers']}
    every = not ids
    ids = ids or sorted(p.stem for p in (OUT / 'verdicts').glob('*.json'))
    rows = []
    for key in ids:
        rows += check_study(key, papers[key])
    if every:
        (OUT / 'PAPER-CHECK.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf-8')
        with (OUT / 'PAPER-CHECK.csv').open('w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['key', 'n', 'q', 'point', 'status', 'outcome', 'sheet', 'notes', 'fix', 'sheet items in paper',
                        'notes items in paper', 'fix items in paper', 'sheet words verbatim in paper',
                        'notes words verbatim in paper', 'answer quotations on their page'])
            for r in rows:
                w.writerow([r['key'], r['n'], r['q'], r['point'], r['status'], r['outcome'], r['sheet'], r['notes'], r['fix'],
                            show(r['sheet_items']), show(r['notes_items']), show(r['fix_items']),
                            '; '.join(f"p{','.join(map(str, p['pages']))}" for p in r['sheet_passages'] if p['pages']),
                            '; '.join(f"p{','.join(map(str, p['pages']))}" for p in r['notes_passages'] if p['pages']),
                            r['answer_quotes_on_page']])
    print(f'{len(rows)} flagged points in {len({r["key"] for r in rows})} studies')
    for (status, outcome), c in sorted(Counter((r['status'], r['outcome']) for r in rows).items()):
        print(f'  {status:13} {outcome:42} {c}')
    bad = [f"{r['key']} {r['q']} {r['answer_quotes_on_page']}" for r in rows
           if r['answer_quotes_on_page'].split('/')[0] != r['answer_quotes_on_page'].split('/')[1]]
    print('answers whose quotations are not all on their page:', sorted(set(bad)) or 'none')


if __name__ == '__main__':
    main(sys.argv[1:])
