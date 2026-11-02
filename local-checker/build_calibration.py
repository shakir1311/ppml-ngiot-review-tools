#!/usr/bin/env python3
"""Build the test set that shows how far the fact checker can be trusted, before it is used on anything that matters.

  quote    sheet quotations already proven to be on their page (true statements; expected: supported)
  altered  the same quotations with one number or one key word changed (false statements; expected: not supported)
  hand     statements written from the records whose truth is settled by quotations proven to be on their page
           (data/calibration-hand.jsonl; expected label given there)

Reads only the evidence sheets (records). Writes data/calibration.jsonl.
"""
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
SWAPS = [('honest-but-curious', 'malicious'), ('permissioned', 'permissionless'), ('consortium', 'public'),
         ('decentralized', 'centralized'), ('centralized', 'decentralized'), ('decentralised', 'centralised'),
         ('increases', 'decreases'), ('increase', 'decrease'), ('decreases', 'increases'), ('higher', 'lower'),
         ('lower', 'higher'), ('cannot', 'can'), ('does not', 'does'), ('without', 'with'), ('before', 'after'),
         ('after', 'before'), ('untrusted', 'trusted'), ('trusted', 'untrusted'), ('off-chain', 'on-chain'),
         ('on-chain', 'off-chain'), ('encrypted', 'unencrypted'), ('always', 'never'), ('never', 'always'),
         ('outperforms', 'underperforms'), ('more', 'fewer'), ('less', 'more'), ('private', 'public'), ('public', 'private')]
NUMBER = re.compile(r'(?<![\w.])(\d+(?:\.\d+)?)(?![\w.]*\])')


def alter(quote, rnd):
    nums = [m for m in NUMBER.finditer(quote) if m.group(1) not in ('1', '2')]
    if nums:
        m = rnd.choice(nums)
        n = m.group(1)
        new = (f'{float(n) * 1.5 + 7:.{len(n.split(".")[1])}f}' if '.' in n else str(int(n) * 3 + 7))
        return quote[:m.start(1)] + new + quote[m.end(1):], f'number {n} -> {new}'
    low = quote.lower()
    for a, b in SWAPS:
        i = re.search(r'\b' + re.escape(a) + r'\b', low)
        if i:
            changed = quote[:i.start()] + b + quote[i.end():]
            if re.search(r'\b(\w+) and \1\b', changed.lower()):      # 'with and with': nonsense, not a clear falsehood
                continue
            return changed, f'{a} -> {b}'
    return None, None


def main():
    rnd = random.Random(11)
    rows = []
    for f in sorted(SHEETS.glob('*.json')):
        s = json.loads(f.read_text(encoding='utf-8'))
        quotes = [e for a in s['answers'].values() for e in (a.get('evidence') or [])
                  if isinstance(e, dict) and e.get('source') not in ('table', 'image') and len(e.get('quote', '').split()) >= 8]
        for e in rnd.sample(quotes, min(2, len(quotes))):
            rows.append({'id': f'{s["id"]}-q{len(rows)}', 'key': s['id'], 'claim': e['quote'], 'group': 'quote',
                         'expected': 'supported'})
            changed, how = alter(e['quote'], rnd)
            if changed:
                rows.append({'id': f'{s["id"]}-a{len(rows)}', 'key': s['id'], 'claim': changed, 'group': 'altered',
                             'expected': 'not supported', 'change': how})
    hand = HERE / 'data' / 'calibration-hand.jsonl'
    if hand.exists():
        rows += [dict(json.loads(l), group='hand') for l in hand.read_text(encoding='utf-8').splitlines() if l.strip()]
    (HERE / 'data' / 'calibration.jsonl').write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n',
                                                     encoding='utf-8')
    from collections import Counter
    print(len(rows), 'statements:', dict(Counter(r['group'] for r in rows)))


if __name__ == '__main__':
    main()
