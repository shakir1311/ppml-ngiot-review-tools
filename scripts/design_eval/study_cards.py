#!/usr/bin/env python3
"""Builds one card per design for the Phase 2 study, all 54 designs on one frame: the six carried forward and the 48 not carried forward.

The frame is the review's own: the evidence sheets' P1 to P3 fields (setting, privacy, ledger, checking, threats, evaluation) and
the three conditions of the review's gap, computed by the review's rule (thematic.gap_conditions; C1 a cost measured on
device-class hardware, C2 no party that checks or aggregates sees an individual update, C3 an attack of poisoning, malicious or
fake participants or free riding tested), with the PhD's threats claimed and tested, how far the paper specifies the design
(the Phase 1 checklist), and the datasets, set-up and runs. Sources: the review's 45 evidence sheets (verified by the author)
and Phase 1 reader checklists; for the nine new designs and the six carried forward, the study readers' records
(study/reader.json, checked by verify_study_quotes.py). Run on the 45 sheets, the rule gives exactly the review's own lists of
designs meeting each condition (build/cites-v68.json); the script stops if it does not.

Writes study/card.json in each design's folder, design-evaluation/study/CARDS.json and CARDS.csv.
Usage: python3 scripts/design_eval/study_cards.py
"""
import csv, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'paper_ppml'))
from common import EVAL, ROOT, load_designs, now, save_json   # noqa: E402
from phase2_tables import GROUPS, collect   # noqa: E402
from study_packets import QUALITATIVE, SIX, resolve   # noqa: E402
from verify_study_quotes import verdict_of   # noqa: E402
import thematic as T   # noqa: E402

STUDY = EVAL / 'study'
NAMES = {'n2721': 'zkPET', 'n3378': 'FL-BC-IDS', 'Z01': 'PoL-BFL', 'Z04': 'RoFL', 'Z06': 'zkPoT', 'Z07': 'zk-DEAP'}
FIELDS = [('P1', 'settings'), ('P1', 'enablers'), ('P1', 'fl'), ('P1', 'device_measured'), ('P1', 'network_measured'),
          ('P1', 'costs_reported'), ('P1', 'cost_where'), ('P2', 'mechanisms'), ('P2', 'protects'), ('P2', 'hidden_from'),
          ('P2', 'ledger'), ('P2', 'platform'), ('P2', 'consensus'), ('P2', 'on_chain'), ('P2', 'roles'), ('P2', 'trusted'),
          ('P3', 'checked'), ('P3', 'checker'), ('P3', 'checker_sees_update'), ('P3', 'zk_used'), ('P3', 'zk_shows'),
          ('P3', 'claimed'), ('P3', 'tested'), ('P3', 'defences'), ('P3', 'datasets'), ('P3', 'baselines'),
          ('P3', 'environment'), ('P3', 'scale')]
PHD = {'poisoning': {'poisoning', 'backdoor'}, 'malicious_fake': {'byzantine-malicious', 'sybil-fake'}, 'free_riding': {'free-riding'}}
CHECKLIST = ['A_task_model', 'B_training_aggregation', 'C_privacy_mechanism', 'D_check_defence', 'E_ledger', 'F_protocol',
             'G_experiment_setup', 'H_attack_setup', 'I_results_to_compare']


def sheet_of(i, reader):
    """the review's evidence sheet, or the reader's classification in the sheet's form"""
    p = ROOT / 'search-ppml' / 'evidence' / 'sheets' / f'{i}.json'
    if p.exists():
        return json.load(open(p)), 'evidence sheet (author-verified)'
    sv = (reader or {}).get('sheet_values') or {}
    return {'id': i, 'answers': {P: {'values': sv.get(P, {})} for P in ('P1', 'P2', 'P3')}}, 'study reader'


def conditions(i, sh):
    g = T.gap_conditions(i, sh)
    return {'C1': g['C1'], 'C2': g['C2'], 'C3': bool(g['C4a'] or g['C4b'] or g['C4c'])}


