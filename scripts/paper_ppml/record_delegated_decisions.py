#!/usr/bin/env python3
"""Record the two full-text decisions the author delegated (5 October 2026: "do with your judgements"), settled by applying
the criteria as written, in search-ppml/evidence/rescreen/AUTHOR-RESCREEN-DECISIONS-2026-10-05.csv, each logged with its
old value and basis in AUTHOR-RESCREEN-LOG-2026-10-05.jsonl. Running it twice changes nothing.

- 4875 (p4875): INCLUDE. It builds on a blockchain (identity records on an editable ledger) and its authentication decides
  which vehicles take part (IC3b under R2, IC3f), with secure aggregation of the updates (IC1); criteria V9 do not exclude it.
- 236 (p0236): EXCLUDE, OFF-FOCUS. Its extraction record shows every focus angle only mentioned, none as a subject — the
  reason S004 was excluded.

Usage: python3 scripts/paper_ppml/record_delegated_decisions.py
"""
import csv, datetime, json, pathlib

RS = pathlib.Path(__file__).resolve().parents[2] / 'search-ppml' / 'evidence' / 'rescreen'
NOW = datetime.datetime.now().isoformat(timespec='seconds')
WHO = 'settled by applying the criteria as written, at the author\'s request ("do with your judgements", 5 October 2026)'
CHANGES = {
    '4875': {'decision': 'INCLUDE', 'code': '',
             'comment': 'meets every criterion: blockchain in the design and authentication that decides who takes part; ' + WHO},
    '236': {'decision': 'EXCLUDE', 'code': 'OFF-FOCUS',
            'comment': 'focus angles not covered in substance (every angle only mentioned in its extraction record, as S004); ' + WHO},
}


def main():
    f = RS / 'AUTHOR-RESCREEN-DECISIONS-2026-10-05.csv'
    rows = list(csv.DictReader(open(f, encoding='utf-8')))
    for r in rows:
        new = CHANGES.get(r['n'])
        if new and any(r.get(k) != v for k, v in new.items()):
            with open(RS / 'AUTHOR-RESCREEN-LOG-2026-10-05.jsonl', 'a', encoding='utf-8') as fh:
                fh.write(json.dumps({'time': NOW, 'n': int(r['n']), 'changed': 'decision', 'note': WHO,
                                     'old': {k: r.get(k) for k in new}, **new}, ensure_ascii=False) + '\n')
            r.update(new)
            r['decided_at'] = NOW
            print(f"{r['n']}: {new['decision']} {new['code']}")
    with open(f, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    main()
