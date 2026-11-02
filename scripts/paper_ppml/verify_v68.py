#!/usr/bin/env python3
"""Recount, straight from the sheets and by its own code, every cell of the five tables of the simple frame
(surveys_v68, cost, trusted, evaluation, gap3) and the numbers of the gap, and compare them with what data_v68.py wrote.
Usage: python3 scripts/paper_ppml/verify_v68.py
"""
import csv, json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import thematic as T
SH = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in (ROOT / 'search-ppml' / 'evidence' / 'sheets').glob('*.json')}
KIND = {r['corpus_id']: r['kind'] for r in csv.DictReader(open(ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8'))}
PRIM = sorted(k for k in SH if KIND[k] == 'primary'); SEC = sorted(k for k in SH if KIND[k] == 'secondary')
s = json.loads((B / 'stats.json').read_text(encoding='utf-8'))
c = json.loads((B / 'cites.json').read_text(encoding='utf-8'))
problems = []

def tags(k, f):
    for a in SH[k]['answers'].values():
        if f in (a.get('values') or {}):
            v = a['values'][f]; return v if isinstance(v, list) else [v]
    return []

def table(key):
    rows = [l for l in (B / 'tables' / f'{key}.md').read_text(encoding='utf-8').splitlines() if l.startswith('| ')]
    sp = lambda l: [c.strip() for c in l.strip().strip('|').split(' | ')]
    return sp(rows[0]), [sp(r) for r in rows[1:]]

def ids_in(cell):
    return set(re.findall(r'@([\w-]+)', cell))

def count_in(cell):
    m = re.match(r'(\d+)', cell); return int(m.group(1)) if m else 0

def check_rows(key, expect):
    """expect: {row label: set of ids}; the table's row must show the same count and the same ids"""
    head, rows = table(key)
    got = {r[0]: r[-1] for r in rows}
    for lab, ids in expect.items():
        if lab not in got:
            if not ids: continue                                   # a row no design falls under is dropped from the table
            problems.append(f'{key}: row "{lab}" missing'); continue
        if count_in(got[lab]) != len(ids) or (ids and ids_in(got[lab]) != set(ids)):
            problems.append(f'{key}: row "{lab}": table {count_in(got[lab])} {sorted(ids_in(got[lab]))} ≠ sheets {len(ids)} {sorted(ids)}')

# cost
COST = {'Computation or training time': 'computation-time', 'Latency': 'latency', 'Throughput': 'throughput', 'Storage or memory': 'storage', 'Communication': 'communication', 'Gas': 'gas', 'Energy': 'energy', 'No cost reported': 'none'}
exp = {f'Cost reported: {lab}': {k for k in PRIM if v in tags(k, 'costs_reported')} for lab, v in COST.items()}
WHERE = {'On device-class hardware': 'device-class', 'On servers or workstations': 'server-workstation', 'In simulation': 'simulation', 'Where not stated': 'not-stated'}
exp.update({f'Measured: {lab}': {k for k in PRIM if tags(k, 'cost_where') == [v]} for lab, v in WHERE.items()})
check_rows('cost', exp)
# trusted
TR = {'No party': 'none', 'A trusted authority or key centre': 'trusted-authority-key-centre', 'A certificate authority': 'certificate-authority', 'The server, aggregator or task publisher': 'server-aggregator', 'Non-colluding servers': 'non-colluding-servers', 'An enclave': 'enclave-TEE', 'An honest majority of a committee or of the nodes': 'committee-honest-majority', 'A trusted set-up': 'trusted-setup', 'Not stated': 'not-stated'}
check_rows('trusted', {lab: {k for k in PRIM if v in tags(k, 'trusted')} for lab, v in TR.items()})
check_rows('trusted', {'Other': {k for k in PRIM if any(str(x).startswith('other') for x in tags(k, 'trusted'))}})
# evaluation
ENV = {'Real devices or a test bed': 'real-devices', 'Emulation': 'emulation', 'Simulation': 'simulation', 'An experiment on data sets on servers': 'server-experiment', 'No experiment': 'none', 'Not stated': 'not-stated'}
exp = {f'Environment: {lab}': {k for k in PRIM if v in tags(k, 'environment')} for lab, v in ENV.items()}
sc = {k: (tags(k, 'scale') or [None])[0] for k in PRIM}
exp['Largest scale: up to 10 clients or nodes'] = {k for k in PRIM if isinstance(sc[k], int) and sc[k] <= 10}
exp['Largest scale: 11 to 100 clients or nodes'] = {k for k in PRIM if isinstance(sc[k], int) and 11 <= sc[k] <= 100}
exp['Largest scale: 101 to 1,000 clients or nodes'] = {k for k in PRIM if isinstance(sc[k], int) and 101 <= sc[k] <= 1000}
exp['Largest scale: not stated'] = {k for k in PRIM if not isinstance(sc[k], int)}
exp['Named baselines compared'] = {k for k in PRIM if tags(k, 'baselines')}
exp['Code available'] = {k for k in PRIM if tags(k, 'code') == ['yes']}
check_rows('evaluation', exp)
# surveys_v68: every cell against the sheet
head, rows = table('surveys_v68'); COLS = ['fabric', 'privacy', 'trust', 'regulation', 'poisoning', 'malicious_fake', 'free_riding']
M = {'subject': 'Yes', 'mentioned': 'Partial', 'absent': 'No'}
seen = set()
for r in rows:
    if not ids_in(r[0]):                                   # the last row is this review (V75): all Yes by construction, not a survey
        if r[0] != 'This review' or r[2:] != ['Yes'] * len(COLS): problems.append(f'surveys_v68: unexpected row {r[:2]}')
        continue
    k = next(iter(ids_in(r[0]))); seen.add(k)
    want = [M.get((tags(k, c) or [''])[0], '?') for c in COLS]
    if r[2:] != want: problems.append(f'surveys_v68: {k}: table {r[2:]} ≠ sheets {want}')
if seen != set(SEC): problems.append(f'surveys_v68: surveys listed {len(seen)} ≠ {len(SEC)}')
_st = json.loads((pathlib.Path(__file__).resolve().parents[2] / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / 'stats.json').read_text(encoding='utf-8'))
for f in COLS:                                             # the sv_* numbers quoted in Section II against the sheets
    for grade, word in (('subject', 'yes'), ('mentioned', 'partial'), ('absent', 'no')):
        n = sum(1 for k in SEC if (tags(k, f) or [''])[0] == grade)
        if _st.get(f'sv_{f}_{word}') != n: problems.append(f'sv_{f}_{word}: stats {_st.get(f"sv_{f}_{word}")} ≠ sheets {n}')
# gap3, with the conditions recomputed by the earlier frame's own rules
C = {k: T.gap_conditions(k, SH[k]) for k in PRIM}
c1 = {k for k in PRIM if C[k]['C1']}; c2 = {k for k in PRIM if C[k]['C2']}; c3 = {k for k in PRIM if C[k]['C4a'] or C[k]['C4b'] or C[k]['C4c']}
meet = {k: (k in c1) + (k in c2) + (k in c3) for k in PRIM}
check_rows('gap3', {'C1': c1, 'C2': c2, 'C3': c3, 'All three': {k for k in PRIM if meet[k] == 3}, 'Any two': {k for k in PRIM if meet[k] == 2}})
for key, val in (('gap3_c1', len(c1)), ('gap3_c2', len(c2)), ('gap3_c3', len(c3)), ('gap3_all', sum(m == 3 for m in meet.values())), ('gap3_two', sum(m == 2 for m in meet.values())),
                 ('trusted_any_party', sum(1 for k in PRIM if any(T.O(x) not in ('none', 'not-stated') for x in tags(k, 'trusted')))),
                 ('sv_all_yes', sum(1 for k in SEC if all(tags(k, c) == ['subject'] for c in COLS))),
                 ('sv_core_and_threats', sum(1 for k in SEC if all(tags(k, c) == ['subject'] for c in COLS if c != 'regulation'))),
                 ('answers_total', sum(len(SH[k]['answers']) for k in SH)), ('quotes_total', sum(len(a.get('evidence') or []) for k in SH for a in SH[k]['answers'].values()))):
    if s.get(key) != val: problems.append(f'stats {key}: {s.get(key)} ≠ recount {val}')
# years
head, rows = table('years_v68')
for r in rows:
    y = int(r[0]); ks = [k for k in PRIM if int(next(x['year'] for x in csv.DictReader(open(ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')) if x['corpus_id'] == k)) == y]
    want = [y, len(ks), sum(1 for k in SEC if int(next(x['year'] for x in csv.DictReader(open(ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')) if x['corpus_id'] == k)) == y), sum(1 for k in ks if k in c3), sum(1 for k in ks if k in c1)]
    if [int(x) for x in r] != want: problems.append(f'years_v68 {y}: table {r} ≠ records {want}')
# the grids' data and the conditions table
import figures_v68 as FV
sg = json.loads((B / 'figures' / 'survey_coverage.data.json').read_text(encoding='utf-8'))
refs = json.loads((ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json').read_text(encoding='utf-8'))
year = {r['corpus_id']: int(r['year']) for r in csv.DictReader(open(ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8'))}
want = {FV.label(k, refs, year): [M.get((tags(k, c) or [''])[0], 'No') for c in COLS] for k in SEC}
got = {l: m for l, m in sg['rows']}
if got != want: problems.append('survey_coverage figure data ≠ sheets: ' + str([l for l in want if got.get(l) != want[l]]))
pg = json.loads((B / 'figures' / 'prim_coverage.data.json').read_text(encoding='utf-8'))
def grade(k):                                             # the grades recomputed here, from the record, by the stated rules
    c = T.gap_conditions(k, SH[k]); sh = SH[k]
    v = lambda q, f: (tags(k, f) or [None])[0]
    claimed = T.threats_of(k, sh, 'claimed')
    named = T.GAP_THREATS['C4a'] | T.GAP_THREATS['C4b'] | T.GAP_THREATS['C4c']
    return {'C1': 'Yes' if c['C1'] else ('Partial' if v('P1', 'network_measured') == 'yes' or v('P1', 'cost_where') == 'server-workstation' else 'No'),
            'C2': 'Yes' if c['C2'] else ('Partial' if T.hidden_kind(sh) in ('hidden', 'noised') else 'No'),
            'C3': 'Yes' if (c['C4a'] or c['C4b'] or c['C4c']) else ('Partial' if claimed & named else 'No')}
wantp = {FV.label(k, refs, year): [grade(k)[code] for _, code in FV.COND] for k in PRIM}
gotp = {l: m for l, m in pg['rows']}
if gotp != wantp: problems.append('prim_coverage figure data ≠ sheets: ' + str([l for l in wantp if gotp.get(l) != wantp[l]]))
head, rows = table('conditions')
for r in rows:
    k = next(iter(ids_in(r[0]))); g = grade(k)
    want = [g[code] for _, code in FV.COND] + [str(sum(x == 'Yes' for x in g.values()))]
    if r[1:] != want: problems.append(f'conditions {k}: table {r[1:]} ≠ sheets {want}')
print(f'{len(problems)} difference(s)'); [print('  ', p) for p in problems]
raise SystemExit(1 if problems else 0)
