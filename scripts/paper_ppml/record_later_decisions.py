#!/usr/bin/env python3
"""Record the author's decisions taken after the second-screening decisions (record_check_decisions.py) on records of
search-ppml/CHECK-DECISIONS-2026-10-05.csv. Each change is logged with the old row and the author's words in
search-ppml/LATER-DECISIONS-LOG-2026-10-05.jsonl. Running it twice changes nothing.

- 1838 (S004, Nguyen et al. 2021): excluded at full text, OFF-FOCUS (EC7). Its extraction record shows every focus angle
  only "mentioned" (S4), so it does not cover an angle as a subject or in substance (IC3). Proposed after the sample check
  of the first downloads; the author: "ok/ process all of them and let me know the result" (5 October 2026).

- 574 (p0574) and 5351 (p5351): excluded under criteria V9 (a primary study must build on a blockchain; neither has a ledger),
  the author's answer of 5 October 2026 "Blockchain must be in the design".

Usage: python3 scripts/paper_ppml/record_later_decisions.py
"""
import csv, datetime, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
CHANGES = {'1838': {'decision': 'EXCLUDE', 'code': 'OFF-FOCUS', 'focus': 'no', 'focus_parts': '',
                    'decided': 'the author: "ok" to excluding S004 for consistency with IC3 (5 October 2026)'},
           # criteria V9 (apply_fulltext_reasons.py): a primary study must build on a blockchain; these two have no ledger
           '574': {'decision': 'EXCLUDE', 'code': 'NO-BLOCKCHAIN',
                   'decided': 'the author: "Blockchain must be in the design" (criteria V9, 5 October 2026); no ledger in the design'},
           '5351': {'decision': 'EXCLUDE', 'code': 'NO-BLOCKCHAIN',
                    'decided': 'the author: "Blockchain must be in the design" (criteria V9, 5 October 2026); no ledger in the design'}}


def main():
    f = P / 'CHECK-DECISIONS-2026-10-05.csv'
    rows = list(csv.DictReader(open(f, encoding='utf-8')))
    log = P / 'LATER-DECISIONS-LOG-2026-10-05.jsonl'
    for r in rows:
        ch = CHANGES.get(r['n'])
        if ch and any(r.get(k) != v for k, v in ch.items()):
            with open(log, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps({'time': datetime.datetime.now().isoformat(timespec='seconds'), 'n': r['n'], 'old': dict(r), 'new': ch},
                                    ensure_ascii=False) + '\n')
            r.update(ch)
            print(f"{r['n']} ({r['corpus_id']}): {ch['decision']} {ch['code']}")
    with open(f, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    main()
