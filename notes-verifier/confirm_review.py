#!/usr/bin/env python3
"""Record that the author reviewed the answers left ticked by default (the author, 12 October 2026: "i did look at all
the answer. So they are not defaults").

Each answer still ticked "default" becomes "reviewed by the author (left ticked)", with the time of this confirmation and
the author's words; the time the default was first set stays as "verified_on". Answers unticked or changed since are
not touched. The record as it was is kept in notes-verifier/history/_review/. Close the Sheet Reviewer first.

Usage: notes-verifier/.venv/bin/python notes-verifier/confirm_review.py [--apply]
"""
import argparse
import datetime
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECORD = HERE / 'data' / 'sheet-review.json'
STATEMENT = 'i did look at all the answer. So they are not defaults'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    data = json.loads(RECORD.read_text(encoding='utf-8'))
    now = datetime.datetime.now()
    targets = [(k, q) for k, qs in data.items() for q, e in qs.items() if e.get('verified') is True and e.get('how') == 'default']
    if a.apply and targets:
        backup = HERE / 'history' / '_review' / f"sheet-review-before-confirm-{now.strftime('%Y-%m-%d_%H-%M-%S')}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RECORD, backup)
        for k, q in targets:
            data[k][q].update({'how': 'reviewed by the author (left ticked)',
                               'confirmed_on': now.isoformat(timespec='seconds'), 'author_statement': STATEMENT})
        tmp = RECORD.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
        tmp.replace(RECORD)
    print(f"answers ticked by default: {len(targets)}" + (' — now recorded as reviewed by the author' if a.apply
                                                          else '  (check only: nothing written)'))


if __name__ == '__main__':
    main()
