#!/usr/bin/env python3
"""Checks that every quotation a reader gave is on the page it names, and that the reader's verdict file is complete, printing counts only.

For each design given, reads `algorithm/reader-quotes.json` and finds each quotation on its page (text/pages/ or
text/pages_ocr/, after joining hyphenated line breaks and collapsing white space; a quotation found on a neighbouring page is
counted as found there). Checks that `algorithm/reader.json` has every checklist item with an allowed status, an allowed
verdict and effort, and applies the instructions' rule to the item statuses (core items C, D, F and, where it applies, E):
viable when every item that applies is specified; viable with assumptions when the core is specified; core partly
specified (the author to judge) when no core item is missing but one is partly; not viable when a core item is missing. Writes `algorithm/02-quote-check.json` (per quotation: found or not, page found on; no quotation text)
and prints one line per design. No quotation is printed.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/verify_reader_quotes.py <id> [<id> ...]
"""
import json, pathlib, re, sys, unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import design, page_texts, save_json, now   # noqa: E402

ITEMS = ['A_task_model', 'B_training_aggregation', 'C_privacy_mechanism', 'D_check_defence', 'E_ledger', 'F_protocol',
         'G_experiment_setup', 'H_attack_setup', 'I_results_to_compare']
STATUS = {'specified', 'partly', 'missing', 'not applicable'}
VERDICTS = {'viable', 'viable with assumptions', 'not viable'}


def norm(t):
    t = unicodedata.normalize('NFKC', t)
    t = re.sub(r'-\s*\n\s*', '', t)
    t = re.sub(r'[‐-―−]', '-', t)
    t = re.sub(r'[‘’]', "'", re.sub(r'[“”]', '"', t))
    return re.sub(r'\s+', ' ', t).strip().lower()


def check(design_id):
    d = design(design_id)
    alg = d['folder'] / 'algorithm'
    pages = {n: norm(p.read_text(errors='replace')) for n, p in page_texts(d['paper_folder'])}
    supp = {}                                            # the paper's supplementary material, where the pipeline extracted it
    for sp in sorted((d['folder'] / 'evidence' / 'supplementary').glob('*/text/pages/page_*.txt')):
        supp[int(sp.stem.split('_')[1])] = norm(sp.read_text(errors='replace'))
    problems = []
    try:
        r = json.load(open(alg / 'reader.json'))
    except Exception as e:
        return {'design': design_id, 'error': f'reader.json unreadable: {e}'}
    for k in ITEMS:
        it = r.get('items', {}).get(k)
        if not it or it.get('status') not in STATUS:
            problems.append(f'item {k} missing or bad status')
    if r.get('verdict') not in VERDICTS:
        problems.append('bad verdict')
    if r.get('effort') not in ('small', 'medium', 'large'):
        problems.append('bad effort')
    try:
        quotes = json.load(open(alg / 'reader-quotes.json'))
    except Exception:
        quotes = []
    rows = []
    for q in quotes:
        nq = norm(q.get('quote', ''))
        p = q.get('page')
        where = None
        book = supp if q.get('source') == 'supplementary' else pages
        if nq and p in book and nq in book[p]:
            where = p
        else:
            for n in (p - 1, p + 1) if isinstance(p, int) else ():
                if n in book and nq in book[n]:
                    where = n
                    break
        rows.append({'item': q.get('item'), 'source': q.get('source', 'paper'), 'page_given': p, 'found': where is not None, 'found_on': where,
                     'words': len(q.get('quote', '').split())})
    found = sum(1 for x in rows if x['found'])
    st = {k: (r.get('items', {}).get(k) or {}).get('status') for k in ITEMS}
    core = [k for k in ('C_privacy_mechanism', 'D_check_defence', 'F_protocol', 'E_ledger') if st.get(k) != 'not applicable']
    applies = [k for k in ITEMS if st.get(k) != 'not applicable']
    if any(st[k] == 'missing' for k in core):
        rule = 'not viable'
    elif any(st[k] == 'partly' for k in core):
        rule = 'core partly specified'
    elif all(st[k] == 'specified' for k in applies):
        rule = 'viable'
    else:
        rule = 'viable with assumptions'
    agree = (rule == r.get('verdict')) or (rule == 'core partly specified' and r.get('verdict') != 'viable')
    out = {'made': now(), 'quotations': len(rows), 'found': found, 'not_found': len(rows) - found, 'rows': rows,
           'verdict_file_problems': problems, 'reader_verdict': r.get('verdict'), 'rule_verdict': rule,
           'statuses': st, 'reader_and_rule_agree': agree}
    save_json(alg / '02-quote-check.json', out)
    return {'design': design_id, 'verdict': r.get('verdict'), 'rule': rule, 'agree': agree, 'quotes': len(rows), 'found': found,
            'problems': problems}


if __name__ == '__main__':
    for i in sys.argv[1:]:
        x = check(i)
        print(f"{x['design']:6} reader {x.get('verdict', '-'):24} rule {x.get('rule', '-'):22} {'' if x.get('agree', True) else 'DIFFER '}quotes {x.get('found', 0)}/{x.get('quotes', 0)} found  "
              f"{'; '.join(x.get('problems', [])) or x.get('error', 'complete')}")
