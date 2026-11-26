#!/usr/bin/env python3
"""Checks each study reader's output: the form of study/reader.json, the review's allowed values in its P1 to P3 classification, and every quotation found on its page of the paper.

For each design read in the Phase 2 study (study_packets.SIX and QUALITATIVE), the parts its kind must fill are present, the
`sheet_values` use the values that check_sheets.ALLOWED allows for the evidence sheets (or "other: ..."), the checklist uses the
Phase 1 statuses, and each quotation in study/reader-quotes.json is found, after normalising spaces, hyphens and quotation marks,
on the page given or the page next to it. Writes study/02-quote-check.json in the design's folder and prints one line per design:
counts and problems only, never the quotations.

Usage: python3 scripts/design_eval/verify_study_quotes.py [<id> ...]
"""
import json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'paper_ppml'))
from common import page_texts, now, save_json   # noqa: E402
from study_packets import QUALITATIVE, SIX, resolve   # noqa: E402
from verify_reader_quotes import ITEMS, STATUS, VERDICTS, norm   # noqa: E402
import check_sheets   # noqa: E402

NEED = {'six': ['card', 'datasets', 'setup', 'runs', 'experiments', 'code_vs_paper', 'reproduction_notes'],
        'qualitative': ['card', 'datasets', 'setup', 'runs', 'checklist']}


def verdict_of(r):
    """the checklist verdict: at the top of reader.json, or inside the checklist (the prompt allowed either reading)"""
    return r.get('verdict') or (r.get('checklist') or {}).get('verdict')
CARD = ['summary', 'parties', 'round', 'task_and_model', 'aggregation', 'privacy', 'verification', 'ledger', 'trust_assumptions',
        'threat_model', 'phd_threats', 'stated_limitations']


def allowed(value, ok):
    return value in ok or str(value).startswith('other')


def check_sheet_values(sv):
    problems = []
    for P in ('P1', 'P2', 'P3'):
        vals = (sv or {}).get(P)
        if not isinstance(vals, dict):
            problems.append(f'sheet_values.{P} missing')
            continue
        for field, ok in check_sheets.ALLOWED[P].items():
            if field not in vals:
                if (P, field) not in check_sheets.OPTIONAL or vals.get('zk_used'):
                    problems.append(f'{P}.{field} missing')
                continue
            if ok is None:
                continue
            for x in (vals[field] if isinstance(vals[field], list) else [vals[field]]):
                if not allowed(x, ok):
                    problems.append(f'{P}.{field} has {x!r}')
    return problems


def check(i):
    d = resolve(i)
    kind = 'six' if i in SIX else 'qualitative'
    st = d['folder'] / 'study'
    try:
        r = json.load(open(st / 'reader.json'))
    except Exception as e:
        return {'design': i, 'kind': kind, 'error': f'reader.json missing or unreadable: {e}'}
    problems = [f'{k} missing' for k in NEED[kind] if k not in r]
    problems += [f'card.{k} missing' for k in CARD if k not in (r.get('card') or {})]
    if not d['sheet']:
        problems += check_sheet_values(r.get('sheet_values'))
    if kind == 'qualitative':
        for k in ITEMS:
            if (r.get('checklist', {}).get(k) or {}).get('status') not in STATUS:
                problems.append(f'checklist.{k} missing or bad status')
        if verdict_of(r) not in VERDICTS:
            problems.append('bad verdict')
    pages = {n: norm(p.read_text(errors='replace')) for n, p in page_texts(d['paper_folder'])}
    try:
        quotes = json.load(open(st / 'reader-quotes.json'))
    except Exception:
        quotes, problems = [], problems + ['reader-quotes.json missing or unreadable']
    rows = []
    for q in quotes:
        nq, p = norm(q.get('quote', '')), q.get('page')
        where = p if (nq and p in pages and nq in pages[p]) else next(
            (n for n in ((p - 1, p + 1) if isinstance(p, int) else ()) if n in pages and nq in pages[n]), None)
        rows.append({'item': q.get('item'), 'page_given': p, 'found': where is not None, 'found_on': where,
                     'words': len(q.get('quote', '').split()), 'too_long': len(q.get('quote', '').split()) > 25})
    out = {'design': i, 'kind': kind, 'made': now(), 'quotations': len(rows), 'found': sum(x['found'] for x in rows),
           'not_found': [x for x in rows if not x['found']], 'too_long': sum(x['too_long'] for x in rows),
           'problems': problems, 'rows': rows}
    save_json(st / '02-quote-check.json', out)
    return out


if __name__ == '__main__':
    for i in sys.argv[1:] or SIX + QUALITATIVE:
        o = check(i)
        if 'error' in o:
            print(i, o['kind'], 'ERROR', o['error'])
        else:
            print(i, o['kind'], f"quotes {o['found']}/{o['quotations']} found, {o['too_long']} over 25 words,",
                  f"{len(o['problems'])} problems", ('| ' + '; '.join(o['problems'][:6])) if o['problems'] else '')
