#!/usr/bin/env python3
"""Check that every record field the generators and the recounts read exists in the records (the lesson of 9 November 2026: the
field zk_on_chain went with the merge of the answers on 15 October 2026; the rule that read it kept answering 'no', the recount
shared the rule, and Table VII's aggregation-proof row read 0 for three weeks while every check passed).

Scans the scripts that build and check the paper (PIPELINE) for every field read of the forms V(sheet, 'Pn', 'field'), L(…), one(k, 'Pn', 'field'),
vals(k, 'Pn', 'field'), count(name, …, 'Pn', 'field') and field(k, 'field'), and the field lists of claims_audit.py, and reports
every field name that no sheet in search-ppml/evidence/sheets/ carries, with file and line. Exit code 1 if any.

Usage: python3 scripts/paper_ppml/fields_check.py
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts' / 'paper_ppml'
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
PIPELINE = ('thematic.py', 'data.py', 'data_v68.py', 'experiment_v82.py', 'figures.py', 'figures_v68.py', 'verify_tables.py', 'verify_v68.py',
            'check_claims_v68.py', 'claims_audit.py', 'build.py', 'build_supporting.py', 'links.py', 'refs.py', 'release_package.py')
READ = re.compile(r"\b(?:V|L|one|vals|count)\([^\n]*?'([PS])\d'\s*,\s*'([A-Za-z_][A-Za-z0-9_]*)'")   # V(sh, 'P3', 'roles'), one(k, 'P4', 'x') …
FIELD_CALL = re.compile(r"\bfield\(\s*\w+\s*,\s*'([A-Za-z_][A-Za-z0-9_]*)'")   # field(k, 'code')
ALLOW = set()                                                               # (kind, field) pairs accepted with a reason, e.g. ('S', 'x')


def main():
    present = {'P': set(), 'S': set()}                                        # the fields of the designs' sheets and of the surveys'
    for p in SHEETS.glob('*.json'):
        sh = json.loads(p.read_text(encoding='utf-8'))
        kind = 'S' if sh.get('kind') == 'secondary' else 'P'
        for a in sh.get('answers', {}).values():
            present[kind] |= set(((a or {}).get('values') or {}).keys())
    reads = {}
    for p in sorted(SCRIPTS.glob('*.py')):
        if p.name not in PIPELINE:
            continue
        for n, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            for kind, f in READ.findall(line) + [('*', f) for f in FIELD_CALL.findall(line)]:     # field(k, …) searches every answer
                reads.setdefault((kind, f), []).append(f'{p.name}:{n}')
    sys.path.insert(0, str(SCRIPTS))
    import claims_audit as CA                                               # noqa: E402
    for q, fs in {**CA.PRIMARY_FIELDS, **CA.SECONDARY_FIELDS}.items():
        for f in fs:
            reads.setdefault((q[0], f), []).append(f'claims_audit.py ({q} list)')
    present['*'] = present['P'] | present['S']
    ghosts = {kf: w for kf, w in reads.items() if kf[1] not in present[kf[0]] and kf not in ALLOW}
    for (kind, f), where in sorted(ghosts.items()):
        who = {'P': 'design', 'S': 'survey', '*': ''}[kind]
        print(f'no {who} sheet carries the field {f!r}, read at: ' + ', '.join(where[:6]) + (' …' if len(where) > 6 else ''))
    print(f'{len(reads)} field read(s) in the scripts; {len(present["P"])} design and {len(present["S"])} survey field(s) in the sheets; {len(ghosts)} ghost(s)')
    return 1 if ghosts else 0


if __name__ == '__main__':
    sys.exit(main())
