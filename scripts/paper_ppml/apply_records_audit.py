#!/usr/bin/env python3
"""Apply the corrections of the records audit (records_audit.py) to the study paragraphs, and list the other findings
for a decision by hand.

A finding on a study's own paragraph (type 'own') is the paragraph's sentence as written in
myliteraturereviewpaper/ppml2026/studies/*.md, so its correction replaces that sentence there, if it occurs exactly once.
Findings on other units (prose, group headings, QA6) quote built text, where numbers and citation lists are already
filled in; they are listed for the author's assistant to apply in the parts by hand. Decisions (accept / reject with a
reason) are read from records/DECISIONS.json if present: {"<key> <id>": {"decision": "accept"|"reject"|"edit",
"text": "…", "reason": "…"}}; without a decision a finding on an own unit is accepted as proposed.
Every applied change goes to records/APPLIED.jsonl.

Usage: python3 scripts/paper_ppml/apply_records_audit.py <version> [--apply]
"""
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
STUDIES = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'studies'


def main():
    v, apply = sys.argv[1], '--apply' in sys.argv
    base = ROOT / 'search-ppml' / 'evidence' / f'claims-audit-V{v}' / 'records'
    idx = json.loads((base.parent / 'index.json').read_text(encoding='utf-8'))
    dec_f = base / 'DECISIONS.json'
    decisions = json.loads(dec_f.read_text(encoding='utf-8')) if dec_f.exists() else {}
    files = {f: f.read_text(encoding='utf-8') for f in sorted(STUDIES.glob('*.md'))}
    applied, manual, rejected, problems = [], [], [], []
    for res in sorted((base / 'results').glob('*.json')):
        r = json.loads(res.read_text(encoding='utf-8'))
        key = r['key']
        units = {u['id']: u for u in idx[key]['units']}
        for x in r.get('units', []):
            if x.get('verdict') == 'supported':
                continue
            u = units[x['id']]
            d = decisions.get(f"{key} {x['id']}", {})
            if d.get('decision') == 'reject':
                rejected.append((key, x['id'], d.get('reason', '')))
                continue
            new = d.get('text', x.get('correction', '')) if d.get('decision') == 'edit' else x.get('correction', '')
            if u['type'] != 'own':
                manual.append((key, x['id'], u['type'], u['where'], x['verdict'], x.get('why', ''), u['text'], new))
                continue
            hits = [f for f, t in files.items() if t.count(u['text']) == 1]
            if len(hits) != 1:
                problems.append(f"{key} {x['id']}: own sentence found in {len(hits)} files")
                continue
            f = hits[0]
            old_text = files[f]
            files[f] = old_text.replace(u['text'], new) if new else old_text.replace(u['text'] + ' ', '').replace(u['text'], '')
            applied.append({'key': key, 'id': x['id'], 'file': f.name, 'verdict': x['verdict'], 'why': x.get('why', ''),
                            'sheet': x.get('sheet', ''), 'old': u['text'], 'new': new,
                            'on': datetime.datetime.now().isoformat(timespec='seconds')})
    if apply:
        for f, t in files.items():
            if t != f.read_text(encoding='utf-8'):
                f.write_text(t, encoding='utf-8')
        with (base / 'APPLIED.jsonl').open('a', encoding='utf-8') as log:
            for a in applied:
                log.write(json.dumps(a, ensure_ascii=False) + '\n')
    print(f"own corrections {'applied' if apply else 'to apply'}: {len(applied)} · rejected: {len(rejected)} · "
          f"for a decision by hand: {len(manual)} · problems: {len(problems)}")
    for p in problems:
        print('  PROBLEM', p)
    out = base / 'MANUAL.json'
    out.write_text(json.dumps([dict(zip(['key', 'id', 'type', 'where', 'verdict', 'why', 'unit', 'correction'], m))
                               for m in manual], indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'manual findings -> {out.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