def main():
    rows, six = collect()
    status = {r[0]: ('not carried forward', key) for key, *_ in GROUPS for r in rows[key]}
    status.update({s[0]: ('carried forward', 'carried') for s in six})
    label = dict((k, t) for k, t, _ in GROUPS) | {'carried': 'Carried forward: code the paper names, licence lets us run it'}
    review = {d['id']: d for d in load_designs()}
    ids = sorted(review) + [f'Z0{n}' for n in range(1, 10)]
    assert set(ids) == set(status), set(ids) ^ set(status)
    cards = []
    for i in ids:
        d = resolve(i)
        st = d['folder'] / 'study'
        reader = json.load(open(st / 'reader.json')) if (st / 'reader.json').exists() else None
        if i in SIX + QUALITATIVE and reader is None:
            print(f'{i}: no study reader record yet; card made from what is there')
        sh, source = sheet_of(i, reader)
        values = {f: T.V(sh, P, f) for P, f in FIELDS}
        claimed, tested = set(T.L(sh, 'P3', 'claimed')), set(T.L(sh, 'P3', 'tested'))
        c = {'id': i, 'name': NAMES.get(i) or (review[i]['acronym'] if i in review else d['name']) or '',
             'title': d['title'], 'who': d['who'], 'year': int(review[i]['year']) if i in review else int(d['who'][-4:]),
             'from': 'review' if i in review else 'new search', 'status': status[i][0], 'group': status[i][1],
             'group_label': label[status[i][1]], 'classified_by': source, **values,
             'conditions': conditions(i, sh),
             'phd_threats': {t: {'claimed': bool(claimed & tags), 'tested': bool(tested & tags)} for t, tags in PHD.items()}}
        if i in review:
            c['sheet_answers'] = {P: sh['answers'][P].get('answer', '') for P in ('P1', 'P2', 'P3')}
        alg = review[i]['folder'] / 'algorithm' if i in review else None
        if alg is not None and (alg / 'reader.json').exists():           # Phase 1 checklist (the 43 without usable code)
            p1 = json.load(open(alg / 'reader.json'))
            q = json.load(open(alg / '02-quote-check.json'))
            c['checklist'] = {k: (p1['items'].get(k) or {}).get('status') for k in CHECKLIST}
            c['checklist_notes'] = {k: (p1['items'].get(k) or {}).get('missing', '') for k in CHECKLIST}
            c['buildable'] = {'reader': p1.get('verdict'), 'rule': q.get('rule_verdict'), 'effort': p1.get('effort'), 'source': 'Phase 1 reader'}
            c['summary'] = p1.get('summary', '')
        if reader:
            card = reader.get('card') or {}
            c['summary'] = card.get('summary') or c.get('summary', '')
            c['card'] = card
            c['datasets_detail'] = reader.get('datasets', [])
            c['setup'] = reader.get('setup', {})
            c['runs'] = reader.get('runs', {})
            for k in ('experiments', 'code_vs_paper', 'reproduction_notes'):
                if k in reader:
                    c[k] = reader[k]
            if reader.get('checklist'):
                c['checklist'] = {k: (reader['checklist'].get(k) or {}).get('status') for k in CHECKLIST}
                c['checklist_notes'] = {k: (reader['checklist'].get(k) or {}).get('missing', '') for k in CHECKLIST}
                c['buildable'] = {'reader': verdict_of(reader), 'source': 'study reader'}
            qc = st / '02-quote-check.json'
            if qc.exists():
                q = json.load(open(qc))
                c['quote_check'] = {'quotations': q['quotations'], 'found': q['found'], 'problems': q['problems']}
        c['made'] = now()
        save_json(st / 'card.json', c)
        cards.append(c)
    # the rule must give the review's own lists on the 45 sheets
    ref = json.load(open(ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / 'cites-v68.json'))
    for col, key in (('C1', 'gap3_c1'), ('C2', 'gap3_c2'), ('C3', 'gap3_c3')):
        mine = sorted(c['id'] for c in cards if c['from'] == 'review' and c['conditions'][col])
        assert mine == sorted(ref[key]), (col, mine, ref[key])
    save_json(STUDY / 'CARDS.json', {'about': 'One card per design of the Phase 2 study (54); built by scripts/design_eval/study_cards.py',
                                     'made': now(), 'cards': cards})
    flat = ['id', 'name', 'who', 'from', 'status', 'group'] + [f for _, f in FIELDS]
    with open(STUDY / 'CARDS.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(flat + ['C1', 'C2', 'C3', 'buildable'])
        for c in cards:
            w.writerow([('; '.join(map(str, c[f])) if isinstance(c.get(f), list) else c.get(f)) for f in flat]
                       + [c['conditions'][k] for k in ('C1', 'C2', 'C3')] + [(c.get('buildable') or {}).get('reader', 'own code')])
    n = len(cards)
    print(f'{n} cards: {sum(c["status"] == "carried forward" for c in cards)} carried forward, {sum(c["status"] != "carried forward" for c in cards)} not;',
          'conditions on the 45 sheets match the review: yes;',
          'C1/C2/C3 over all:', [sum(c['conditions'][k] for c in cards) for k in ('C1', 'C2', 'C3')])


if __name__ == '__main__':
    main()
