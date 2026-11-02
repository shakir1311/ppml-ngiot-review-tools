#!/usr/bin/env python3
"""Second, independent check of the corrected evidence sheets (11–12 October 2026).

Two kinds of item per study go to a second reader with full-text access:
  1. every tag value the correction pass changed (before → after, with the first reader's reason);
  2. every value that says something is absent: "absent", "not stated", "none", "no", false, an empty list, or an
     answer that starts "not stated" — absence is the hardest claim to prove (a word search missed "multi-input
     function encryption" for "functional encryption"), and these values feed the paper's "no study …" statements.

Writes search-ppml/evidence/sheet-fix/check2/packets/<key>.md. Reads only records.
Usage: python3 scripts/paper_ppml/sheet_check2_packets.py [key ...]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / 'search-ppml' / 'evidence'
SHEETS = EV / 'sheets'
FIX = EV / 'sheet-fix'
OUT = FIX / 'check2' / 'packets'
ABSENT = {'absent', 'not stated', 'not-stated', 'none', 'none-stated', 'no', 'not-addressed', 'no-check', 'n/a'}
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sheet_fix_packets import codebook, titles


def main(keys):
    rules, qt = codebook(), titles()
    first = {}
    for line in (FIX / 'APPLIED.jsonl').read_text(encoding='utf-8').splitlines():
        a = json.loads(line)
        first.setdefault((a['key'], a['q']), a)
    keys = keys or sorted(p.stem for p in SHEETS.glob('*.json'))
    total_c = total_a = 0
    for key in keys:
        sheet = json.loads((SHEETS / f'{key}.json').read_text(encoding='utf-8'))
        changes, absences = [], []
        for q, ans in sheet['answers'].items():
            log = first.get((key, q))
            before = (log['before'].get('values') or {}) if log else {}
            for f, v in (ans.get('values') or {}).items():
                if log and before.get(f) != v:
                    changes.append((q, f, before.get(f), v, log.get('why', '')))
                vals = v if isinstance(v, list) else [v]
                if v is False or vals == [] or any(str(x).lower() in ABSENT for x in vals) \
                        or any(str(x).lower() in ABSENT for x in vals if isinstance(x, str)):
                    absences.append((q, f, v))
            if str(ans.get('answer', '')).lower().startswith('not stated'):
                absences.append((q, '(answer)', 'not stated'))
        out = [f'# Second check — {key}', '', f"Kind: {sheet.get('kind')}", '']
        out += ['## 1. Tag values changed by the correction pass (confirm or overturn each)', '']
        out += [f"- {q} `{f}`: {json.dumps(b, ensure_ascii=False)} → {json.dumps(a, ensure_ascii=False)} — first reader: {w}"
                for q, f, b, a, w in changes] or ['- (none)']
        out += ['', '## 2. Values that say something is absent (confirm each by searching the whole paper)', '']
        out += [f"- {q} `{f}` = {json.dumps(v, ensure_ascii=False)}" for q, f, v in absences] or ['- (none)']
        out += ['', '## The current answers these items belong to', '']
        for q in sorted({x[0] for x in changes} | {x[0] for x in absences}):
            ans = sheet['answers'][q]
            out += [f'### {q} — {qt.get(q, ("", ""))[0]}', '', f'Allowed values: {qt.get(q, ("", ""))[1]}', '',
                    f'Decision rules: {rules.get(q, "")}', '', ans.get('answer', ''), '',
                    'Values: ' + json.dumps(ans.get('values') or {}, ensure_ascii=False), '']
            out += [f"- [p{e.get('page')}] \"{e.get('quote', '')}\"" for e in ans.get('evidence') or [] if isinstance(e, dict)]
            out.append('')
        (OUT / f'{key}.md').write_text('\n'.join(out), encoding='utf-8')
        total_c += len(changes); total_a += len(absences)
    print(f'{len(keys)} packets; tag changes {total_c}; absence values {total_a}')


if __name__ == '__main__':
    main(sys.argv[1:])
