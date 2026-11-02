#!/usr/bin/env python3
"""Audit what the review says about each included study against its evidence sheet — the record the author verified
answer by answer against the full text (12 October 2026). Records only: no paper is read (workspace CLAUDE.md).

Built on claims_audit.py: run `claims_audit.py prepare <v>` first; this script takes its index.json and keeps, for each
included study, the units that state something about the study in words — its own paragraph (own), other sentences that
cite it (prose), the heading of its group (group) and the inconsistency reported for it (qa6). Table rows and counts are
not included: they are generated from the sheet's values by the build (thematic.py, data.py) and guarded by
check_claims.py.

prepare <v>   claims-audit-V<v>/records/packets/<key>.md: the units (ids as in index.json), then the whole corrected
              sheet — every answer with its values and its quotations with pages.
check <v>     every unit of every packet has a result in records/results/<key>.json with a verdict from the allowed list;
              a verdict other than 'supported' carries the sheet answer it rests on and a corrected wording.
findings <v>  records/FINDINGS.csv and a count by verdict.

Options: --delta      only the units of claims-audit-V<v>/DELTA.json (`claims_audit.py delta <v> <prev>`): the sentences
                       changed since the last audited version;
         --no-quotes  packets without the sheets' quotations: the answers and values only (the records' own words,
                       verified by the author), so that no text of a paper reaches the auditor.

Usage: python3 scripts/paper_ppml/records_audit.py prepare|check|findings <version> [--delta] [--no-quotes]
"""
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
EV = ROOT / 'search-ppml' / 'evidence'
SHEETS = EV / 'sheets'
TYPES = ('own', 'prose', 'group', 'qa6')
VERDICTS = {'supported', 'partly', 'unsupported', 'contradicted', 'misattributed'}
TITLES = {'P1': 'System, setting and tiers', 'P2': 'Privacy', 'P3': 'Ledger', 'P4': 'Checking', 'P5': 'Threats',
          'P6': 'Evaluation', 'P7': "Regulation and the ledger's data", 'P8': 'Limitations',
          'S1': 'Scope and method', 'S2': 'The five layers', 'S3': 'Privacy mechanisms covered',
          'S4': "The review's angles", 'S5': 'Regulation', 'S6': 'What it concludes',
          'S7': 'Open issues and future directions', 'S8': 'Limitations of the survey'}


def base(v):
    return EV / f'claims-audit-V{v}' / 'records'


DELTA_ONLY, NO_QUOTES = '--delta' in sys.argv, '--no-quotes' in sys.argv


def selected(v):
    idx = json.loads((EV / f'claims-audit-V{v}' / 'index.json').read_text(encoding='utf-8'))
    changed = json.loads((EV / f'claims-audit-V{v}' / 'DELTA.json').read_text(encoding='utf-8'))['packets'] if DELTA_ONLY else None
    out = {}
    for k, d in idx.items():
        if d.get('kind') not in ('primary', 'secondary') or not (SHEETS / f'{k}.json').exists():
            continue
        units = [u for u in d['units'] if u['type'] in TYPES
                 and (changed is None or u['id'] in set((changed.get(k) or {}).get('units', [])))]
        if units:
            out[k] = (d, units)
    return out


def prepare(v):
    od = base(v) / 'packets'
    od.mkdir(parents=True, exist_ok=True)
    n = 0
    for k, (d, units) in selected(v).items():
        sheet = json.loads((SHEETS / f'{k}.json').read_text(encoding='utf-8'))
        L = [f'# Records audit packet {k}', '', f"**{d['kind'].capitalize()} study** — {d['title']}", '',
             '## Units: what the review says about this study (judge each against the sheet below)', '']
        for u in units:
            L += [f"### {u['id']} — {u['where']} — {u['type']}", u['text'], '']
            n += 1
        L += ['## The evidence sheet (verified by the author against the full text)', '']
        if NO_QUOTES:
            L += ['(The quotations are left out of this packet: judge from the answers and values, which the author verified.)', '']
        for q, a in sheet['answers'].items():
            L.append(f"### {q} — {TITLES.get(q, '')}")
            L.append(a.get('answer', '').strip())
            vals = a.get('values') or {}
            if vals:
                L.append('Values: ' + '; '.join(f'{f} = {json.dumps(x, ensure_ascii=False)}' for f, x in vals.items()))
            for e in ([] if NO_QUOTES else a.get('evidence') or []):
                src = f" ({e['source']})" if e.get('source') else ''
                L.append(f"- p{e.get('page')}{src}: \"{e.get('quote', '')}\"")
            L.append('')
        (od / f'{k}.md').write_text('\n'.join(L), encoding='utf-8')
    print(f'{len(selected(v))} packets, {n} units -> {od.relative_to(ROOT)}')


def check(v):
    problems, done = [], 0
    for k, (d, units) in selected(v).items():
        f = base(v) / 'results' / f'{k}.json'
        if not f.exists():
            problems.append(f'{k}: no result')
            continue
        r = json.loads(f.read_text(encoding='utf-8'))
        got = {x.get('id'): x for x in r.get('units', [])}
        for u in units:
            x = got.get(u['id'])
            if not x:
                problems.append(f"{k} {u['id']}: no verdict")
            elif x.get('verdict') not in VERDICTS:
                problems.append(f"{k} {u['id']}: verdict {x.get('verdict')!r}")
            elif x['verdict'] != 'supported' and not (x.get('sheet') and x.get('correction') is not None):
                problems.append(f"{k} {u['id']}: a finding needs 'sheet' and 'correction'")
        extra = set(got) - {u['id'] for u in units}
        if extra:
            problems.append(f'{k}: verdicts for units not in the packet: {sorted(extra)}')
        done += 1
    print(f'{done} results checked; {len(problems)} problem(s)')
    for p in problems[:40]:
        print('  ', p)
    return not problems


def findings(v):
    rows, count = [], {}
    for k, (d, units) in selected(v).items():
        f = base(v) / 'results' / f'{k}.json'
        if not f.exists():
            continue
        text = {u['id']: u for u in units}
        for x in json.loads(f.read_text(encoding='utf-8')).get('units', []):
            count[x['verdict']] = count.get(x['verdict'], 0) + 1
            if x['verdict'] != 'supported' and x.get('id') in text:
                u = text[x['id']]
                rows.append({'key': k, 'id': x['id'], 'where': u['where'], 'type': u['type'], 'verdict': x['verdict'],
                             'unit': u['text'], 'sheet': x.get('sheet', ''), 'why': x.get('why', ''),
                             'correction': x.get('correction', '')})
    out = base(v) / 'FINDINGS.csv'
    with out.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['key', 'id', 'where', 'type', 'verdict', 'unit', 'sheet', 'why', 'correction'])
        w.writeheader()
        w.writerows(rows)
    print(' · '.join(f'{k} {n}' for k, n in sorted(count.items())), f'| {len(rows)} findings -> {out.relative_to(ROOT)}')


if __name__ == '__main__':
    cmd, v = [a for a in sys.argv[1:] if not a.startswith('--')][:2]
    {'prepare': prepare, 'check': check, 'findings': findings}[cmd](v)
