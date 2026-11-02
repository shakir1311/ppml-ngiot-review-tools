#!/usr/bin/env python3
"""Settle the points the readers left open in the five evidence sheets added after the second screening (5 October 2026):
p5351, p0574, n2438 (primary) and S004, S019 (secondary).

1. A design without a ledger (P3 ledger = none) leaves the other ledger fields empty instead of "other: none", so that the
   "other" counts of the ledger table stay true (p5351, p0574). EXTRACTION-GUIDE.md states the rule.
2. Item QA6 (consistency), from the inconsistencies the reader recorded in each sheet's remarks and confirmed on the page:
   p5351 and n2438 contradict their own claims ('no'); p0574's conclusion overstates what its case study tests ('partial').
   Added later: p4875 ('no'), included at the author's request (record_delegated_decisions.py).
Every change is appended to search-ppml/evidence/SHEET-CORRECTIONS-2026-10-05.json. Running it twice changes nothing.

Usage: python3 scripts/paper_ppml/settle_new_studies.py
"""
import datetime, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
E = ROOT / 'search-ppml' / 'evidence'
NOW = datetime.datetime.now().isoformat(timespec='seconds')
NO_LEDGER = ('p5351', 'p0574')
QA6_NO = {
    'p5351': 'the server computes cosine similarity, norms and statistics of each update (p5, p7), yet the paper states that the server cannot see gradient plaintext (p9); DP is claimed in the security model (p8) but absent from the implementation (p9)',
    'n2438': 'the abstract claims significantly lower false positives (p1), but the false positive rate equals that of logistic regression (p14, p17); the data sets differ between the text, Table 2 and Table 3 (p7); thresholds differ between Tables 6 and 8 (p8-9)',
    'p4875': 'the abstract claims confidentiality and integrity of the parameters (p1) and the conclusion that the scheme resists various attacks (p6), but only confidentiality against semi-honest parties is proved and the experiments measure running time only',
}
QA6_PARTIAL = {
    'p0574': 'the conclusion says the case study validates the effectiveness of the proposed framework and solutions (p10), but only membership inference is tested, not the defences against poisoning and backdoors (p8-9)',
}


def main():
    log_f = E / 'SHEET-CORRECTIONS-2026-10-05.json'
    log = json.loads(log_f.read_text(encoding='utf-8'))
    for cid in NO_LEDGER:
        f = E / 'sheets' / f'{cid}.json'
        if not f.exists():                                      # since excluded (sheets/_excluded/), already settled
            continue
        sh = json.loads(f.read_text(encoding='utf-8'))
        v = sh['answers']['P3']['values']
        assert v['ledger'] == ['none'], cid
        for field in ('platform', 'consensus', 'on_chain', 'roles'):
            if v.get(field) == ['other: none']:
                log.append({'time': NOW, 'id': cid, 'key': 'P3', 'field': field, 'old': v[field], 'new': [],
                            'why': 'No ledger (P3 ledger = none): the other ledger fields stay empty, so that "other" counts only real other values (settle_new_studies.py).'})
                v[field] = []
        f.write_text(json.dumps(sh, indent=1, ensure_ascii=False), encoding='utf-8')
    qa_f = E / 'QA-CONSISTENCY-2026-10-05.json'
    qa = json.loads(qa_f.read_text(encoding='utf-8'))
    for level, items in (('no', QA6_NO), ('partial', QA6_PARTIAL)):
        for cid, why in items.items():
            if qa[level].get(cid) != why:
                qa[level][cid] = why
                log.append({'time': NOW, 'id': cid, 'key': 'QA6', 'field': 'consistency', 'old': None, 'new': level,
                            'why': 'Inconsistency found by the reader and confirmed on the page (settle_new_studies.py): ' + why})
    qa_f.write_text(json.dumps(qa, indent=1, ensure_ascii=False), encoding='utf-8')
    log_f.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding='utf-8')
    g = E / 'EXTRACTION-GUIDE.md'
    t = g.read_text(encoding='utf-8')
    rule = '\n\nA design without a ledger: `ledger` = none, and `platform`, `consensus`, `on_chain` and `roles` are empty lists (not "other: none").\n'
    if 'A design without a ledger' not in t:
        g.write_text(t.rstrip('\n') + rule, encoding='utf-8')
    print('settled:', ', '.join(NO_LEDGER), '(no ledger);', ', '.join(QA6_NO), '(QA6 no);', ', '.join(QA6_PARTIAL), '(QA6 partial)')


if __name__ == '__main__':
    main()
