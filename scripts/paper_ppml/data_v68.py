#!/usr/bin/env python3
"""The tables and numbers of the simple frame (V68, 15 October 2026) that the earlier data module does not produce, computed
from the evidence sheets in the form of 15 October (one answer per review question): the related-surveys table, the costs
the designs report, the parties they still trust, how they are evaluated, and the three conditions of the research gap.
Run after scripts/paper_ppml/data.py (which writes build/stats.json and the tables V68 reuses); adds to build/stats.json
and writes build/tables/{surveys_v68,cost,trusted,evaluation,gap3}.md and parts-v68/figcaps.json.
Usage: python3 scripts/paper_ppml/data_v68.py
"""
import collections, json, os, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import data as D                       # md_table, sheets, read
import thematic as T                   # V, L, cites, gap_conditions, names
B = D.B
slug = D.slug


def main():
    S = D.sheets()
    fin = D.read(D.P / 'FINAL-STUDIES-2026-10-05.csv')
    prim, sec = T.split(S, fin)
    year = {r['corpus_id']: int(r['year']) for r in fin}
    s = json.loads((B / 'stats.json').read_text(encoding='utf-8'))
    order = lambda keys: sorted(keys, key=lambda k: (year[k], k))

    # ---- related surveys: what each treats -------------------------------------------------------------------------
    cols = [('fabric', 'SQ1: NG-IoT fabric'), ('privacy', 'SQ2: Privacy mechanisms'), ('trust', 'SQ2: Blockchain and checking'),
            ('regulation', 'SQ2: Data-protection law'), ('poisoning', 'SQ3: Poisoning'),
            ('malicious_fake', 'SQ3: Malicious or fake participants'), ('free_riding', 'SQ3: Free riding')]     # each column named by its review question (V78)
    rows, allyes = [], []
    for key in [x for x in s if x.startswith('sv_') and x.rsplit('_', 1)[-1] in ('yes', 'partial', 'no')]:
        s[key] = 0                                   # fresh counts: stats.json is read back, so a second run must not add to the first
    for f, _ in cols:
        for x in ('yes', 'partial', 'no'): s[f'sv_{f}_{x}'] = 0
    for k in order(sec):
        g = [T.MARK.get(T.V(S[k], 'S1', f), '?') for f, _ in cols]
        rows.append([f'[@{k}]', year[k]] + g)
        if all(x == 'Yes' for x in g):
            allyes.append(k)
        for (f, _), x in zip(cols, g):
            s[f'sv_{f}_{x.lower()}'] = s.get(f'sv_{f}_{x.lower()}', 0) + 1
    rows.append(['This review', '—'] + ['Yes'] * len(cols))     # the last row: what this review treats (V75); outside the counts and the grid
    s['sv_all_yes'] = len(allyes)
    s['sv_core_yes'] = sum(1 for k in sec if all(T.V(S[k], 'S1', f) == 'subject' for f in ('fabric', 'privacy', 'trust')))
    s['sv_threats_yes'] = sum(1 for k in sec if all(T.V(S[k], 'S1', f) == 'subject' for f in ('poisoning', 'malicious_fake', 'free_riding')))
    s['sv_core_and_threats'] = sum(1 for k in sec if all(T.V(S[k], 'S1', f) == 'subject' for f in ('fabric', 'privacy', 'trust', 'poisoning', 'malicious_fake', 'free_riding')))
    D.md_table('surveys_v68', 'Subjects treated by each included survey, by review question',
               ['Survey', 'Year'] + [c for _, c in cols], rows, note='Yes: a subject of its own (a section, subsection or table); Partial: mentioned; No: absent. The last row is this review.')

    # ---- eligibility criteria in plain words (V79): the paper's table; the full criteria as recorded, with their codes, go to the supporting document
    D.md_table('criteria_simple', 'Eligibility criteria', ['Rule', 'Criterion'], [
        ['Included, all of', 'The privacy of machine learning (its data, models or updates) in a next-generation IoT setting: IoT with 5G or 6G, edge, fog or multi-access edge computing, and the settings built on them.'],
        ['', 'A design (a primary study that proposes, builds or evaluates a privacy-preserving method, system, protocol or attack, or measures leakage) or a survey (a review, mapping study or systematisation of knowledge).'],
        ['', 'Treats at least one of: verification of training, updates or aggregation; zero-knowledge proofs about the learning; a blockchain or distributed ledger; poisoning; malicious or fake participants; free riding. A design must build on a blockchain or distributed ledger.'],
        ['', 'A peer-reviewed journal, conference or magazine article in English, with the full text available, published from 2020 to the date of the search.'],
        ['', 'A survey is published in 2024 or later, or is cited at least 100 times.'],
        ['Excluded, any of', 'Retracted; a duplicate or an earlier version of an included study; only an unedited early-access version available.'],
        ['', 'Not a full paper (editorial, poster, extended abstract, thesis, book) or not a study (position or opinion paper).'],
        ['', 'Privacy, the learning or the setting is incidental: for a design, no privacy mechanism or privacy analysis of its own; for a survey, privacy named but not treated.'],
        ['', 'A design without a blockchain or distributed ledger; a study that treats none of the subjects above in substance.'],
        ['', 'A survey published before 2024 and cited fewer than 100 times.']], widths=[16, 84])

    # ---- costs reported and where measured -------------------------------------------------------------------------
    COST = [('computation-time', 'Computation or training time'), ('latency', 'Latency'), ('throughput', 'Throughput'), ('storage', 'Storage or memory'),
            ('communication', 'Communication'), ('gas', 'Gas'), ('energy', 'Energy'), ('none', 'No cost reported')]
    WHERE = [('device-class', 'On device-class hardware'), ('server-workstation', 'On servers or workstations'), ('simulation', 'In simulation'), ('not-stated', 'Where not stated')]
    rows = []
    for v, lab in COST:
        ks = [k for k in prim if v in T.L(S[k], 'P1', 'costs_reported')]
        s[f'cost_{slug(v)}'] = len(ks)
        rows.append([f'Cost reported: {lab}', f'{len(ks)} {T.cites(ks)}' if ks else '0'])
    for v, lab in WHERE:
        ks = [k for k in prim if T.V(S[k], 'P1', 'cost_where') == v]
        s[f'where_{slug(v)}'] = len(ks)
        rows.append([f'Measured: {lab}', f'{len(ks)} {T.cites(ks)}' if ks else '0'])
    s['cost_any'] = sum(1 for k in prim if any(v != 'none' for v in T.L(S[k], 'P1', 'costs_reported')))
    D.md_table('cost', 'Costs reported by the designs, and where they were measured',
               ['Feature', 'Designs'], rows)

    # ---- parties still trusted --------------------------------------------------------------------------------------
    TRUST = [('none', 'No party'), ('trusted-authority-key-centre', 'A trusted authority or key centre'), ('certificate-authority', 'A certificate authority'),
             ('server-aggregator', 'The server, aggregator or task publisher'), ('non-colluding-servers', 'Non-colluding servers'),
             ('enclave-TEE', 'An enclave'), ('committee-honest-majority', 'An honest majority of a committee or of the nodes'),
             ('trusted-setup', 'A trusted set-up'), ('other', 'Other'), ('not-stated', 'Not stated')]
    rows = []
    for v, lab in TRUST:
        ks = [k for k in prim if any(T.O(x) == v for x in T.L(S[k], 'P2', 'trusted'))]
        s[f'trusted_{slug(v)}'] = len(ks)
        rows.append([lab, f'{len(ks)} {T.cites(ks)}' if ks else '0'])
    s['trusted_any_party'] = sum(1 for k in prim if any(T.O(x) not in ('none', 'not-stated') for x in T.L(S[k], 'P2', 'trusted')))
    D.md_table('trusted', 'Parties the designs still trust', ['Party', 'Designs'], rows)

    # ---- how the designs are evaluated ---------------------------------------------------------------------------
    ENV = [('real-devices', 'Real devices or a test bed'), ('emulation', 'Emulation'), ('simulation', 'Simulation'),
           ('server-experiment', 'An experiment on data sets on servers'), ('none', 'No experiment'), ('not-stated', 'Not stated')]
    rows = []
    for v, lab in ENV:
        ks = [k for k in prim if v in T.L(S[k], 'P3', 'environment')]
        s[f'env_{slug(v)}'] = len(ks)
        rows.append([f'Environment: {lab}', f'{len(ks)} {T.cites(ks)}' if ks else '0'])
    bands = [('up to 10', lambda n: n <= 10), ('11 to 100', lambda n: 11 <= n <= 100), ('101 to 1,000', lambda n: 101 <= n <= 1000), ('over 1,000', lambda n: n > 1000)]
    scale = {k: T.V(S[k], 'P3', 'scale') for k in prim}
    for lab, f in bands:
        ks = [k for k in prim if isinstance(scale[k], int) and f(scale[k])]
        s[f'scale_{slug(lab)}'] = len(ks)
        rows.append([f'Largest scale: {lab} clients or nodes', f'{len(ks)} {T.cites(ks)}' if ks else '0'])
    ks = [k for k in prim if not isinstance(scale[k], int)]
    s['scale_not_stated'] = len(ks)
    rows.append(['Largest scale: not stated', f'{len(ks)} {T.cites(ks)}' if ks else '0'])
    ks = [k for k in prim if T.L(S[k], 'P3', 'baselines')]
    rows.append(['Named baselines compared', f'{len(ks)} {T.cites(ks)}'])
    ks = [k for k in prim if T.V(S[k], 'P3', 'code') == 'yes']
    rows.append(['Code available', f'{len(ks)} {T.cites(ks)}' if ks else '0'])
    D.md_table('evaluation', 'How the designs are evaluated', ['Feature', 'Designs'], rows)

    # ---- the three conditions of the gap ------------------------------------------------------------------------
    C = {k: T.gap_conditions(k, S[k]) for k in prim}          # {C1, C2, C3, C4a, C4b, C4c, C5} of the earlier frame
    c1 = {k for k in prim if C[k]['C1']}
    c2 = {k for k in prim if C[k]['C2']}
    c3 = {k for k in prim if C[k]['C4a'] or C[k]['C4b'] or C[k]['C4c']}
    meet = {k: sum((k in c1, k in c2, k in c3)) for k in prim}
    rows = [['C1', 'A cost of the design is measured on device-class hardware', f'{len(c1)} {T.cites(c1)}'],
            ['C2', 'No party that checks or aggregates sees an individual update', f'{len(c2)} {T.cites(c2)}' if c2 else '0'],
            ['C3', 'A test of the design by an attack of poisoning, malicious or fake participants or free riding is reported', f'{len(c3)} {T.cites(c3)}'],
            ['All three', 'C1, C2 and C3 together', f'{sum(1 for k in prim if meet[k] == 3)} {T.cites([k for k in prim if meet[k] == 3])}' if any(meet[k] == 3 for k in prim) else '0'],
            ['Any two', 'Two of the three', f'{sum(1 for k in prim if meet[k] == 2)} {T.cites([k for k in prim if meet[k] == 2])}' if any(meet[k] == 2 for k in prim) else '0']]
    s.update({'gap3_c1': len(c1), 'gap3_c2': len(c2), 'gap3_c3': len(c3), 'gap3_all': sum(1 for k in prim if meet[k] == 3),
              'gap3_two': sum(1 for k in prim if meet[k] == 2), 'gap3_max': max(meet.values()),
              'gap3_c2_hidden_only': sum(1 for k in prim if C[k]['C2']), 'gap3_c2_lawful_only': sum(1 for k in prim if C[k]['C5'])})
    D.md_table('gap3', 'The three conditions of the agenda, and the designs meeting each', ['Condition', 'Meaning', 'Designs'], rows)
    (B / 'cites-v68.json').write_text(json.dumps({'gap3_c1': sorted(c1), 'gap3_c2': sorted(c2), 'gap3_c3': sorted(c3),
                                                 'gap3_two': sorted(k for k in prim if meet[k] == 2), 'gap3_all': sorted(k for k in prim if meet[k] == 3),
                                                 'sv_all_yes': allyes}, indent=1), encoding='utf-8')
    # the citation lists of the frame: added to cites.json so {{C:key}} works
    cl = json.loads((B / 'cites.json').read_text(encoding='utf-8'))
    cl.update(json.loads((B / 'cites-v68.json').read_text(encoding='utf-8')))
    (B / 'cites.json').write_text(json.dumps(cl, indent=1), encoding='utf-8')
    # ---- the quality questionnaire of the designs only, and the AI-use table with the steps of 15 October ---------------
    rows = [l for l in (B / 'tables' / 'qa_checklist.md').read_text(encoding='utf-8').splitlines()]
    D.md_table('qa_checklist_v68', 'The six quality-appraisal questions',
               ['Item', 'Question', 'Description'], [[c.strip() for c in r.strip().strip('|').split(' | ')] for r in rows if r.startswith('| QA')])
    # the AI-use table is written by data.py alone (one line per use, 2 November 2026)
    cl = json.loads((B / 'cites.json').read_text(encoding='utf-8'))
    cl.update({'trusted_none': sorted(k for k in prim if any(T.O(x) == 'none' for x in T.L(S[k], 'P2', 'trusted'))),
               'env_real_devices': sorted(k for k in prim if 'real-devices' in T.L(S[k], 'P3', 'environment')),
               'where_device_class': sorted(k for k in prim if T.V(S[k], 'P1', 'cost_where') == 'device-class'),
               'cost_gas': sorted(k for k in prim if 'gas' in T.L(S[k], 'P1', 'costs_reported')),
               'scale_over_100': sorted(k for k in prim if isinstance(scale[k], int) and scale[k] > 100),
               'sv_core_and_threats': sorted(k for k in sec if all(T.V(S[k], 'S1', f) == 'subject' for f in ('fabric', 'privacy', 'trust', 'poisoning', 'malicious_fake', 'free_riding'))),
               'trusted_not_stated': sorted(k for k in prim if 'not-stated' in T.L(S[k], 'P2', 'trusted'))})
    (B / 'cites.json').write_text(json.dumps(cl, indent=1), encoding='utf-8')
    D.md_table('items', 'Data items: the three answers of a design and the one answer of a survey, with the tags that fill the tables.',
               ['Answer', 'Question', 'What is recorded', 'Tags'],
               [['P1', 'SQ1', 'The NG-IoT setting; the FL arrangement; who trains, aggregates, verifies and keeps the ledger, on which tier; whether a cost was measured on device-class hardware or a real or emulated link; which costs are reported and where measured', 'settings, enablers, arrangement, device cost measured, network cost measured, costs reported, where measured'],
                ['P2', 'SQ2', 'The privacy mechanisms, what each hides and from whom, and their reported cost; the ledger type, platform and consensus, what is on-chain and what the ledger or its contracts do; the parties still trusted; laws named, personal data on the chain, erasure', 'mechanisms, protects, hidden from, ledger, platform, consensus, on-chain, roles, trusted, laws, personal data on chain, erasure'],
                ['P3', 'SQ3', 'What is checked about updates, training or aggregation, by whom, whether the checker sees the update, what a zero-knowledge proof shows; threats claimed and threats tested, with the defences; data sets, baselines, code, evaluation environment and scale; the limitations the authors state', 'checked, checker, checker sees update, ZKP used, ZKP shows, claimed, tested, defences, data sets, baselines, code, environment, scale'],
                ['S1', 'Related surveys', 'What the survey treats: the NG-IoT fabric, privacy mechanisms, the blockchain and the checking of updates, attacks and defences, data-protection law; poisoning, malicious or fake participants, free riding', 'each: subject, mentioned or absent']])
    qp = B / 'tables' / 'qa_primary.md'
    qp.write_text(qp.read_text(encoding='utf-8').replace('{{TAB:qa_checklist}}', '{{TAB:qa_checklist_v68}}'), encoding='utf-8')
    cp = B / 'tables' / 'chars_primary.md'                                    # the designs table: an "other: …" value reads "other"
    cp.write_text(re.sub(r'other: [^|,]+', 'other', cp.read_text(encoding='utf-8')), encoding='utf-8')
    pv = B / 'tables' / 'privacy.md'                                          # the body spells TEE out once, in the background
    pv.write_text(re.sub(r'[Tt]rusted execution environments? \(TEE\)', 'TEE', pv.read_text(encoding='utf-8')), encoding='utf-8')
    for name, pairs in (('ledger', [('Section III-E', 'Section IV-C')]), ('ai_use', [('Section IX-B', 'Section VII-A')])):   # the frame's section numbers
        p = B / 'tables' / f'{name}.md'; t = p.read_text(encoding='utf-8')
        for a, b in pairs: t = t.replace(a, b)
        p.write_text(t, encoding='utf-8')
    import figures_v68
    refs = json.loads((ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json').read_text(encoding='utf-8'))
    dy, vy, srows, drows = figures_v68.main(s, S, fin, refs)
    rows = []
    for y in range(2020, 2027):
        ks = [k for k in prim if year[k] == y]
        rows.append([y, dy[y], vy[y], sum(1 for k in ks if k in c3), sum(1 for k in ks if k in c1)])
        s[f'yr_{y}_designs'], s[f'yr_{y}_surveys'] = dy[y], vy[y]
    s['c3_2024_on'] = sum(r[3] for r in rows if r[0] >= 2024)                    # designs testing a named attack, 2024 or later
    s['c1_year_max'] = max(r[4] for r in rows)                                   # the most device-class-measured designs in any one year
    D.md_table('years_v68', 'Included studies per year',
               ['Year', 'Designs', 'Surveys', 'Designs with a test of a named attack', 'Designs with a cost on device-class hardware'], rows)
    rows = []
    for k in sorted(prim, key=lambda k: figures_v68.order_key(k, S, refs, year)):
        g = figures_v68.grades_of(k, S[k])
        rows.append([f'[@{k}]'] + [g[code] for _, code in figures_v68.COND] + [sum(v == 'Yes' for v in g.values())])
    D.md_table('conditions', 'The designs against the three conditions, as their records show them (Yes: the condition as the agenda targets it; Partial: a step towards it; No: not shown). C1 a cost measured on device-class hardware (Partial: on a real or emulated link, or on servers); C2 no party that checks or aggregates sees an update (Partial: kept from the aggregator or noised, but a checking party sees it); C3 a test of the design against poisoning, malicious or fake participants or free riding is reported (Partial: the threat is addressed, no test is reported). Met counts the Yes grades.',
               ['Study', 'C1', 'C2', 'C3', 'Met'], rows)
    s['cond_max_met'] = max(r[-1] for r in rows)
    s['cond_zero'] = sum(1 for r in rows if r[-1] == 0)
    s['cond_any_partial'] = sum(1 for r in rows if r[-1] == 0 and any(x == 'Partial' for x in r[1:-1]))
    for name in ('cost', 'trusted', 'evaluation'):                       # a row no design falls under says nothing: dropped
        p = B / 'tables' / f'{name}.md'; lines = p.read_text(encoding='utf-8').splitlines()
        p.write_text('\n'.join(l for l in lines if not (l.startswith('| ') and re.search(r'\| 0 \|$', l))) + '\n', encoding='utf-8')
    th = B / 'tables' / 'threats.md'; t = th.read_text(encoding='utf-8')
    t = re.sub(r'^Table: .*$', 'Table: Threats the designs address, and those they report a test against', t, count=1, flags=re.M)
    th.write_text(t.replace('| Threat | Claimed | Test reported |', '| Threat | Addressed | Test reported |'), encoding='utf-8')
    s['answers_total'] = sum(len(S[k]['answers']) for k in S)
    s['answers_primary'] = sum(len(S[k]['answers']) for k in prim)
    s['quotes_total'] = sum(len(a.get('evidence') or []) for k in S for a in S[k]['answers'].values())
    s['tags_total'] = sum(len(a.get('values') or {}) for k in S for a in S[k]['answers'].values())
    s['prim_before_2024'] = sum(1 for k in prim if year[k] < 2024)
    s['prim_2024_on'] = sum(1 for k in prim if year[k] >= 2024)
    s['set_single'] = sum(1 for v in ('communication_network', 'uav_space', 'maritime', 'supply_chain') if s.get(f'set_{v}') == 1)
    (B / 'stats.json').write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding='utf-8')
    caps = {'roadmap': 'Roadmap of the review: from each question\'s data items, through the sections that answer it, to the open issue, the condition and the deliverable',
            'years': 'Included studies per year, designs and surveys shown apart.',
            'survey_coverage': 'Subjects treated by each included survey, graded as in {{TAB:surveys_v68}}',
            'prim_coverage': 'What each design shows towards the three conditions, graded Yes, Partial or No from its record',
            'design': 'Reference design of the agenda in three layers: gateways train on their own data and send each update as secret shares with answers on labelled test rows; validators mark the answers and sum the shares jointly, seeing no whole update; the ledger records fingerprints and verdicts only. A clean-label backdoor passes the test and stays open.',
            'prisma': 'Identification, screening and inclusion of the studies, as the PRISMA 2020 flow with both searches combined',
            'architecture': 'Where learning, privacy protection, checking and the ledger sit on the tiers of an NG-IoT deployment, and where the threats come in',
            'threats': 'Threats the designs address, and those for which they report a test of the design by an attack, with the attacks on the learning apart from the properties of the system.'}
    for folder in (os.environ.get('PPML_PARTS_NAME', 'parts-v78'),):      # the version being built; delivered versions are never rebuilt in place
        d = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / folder
        if d.is_dir():
            fc = d / 'figcaps.json'                                    # keep the captions other generators merged in (experiment_v82.py)
            kept = json.loads(fc.read_text(encoding='utf-8')) if fc.exists() else {}
            kept.update(caps)
            fc.write_text(json.dumps(kept, indent=1), encoding='utf-8')
    print('V68 tables: surveys_v68, cost, trusted, evaluation, gap3 |', {k: s[k] for k in ('sv_all_yes', 'sv_core_and_threats', 'cost_any', 'where_device_class', 'trusted_any_party', 'trusted_none', 'env_real_devices', 'gap3_c1', 'gap3_c2', 'gap3_c3', 'gap3_all', 'gap3_two')})


if __name__ == '__main__':
    main()
