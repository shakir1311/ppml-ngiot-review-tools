#!/usr/bin/env python3
"""Build the test set for the context judge from records only: quotations already proven to be on their page, labelled
by their own words.

  own    a primary study's sheet quotation that speaks of the authors' own work ('we', 'our', 'the proposed', 'this
         paper') and cites nothing ('et al.', '[n]') and names no usual approach ('traditional', 'existing', ...)
  other  a quotation from a primary study's sheet or from the citation links (Docs/LINKS-TABLE-2026-09-29.csv) that
         cites or names earlier or usual work and does not speak of 'we' or 'our'

Writes data/context-set.jsonl: id, key, page, quote, label. Reads no paper.
"""
import csv
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
LINKS = ROOT / 'Docs' / 'LINKS-TABLE-2026-09-29.csv'
PAPERS = ROOT / 'notes-verifier' / 'data' / 'papers.json'
OWN = re.compile(r"\b(?:we|our|ours|us)\b|\bthe proposed\b|\bthis (?:paper|work|article|study)\b", re.I)
OTHER = re.compile(r"\bet al\b|\[\d+(?:[,–-]\s*\d+)*\]|\b(?:traditional|conventional|existing|previous|prior|"
                   r"earlier|has been proposed|have been proposed|baseline)\b", re.I)


def main():
    rnd = random.Random(7)
    cited = {p['key'] for p in json.loads(PAPERS.read_text())['papers'] if 'primary' in p.get('role', '')}
    own, other = [], []
    for f in sorted(SHEETS.glob('*.json')):
        s = json.loads(f.read_text(encoding='utf-8'))
        if s['id'] not in cited:
            continue
        for a in s['answers'].values():
            for e in a.get('evidence') or []:
                q = e.get('quote', '') if isinstance(e, dict) else ''
                if e.get('source') in ('table', 'image') or len(q.split()) < 8:
                    continue
                if OWN.search(q) and not OTHER.search(q):
                    own.append({'key': s['id'], 'page': e['page'], 'quote': q, 'label': 'own'})
                elif OTHER.search(q) and not OWN.search(q):
                    other.append({'key': s['id'], 'page': e['page'], 'quote': q, 'label': 'other', 'from': 'sheet'})
    for r in csv.DictReader(LINKS.open(encoding='utf-8')):
        if r['from_id'] not in cited:
            continue
        for part in r['quotations'].split(' | '):
            m = re.match(r'\[p(\d+)\]\s*(.+)', part.strip())
            if m and len(m.group(2).split()) >= 8 and OTHER.search(m.group(2)) and not OWN.search(m.group(2)):
                other.append({'key': r['from_id'], 'page': int(m.group(1)), 'quote': m.group(2).strip(), 'label': 'other',
                              'from': 'links'})
    seen, rows = set(), []
    for group in (own, other):
        rnd.shuffle(group)
        picked = []
        for x in group:
            if x['quote'] not in seen and sum(1 for y in picked if y['key'] == x['key']) < 2:
                seen.add(x['quote'])
                picked.append(x)
            if len(picked) == 60:
                break
        rows += picked
    for i, r in enumerate(rows):
        r['id'] = f"ctx{i:03d}-{r['key']}"
    (HERE / 'data' / 'context-set.jsonl').write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n',
                                                    encoding='utf-8')
    print(len(rows), 'quotations:', sum(r['label'] == 'own' for r in rows), 'own,', sum(r['label'] == 'other' for r in rows),
          'other', f"({len(own)} own and {len(other)} other available)")


if __name__ == '__main__':
    main()
