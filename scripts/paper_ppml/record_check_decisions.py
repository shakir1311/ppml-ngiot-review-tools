#!/usr/bin/env python3
"""Record the author's decisions of 5 October 2026 on the records reinstated by the independent second screening and on
the two other-methods records ("proceed with all your recommendations to include/exclude").

1. search-ppml/CHECK-DECISIONS-2026-10-05.csv — one row per record the second screening flagged and that went to full
   text (the author's original screening record stays unchanged): how it had been excluded, whether its full text was
   retrieved, the full-text decision with its code, and the answers used by the review (from the full-text proposals,
   search-ppml/evidence/checks/fulltext-<id>.json).
2. The other-methods records in the author's files: n2438 (record 100006) included, without the zero-knowledge angles
   (no zero-knowledge proof in the paper); O059 (100005) excluded with the proposed reason accepted. Changes are logged with
   the old values (AUTHOR-DECISIONS-LOG-2026-10-04.jsonl, AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl).
The screening app must be closed.

Usage: python3 scripts/paper_ppml/record_check_decisions.py
"""
import csv, datetime, json, pathlib

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
NOW = datetime.datetime.now().isoformat(timespec='seconds')
WHO = "the author accepted the full-text proposals (5 October 2026)"
CHECK = [  # n, corpus id, excluded by, retrieved, decision, code, type, focus_parts, zk_proves
    ('1166', 'S019', 'default exclusion', 'yes', 'INCLUDE', '', 'secondary', 'poisoning; malicious or fake participants; free riding; verification; blockchain', ''),
    ('1838', 'S004', 'default exclusion', 'yes', 'INCLUDE', '', 'secondary', 'poisoning; malicious or fake participants; blockchain', ''),
    # later excluded by the author (OFF-FOCUS): record_later_decisions.py, which must run after this script
    ('574', 'p0574', 'default exclusion', 'yes', 'INCLUDE', '', 'primary', 'poisoning; malicious or fake participants; zero-knowledge proofs', 'other'),
    ('5351', 'p5351', 'automated focus rule', 'yes', 'INCLUDE', '', 'primary', 'malicious or fake participants; verification', ''),
    ('1628', 'p1628', 'default exclusion', 'yes', 'EXCLUDE', 'PRIVACY-INCIDENTAL', 'secondary', 'poisoning', ''),
    ('5129', 'p5129', 'automated focus rule', 'yes', 'EXCLUDE', 'OFF-FOCUS', 'secondary', '', ''),
    ('1101', '', 'default exclusion', 'no', 'NOT-RETRIEVED', '', '', '', ''),
]


def main():
    with open(P / 'CHECK-DECISIONS-2026-10-05.csv', 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['n', 'corpus_id', 'excluded_by', 'retrieved', 'decision', 'code', 'type', 'privacy', 'focus', 'focus_parts', 'zk_proves', 'ngiot', 'basis', 'decided'])
        for n, cid, by, ret, dec, code, typ, parts, zk in CHECK:
            ok = dec == 'INCLUDE'
            w.writerow([n, cid, by, ret, dec, code, typ, 'yes' if ok else ('no' if code == 'PRIVACY-INCIDENTAL' else ''),
                        'yes' if parts else ('no' if dec == 'EXCLUDE' else ''), parts, zk, 'yes' if ok else '',
                        f'search-ppml/evidence/checks/fulltext-{cid}.json' if cid else 'search-ppml/evidence/checks/NOT-RETRIEVED-2026-10-05.json', WHO])
    # the two other-methods records
    D = P / 'AUTHOR-DECISIONS-2026-10-04.csv'
    rows = list(csv.DictReader(open(D, encoding='utf-8')))
    by = {r['n']: r for r in rows}
    with open(P / 'AUTHOR-DECISIONS-LOG-2026-10-04.jsonl', 'a', encoding='utf-8') as log:
        r = by['100006']
        old = {k: r[k] for k in ('decision', 'code', 'focus_parts', 'comment')}
        r['decision'], r['code'], r['focus_parts'], r['focus'] = 'INCLUDE', '', 'malicious or fake participants; blockchain', 'yes'
        r['comment'] = ('Included at the author\'s instruction (5 Oct 2026): meets IC1-IC6 (CKKS-encrypted updates; Hyperledger Fabric smart contracts '
                        'keep trust scores and quarantine low-trust devices); the zero-knowledge angles are removed, as the paper has no zero-knowledge proof.')
        log.write(json.dumps({'time': NOW, 'n': 100006, 'changed': 'decision by the author (accepted proposal)', 'note': f'old {old}',
                              **{k: r[k] for k in ('decision', 'code', 'type', 'privacy', 'focus', 'focus_parts', 'ngiot', 'comment')}}, ensure_ascii=False) + '\n')
        r = by['100005']
        r['comment'] = r['comment'].replace('Proposed by Claude Code for your review:', 'Reason proposed by Claude Code and accepted by the author (5 Oct 2026):')
        log.write(json.dumps({'time': NOW, 'n': 100005, 'changed': 'reason accepted by the author', 'code': r['code'], 'comment': r['comment']}, ensure_ascii=False) + '\n')
    tmp = D.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    tmp.replace(D)
    # the full-text answers of n2438
    FT = P / 'AUTHOR-FULLTEXT-2026-10-05.csv'
    ft = list(csv.DictReader(open(FT, encoding='utf-8')))
    fields = list(ft[0])
    if not any(r['n'] == '100006' for r in ft):
        d = by['100006']
        new = {k: '' for k in fields}
        new.update({k: d.get(k, '') for k in fields if k in d})
        new.update({'n': '100006', 'decision': 'INCLUDE', 'code': '', 'type': 'primary', 'privacy': 'yes', 'focus': 'yes',
                    'focus_parts': 'malicious or fake participants; blockchain', 'zk_proves': '', 'ngiot': 'yes', 'decided_at': NOW})
        ft.append(new)
        with open(P / 'AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'time': NOW, 'n': 100006, 'changed': 'full-text decision by the author (accepted proposal)', 'decision': 'INCLUDE',
                                  'focus_parts': new['focus_parts']}, ensure_ascii=False) + '\n')
        with open(FT, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(ft)
    print('recorded: CHECK-DECISIONS (7 rows), n2438 included, O059 reason accepted')


if __name__ == '__main__':
    main()
