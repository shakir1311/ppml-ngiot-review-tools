#!/usr/bin/env python3
"""Record the author's decisions on the full-text verdicts of the full second screening, in the column "author" of
search-ppml/evidence/rescreen/RESCREEN-FULLTEXT-2026-10-05.csv, as "<INCLUDE|EXCLUDE> <CODE>: <the author's reason>".
`rescreen.py fulltext-result` keeps that column and applies it over the proposed decision. Each change is logged with the
old value and the author's words in search-ppml/evidence/rescreen/AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl. Running it twice
changes nothing.

- p0358 and p0434: only the unedited early-access versions exist (Crossref, 5 October 2026: no volume or issue). The
  author: "remove these or give me links to download if not downloaded already" — removed, as NOT-FINAL-VERSION.

Usage: python3 scripts/paper_ppml/record_fulltext_author_decisions.py
"""
import csv, datetime, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
RS = ROOT / 'search-ppml' / 'evidence' / 'rescreen'
DECISIONS = {
    'p0358': 'EXCLUDE NOT-FINAL-VERSION: only the unedited early-access version exists (Crossref 5 Oct 2026: no volume or issue); removed by the author',
    'p0434': 'EXCLUDE NOT-FINAL-VERSION: only the unedited early-access version exists (Crossref 5 Oct 2026: no volume or issue); removed by the author',
}


def main():
    f = RS / 'RESCREEN-FULLTEXT-2026-10-05.csv'
    rows = list(csv.DictReader(open(f, encoding='utf-8')))
    log = RS / 'AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl'
    for r in rows:
        new = DECISIONS.get(r['id'])
        if new and r.get('author') != new:
            with open(log, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps({'time': datetime.datetime.now().isoformat(timespec='seconds'), 'id': r['id'],
                                     'old': r.get('author', ''), 'new': new}, ensure_ascii=False) + '\n')
            r['author'] = new
            print(f"{r['id']}: {new}")
    with open(f, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    main()
