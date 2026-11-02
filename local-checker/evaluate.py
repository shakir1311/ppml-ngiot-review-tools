#!/usr/bin/env python3
"""How well the checker did on the test set: per group, and over a range of thresholds. Prints counts and ids only."""
import json
import sys
from collections import defaultdict
from pathlib import Path

rows = [json.loads(l) for l in Path(sys.argv[1] if len(sys.argv) > 1 else 'data/calibration-results.jsonl').read_text().splitlines()]
ambiguous = [r for r in rows if r['expected'] == 'ambiguous']
rows = [r for r in rows if r['expected'] != 'ambiguous']      # the paper itself says both: not scored


def verdict(r, ts, tc):
    return 'supported' if r['entails'] >= ts else 'contradicted' if r['contradicts'] >= tc else 'not found'


for ts in (0.5, 0.7, 0.8, 0.9, 0.95):
    g = defaultdict(lambda: [0, 0])
    for r in rows:
        ok = (verdict(r, ts, 0.8) == 'supported') == (r['expected'] == 'supported')
        g[r['group']][0] += ok
        g[r['group']][1] += 1
    true = [r for r in rows if r['expected'] == 'supported']
    false = [r for r in rows if r['expected'] != 'supported']
    missed = sum(verdict(r, ts, 0.8) != 'supported' for r in true)
    wrong = sum(verdict(r, ts, 0.8) == 'supported' for r in false)
    print(f"threshold {ts}: " + ' | '.join(f'{k} {a}/{b}' for k, (a, b) in sorted(g.items()))
          + f" || true statements missed {missed}/{len(true)}, false statements passed {wrong}/{len(false)}")
print(f'\n{len(ambiguous)} statement(s) not scored: the paper says both')
print('\nhand set at 0.8:')
for r in rows:
    if r['group'] == 'hand':
        v = verdict(r, 0.8, 0.8)
        flag = '' if (v == 'supported') == (r['expected'] == 'supported') else '   <-- WRONG'
        print(f"  {r['id']:16} expected {r['expected']:13} got {v:12} (entails {r['entails']:.2f} p{r['entails_page']}, contradicts {r['contradicts']:.2f} p{r['contradicts_page']}){flag}")
