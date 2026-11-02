#!/usr/bin/env python3
"""Numbers and method tables of the PPML review (paper V29 onwards), computed from the review's records; nothing typed
by hand.

Inputs (search-ppml/): MERGE-CHECK-2026-10-04.json and MERGED-RECORDS-2026-10-04.csv (identification, duplicates,
automated rules), exports/PROVENANCE-2026-10-04.tsv (each search: source, file, SHA-256, records, date, who ran it),
AUTHOR-DECISIONS-2026-10-04.csv (the author's screening decisions and answers), PREFILL-2026-10-04.csv (the cue-word
pre-fill), OTHER-METHODS-2026-10-04.csv, AUTHOR-FULLTEXT-2026-10-05.csv, CORRECTIONS-2026-10-05.csv,
FINAL-STUDIES-2026-10-05.csv; the evidence sheets (evidence/sheets/*.json) for the counts of the synthesis; and the
search strings (scripts/search_ppml/strings.py); the supplementary search R-S1, recorded since 8 October 2026
(search-ppml/evidence/regulation-search/, read by scripts/search_ppml/rs1.py; strings in strings_regulation.py).

Outputs (myliteraturereviewpaper/ppml2026/build/): stats.json ({{N:key}} values), tables/<key>.md, figures/<key>.png
(figures by scripts/paper_ppml/figures.py; thematic tables by scripts/paper_ppml/thematic.py).

Usage: python3 scripts/paper_ppml/data.py
"""
import collections, csv, json, pathlib, re, sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
for d in ('tables', 'figures'):
    (B / d).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / 'scripts' / 'search_ppml'))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import strings as STR                                 # noqa: E402
import strings_regulation as SREG                     # noqa: E402  (the supplementary search R-S1)
import rs1 as RS1                                     # noqa: E402

slug = lambda x: re.sub(r'[^a-z0-9]+', '_', str(x).lower()).strip('_')


def read(p, **kw):
    return list(csv.DictReader(open(p, encoding='utf-8'), **kw))


def sheets():
    out = {}
    for f in sorted((P / 'evidence' / 'sheets').glob('*.json')):
        out[f.stem] = json.loads(f.read_text(encoding='utf-8'))
    return out


# ------------------------------------------------------------------ PRISMA and method counts
def prisma_stats():
    s = {}
    mc = json.loads((P / 'MERGE-CHECK-2026-10-04.json').read_text())
    R = {r['n']: r for r in read(P / 'MERGED-RECORDS-2026-10-04.csv')}
    F = {r['n']: r for r in read(P / 'PREFILL-2026-10-04.csv')}
    D = {d['n']: d for d in read(P / 'AUTHOR-DECISIONS-2026-10-04.csv')}
    K = {k['n']: k for k in read(P / 'OTHER-METHODS-2026-10-04.csv')}
    FT = {f['n']: f for f in read(P / 'AUTHOR-FULLTEXT-2026-10-05.csv')}
    prov = read(P / 'exports' / 'PROVENANCE-2026-10-04.tsv', delimiter='\t')
    used = [p for p in prov if p['file'] in mc['files']]
    s['searches_run'] = len(used)
    s['search_date'] = '4 October 2026' if all(p['searched_local_time'].startswith('2026-10-04') for p in used) else 'see provenance'
    s['searches_by_author'] = sum(p['run_by'] == 'the author' for p in used)
    s['search_month'] = s['search_date'].split(' ', 1)[1] if s['search_date'][0].isdigit() else s['search_date']   # the paper gives the month only
    grp = collections.Counter()
    for p in used:
        k = next(v for pre, v in (('P-S1', 'ps1'), ('P-S2', 'ps2'), ('P-A', 'pa'), ('P-B', 'pb'), ('P-C', 'pc')) if p['search'].startswith(pre))
        grp[k] += int(p['records'])
    for k, v in grp.items():
        s[f'rec_{k}'] = v
    s['id_total'], s['id_scopus'], s['id_ieee'], s['id_sd'] = mc['identified_total'], mc['identified']['Scopus'], mc['identified']['IEEE Xplore'], mc['identified']['ScienceDirect']
    s['dup'], s['unique'], s['auto'], s['screened'] = mc['duplicates'], mc['unique'], mc['auto_excluded'], mc['to_screen']
    s['auto_ieee'], s['auto_notpaper'], s['auto_focus'] = mc['auto_excluded_ieee_rule'], mc['auto_excluded_not_a_paper'], mc['auto_excluded_focus']
    s['not_in_scopus'] = mc['not_in_scopus']
    s['screen_survey_arm'], s['screen_primary_arm'], s['screen_both_arms'] = mc['to_screen_by_arm']['survey'], mc['to_screen_by_arm']['primary'], mc['to_screen_both_arms']
    screen = [n for n, r in R.items() if not r['auto_excluded']]
    assert len(screen) == s['screened']
    dec = [n for n in screen if D.get(n, {}).get('decision')]
    s['author_decided'] = len(dec)
    s['author_excluded'] = sum(D[n]['decision'] == 'EXCLUDE' for n in dec)
    s['included_search'] = sum(D[n]['decision'] == 'INCLUDE' for n in dec)
    date = angle = angle_topic = 0
    for n in screen:
        if n in dec:
            continue
        typ, foc = D.get(n, {}).get('type') or F[n]['type'], D.get(n, {}).get('focus') or F[n]['focus']
        y, c = int(R[n]['year'] or 0), (int(R[n]['cited']) if R[n]['cited'] else None)
        if typ == 'secondary' and y < 2024 and (c is None or c < 100):
            date += 1
        elif foc == 'no':
            angle += 1
            if typ == 'secondary' and (F[n]['privacy'], F[n]['ngiot']) == ('yes', 'yes'):
                angle_topic += 1             # surveys on the topic left out only because no focus angle was named
        else:
            raise SystemExit(f'record {n} undecided')
    s['default_date'], s['default_angle'] = date, angle
    s['default_angle_survey_topic'] = angle_topic
    s['default_excluded'] = date + angle
    s['ta_excluded'] = s['author_excluded'] + s['default_excluded']
    keys = ('type', 'privacy', 'focus', 'ngiot')
    s['prefill_answers'] = len(dec) * len(keys)
    s['prefill_changed'] = sum(1 for n in dec for k in keys if D[n].get(k) and D[n][k] != F[n].get(k))
    s['prefill_records_changed'] = sum(1 for n in dec if any(D[n].get(k) and D[n][k] != F[n].get(k) for k in keys))
    def implied(a):                          # the decision that the four pre-filled answers imply on their own
        if a.get('type') not in ('primary', 'secondary') or 'no' in (a.get('privacy'), a.get('ngiot'), a.get('focus')):
            return 'EXCLUDE'
        return 'INCLUDE' if (a.get('privacy'), a.get('ngiot'), a.get('focus')) == ('yes', 'yes', 'yes') else 'UNSURE'
    imp = collections.Counter((implied(F[n]), D[n]['decision']) for n in dec)
    s['pf_implied_include'] = imp[('INCLUDE', 'INCLUDE')] + imp[('INCLUDE', 'EXCLUDE')]
    s['pf_implied_include_excluded'] = imp[('INCLUDE', 'EXCLUDE')]
    s['pf_implied_exclude'] = imp[('EXCLUDE', 'EXCLUDE')] + imp[('EXCLUDE', 'INCLUDE')]
    s['pf_implied_exclude_included'] = imp[('EXCLUDE', 'INCLUDE')]
    s['pf_implied_open'] = imp[('UNSURE', 'INCLUDE')] + imp[('UNSURE', 'EXCLUDE')]
    s['pf_decision_differs'] = s['pf_implied_include_excluded'] + s['pf_implied_exclude_included']
    # the 'exclude' of the pre-fill splits in two (claims audit V38): an answer that fails a criterion, or only the kind of study
    # left open ("can't tell"), which fails nothing
    failed = lambda a: 'no' in (a.get('privacy'), a.get('ngiot'), a.get('focus')) or a.get('type') == 'neither'
    s['pf_failed'] = sum(1 for n in dec if failed(F[n]))
    s['pf_failed_included'] = sum(1 for n in dec if failed(F[n]) and D[n]['decision'] == 'INCLUDE')
    s['pf_type_open'] = sum(1 for n in dec if implied(F[n]) == 'EXCLUDE' and not failed(F[n]))
    s['pf_type_open_included'] = sum(1 for n in dec if implied(F[n]) == 'EXCLUDE' and not failed(F[n]) and D[n]['decision'] == 'INCLUDE')
    assert s['pf_failed'] + s['pf_type_open'] == s['pf_implied_exclude']
    s['prefill_kept'] = s['prefill_answers'] - s['prefill_changed']
    s['sd_only'] = mc['only_sciencedirect']
    s['sd_distinct'] = sum(1 for r in R.values() if 'ScienceDirect' in r['sources'])
    s['om_assessed'] = len(K)
    s['om_included'] = sum(D.get(n, {}).get('decision') == 'INCLUDE' for n in K)
    s['om_excluded'] = s['om_assessed'] - s['om_included']
    codes = collections.Counter(D.get(n, {}).get('code') or 'not recorded' for n in K if D.get(n, {}).get('decision') == 'EXCLUDE')
    for c, v in codes.items():
        s[f'om_ex_{slug(c)}'] = v
    # the database branch: records included at screening, and records reinstated by the full second screening of every
    # default and rule exclusion (search-ppml/evidence/rescreen/; the earlier sample's decisions in CHECK-DECISIONS)
    CK = {c['n']: c for c in read(P / 'CHECK-DECISIONS-2026-10-05.csv')} if (P / 'CHECK-DECISIONS-2026-10-05.csv').exists() else {}
    RS = P / 'evidence' / 'rescreen'
    db_inc = [n for n in screen if D.get(n, {}).get('decision') == 'INCLUDE']
    pop = read(RS / 'POPULATION-2026-10-05.csv')
    s['rs_population'] = len(pop)
    s['rs_from_date'] = sum(r['stratum'] == 'default: survey before 2024' for r in pop)
    s['rs_from_angle'] = sum(r['stratum'] == 'default: no focus angle' for r in pop)
    s['rs_from_rule'] = sum(r['stratum'] == 'automated focus rule' for r in pop)
    rres = json.loads((RS / 'RESCREEN-RESULT-2026-10-05.json').read_text(encoding='utf-8'))
    rdec = {r['n']: r for r in read(RS / 'RESCREEN-DECISIONS-2026-10-05.csv')}
    s['rs_ta_include'] = sum(r['ai_decision'] == 'INCLUDE' for r in rdec.values())
    s['rs_ta_unsure'] = sum(r['ai_decision'] == 'UNSURE' for r in rdec.values())
    s['rs_ic7'] = rres['ic7_settled_by_script']
    s['rs_compared'] = rres['sample_compared']
    s['rs_agree'] = rres['agreement_with_sample_run'].get('same decision', 0)
    flagged = {n for n, r in rdec.items() if r['after_ic7'] in ('INCLUDE', 'UNSURE')} | set(CK)   # either run's flags
    s['rs_flagged'] = len(flagged)
    s['rs_flagged_full_run'] = sum(1 for r in rdec.values() if r['after_ic7'] in ('INCLUDE', 'UNSURE'))
    NR = json.loads((RS / 'NOT-RETRIEVED-2026-10-05.json').read_text(encoding='utf-8'))
    not_ret = {n for n, c in CK.items() if c['retrieved'] != 'yes'} | set(NR)
    s['rs_not_retrieved'] = len(not_ret)
    s['rs_unavailable'] = sum(1 for n, c in CK.items() if c['retrieved'] != 'yes')
    s['rs_not_downloaded'] = sum(1 for v in NR.values() if str(v.get('why', '')).startswith('not downloaded'))
    assert s['rs_unavailable'] + s['rs_not_downloaded'] == s['rs_not_retrieved']
    ft = {r['n']: r for r in read(RS / 'RESCREEN-FULLTEXT-2026-10-05.csv')}
    final = {n: (c['decision'], c['code']) for n, c in CK.items() if c['retrieved'] == 'yes'}
    final.update({n: (r['decision'], r['code']) for n, r in ft.items() if n not in CK})
    s['rs_assessed'] = len(final)
    s['rs_included'] = sum(d == 'INCLUDE' for d, _ in final.values())
    s['rs_excluded'] = sum(d == 'EXCLUDE' for d, _ in final.values())
    for d, c in final.values():
        if d == 'EXCLUDE':
            s[f'rs_ex_{slug(c)}'] = s.get(f'rs_ex_{slug(c)}', 0) + 1
    s['rs_ai_assessed'] = len(ft)                                  # full texts assessed by the AI tool, decided by the author
    # the suggestions as the screening application showed them: the runs' proposals, with the consistency rules applied where the
    # separate runs had read a criterion differently (rescreen/ADJUDICATION-2026-10-05.json; the runs' own outputs are never edited)
    adj = json.loads((RS / 'ADJUDICATION-2026-10-05.json').read_text(encoding='utf-8'))
    sug = {n: r['proposed'] for n, r in ft.items()}
    ruled = {n: ch['to'].split()[0] for rule in adj['rules'] for n, ch in (rule.get('changes') or {}).items() if n in ft}
    sug.update(ruled)
    s['rs_rules_changed'] = sum(1 for n, v in ruled.items() if v != ft[n]['proposed'])
    s['rs_ai_proposed_include'] = sum(v == 'INCLUDE' for v in sug.values())
    s['rs_author_agreed'] = sum(r['proposed'] == r['decision'] for r in ft.values())
    s['rs_author_overruled'] = sum(r['proposed'] == 'INCLUDE' and r['decision'] == 'EXCLUDE' and r['code'] != 'NOT-FINAL-VERSION' for r in ft.values())
    s['rs_not_final'] = sum(r['code'] == 'NOT-FINAL-VERSION' for r in ft.values())
    s['rs_app_included'] = sum(r['decision'] == 'INCLUDE' for r in ft.values())
    AD = {r['n']: r for r in read(RS / 'AUTHOR-RESCREEN-DECISIONS-2026-10-05.csv')}
    deleg = {n for n, r in AD.items() if "at the author's request" in r.get('comment', '')}       # settled by the tool, at the author's request
    s['rs_delegated'] = len(deleg)
    s['rs_delegated_included'] = sum(1 for n in deleg if AD[n]['decision'] == 'INCLUDE')
    s['rs_delegated_excluded'] = sum(1 for n in deleg if AD[n]['decision'] == 'EXCLUDE')
    s['rs_author_included'] = s['rs_app_included'] - s['rs_delegated_included']
    s['rs_author_excluded'] = sum(1 for n, r in ft.items() if r['decision'] == 'EXCLUDE' and n not in deleg)
    s['rs_author_excluded_proposed'] = sum(1 for n, r in ft.items() if sug[n] == 'INCLUDE' and r['decision'] == 'EXCLUDE' and n not in deleg)
    s['rs_first_run_only'] = s['rs_flagged'] - s['rs_flagged_full_run']
    s['rs_ec9_earlier'] = sum(c['code'] == 'NO-BLOCKCHAIN' for c in CK.values())     # included before the blockchain criterion
    s['rs_earlier_assessed'] = sum(1 for c in CK.values() if c['retrieved'] == 'yes')   # flagged by the earlier run, decided first
    s['rs_earlier_included'] = sum(1 for c in CK.values() if c['retrieved'] == 'yes' and c['decision'] == 'INCLUDE')
    early = {n: json.loads((ROOT / c['basis']).read_text(encoding='utf-8')) for n, c in CK.items() if c['retrieved'] == 'yes'}
    s['rs_earlier_proposed_include'] = sum(1 for d in early.values() if d.get('proposed_decision') == 'INCLUDE')   # all accepted at first
    s['rs_earlier_later_excluded'] = sum(1 for n, d in early.items() if d.get('proposed_decision') == 'INCLUDE' and CK[n]['decision'] == 'EXCLUDE'
                                         and CK[n]['code'] != 'NO-BLOCKCHAIN')
    assert s['rs_earlier_assessed'] + s['rs_ai_assessed'] == s['rs_assessed']
    s['rs_ta_flagged'] = s['rs_ta_include'] + s['rs_ta_unsure']
    s['ft_sought'] = len(db_inc) + s['rs_flagged']
    s['ft_not_retrieved'] = s['rs_not_retrieved']
    s['ft_search_assessed'] = sum(1 for n in db_inc if FT.get(n, {}).get('decision')) + s['rs_assessed']
    s['ft_excluded'] = sum(1 for n in db_inc if FT.get(n, {}).get('decision') == 'EXCLUDE') + s['rs_excluded']
    s['ft_assessed'] = s['ft_search_assessed'] + s['om_assessed']
    s.update(RS1.stats())                                         # the supplementary search R-S1
    s['rs1_month'] = s['rs1_date'].split(' ', 1)[1]
    s['db_included'] = len(db_inc) + s['rs_included'] + s['rs1_included']
    assert s['rs_assessed'] + s['rs_not_retrieved'] == s['rs_flagged'], (s['rs_assessed'], s['rs_not_retrieved'], s['rs_flagged'])
    # the extraction check (search-ppml/evidence/checks/CHECKS-RESULT-2026-10-05.json)
    cr = json.loads((P / 'evidence' / 'checks' / 'CHECKS-RESULT-2026-10-05.json').read_text(encoding='utf-8'))
    sp = cr['spot_check']
    s['sc_studies'] = len(sp['per_study'])
    s['sc_answers'] = sp['answers']
    s['sc_agree'], s['sc_minor'], s['sc_disagree'] = sp['verdicts'].get('agree', 0), sp['verdicts'].get('minor', 0), sp['verdicts'].get('disagree', 0)
    # the correction of the extraction against the full texts (search-ppml/evidence/sheet-fix/): first check, second check
    fix = P / 'evidence' / 'sheet-fix'
    first = [json.loads(f.read_text(encoding='utf-8')) for f in sorted((fix / 'results').glob('*.json'))]
    s['fix_studies'] = len(first)
    s['fix_answers'] = sum(len(r['answers']) for r in first)
    s['fix_corrected'] = sum(a.get('verdict') == 'corrected' for r in first for a in r['answers'].values())
    second = [json.loads(f.read_text(encoding='utf-8')) for f in sorted((fix / 'check2' / 'results').glob('*.json'))]
    s['c2_studies'] = len(second)
    s['c2_items'] = sum(len(r.get('items', [])) for r in second)
    s['c2_overturned'] = sum(it.get('verdict') == 'overturned' for r in second for it in r.get('items', []))
    s['c2n_corrected'] = sum(1 for line in (fix / 'APPLIED.jsonl').read_text(encoding='utf-8').splitlines()
                             if json.loads(line).get('pass') == 'check2/narrow/results')
    fin = read(P / 'FINAL-STUDIES-2026-10-05.csv')
    s['included'] = len(fin)
    s['primary'] = sum(r['kind'] == 'primary' for r in fin)
    s['secondary'] = sum(r['kind'] == 'secondary' for r in fin)
    s['inc_via_search'] = sum(r['via'].startswith('searches') for r in fin)
    s['inc_via_check'] = sum('second screening' in r['via'] for r in fin)
    assert s['db_included'] + s['om_included'] == s['included'], (s['db_included'], s['om_included'], s['included'])
    s['inc_via_other'] = sum(r['via'] == 'other methods' for r in fin)
    first = [r for r in fin if r['via'] == 'searches']             # included at the first screening of the main searches
    check = [r for r in fin if 'second screening' in r['via']]   # reinstated by the automated screening tool
    s['inc_first_primary'] = sum(r['kind'] == 'primary' for r in first)
    s['inc_first_secondary'] = sum(r['kind'] == 'secondary' for r in first)
    s['inc_check_primary'] = sum(r['kind'] == 'primary' for r in check)
    s['inc_check_secondary'] = sum(r['kind'] == 'secondary' for r in check)
    s['rs_tool_excluded'] = s['rs_population'] - s['rs_flagged']
    s['ta_excluded_or_default'] = s['author_excluded'] + s['default_excluded']
    s['inc_via_rs1'] = sum(r['via'] == RS1.VIA for r in fin)
    assert s['inc_via_rs1'] == s['rs1_included']
    for kind in ('primary', 'secondary'):                        # how the studies of each tier were reached
        tier = [r for r in fin if r['kind'] == kind]
        s[f'{kind[:4]}_via_search'] = sum(r['via'].startswith('searches') for r in tier)
        s[f'{kind[:4]}_via_rs1'] = sum(r['via'] == RS1.VIA for r in tier)
        s[f'{kind[:4]}_via_other'] = sum(r['via'] == 'other methods' for r in tier)
    # the searches tested against the studies the author already knew (CORPUS-COVERAGE-2026-10-04.csv: every corpus paper
    # matched to the results of the final searches, with the reason where it is not among them; reported in Section II-B
    # from V59). 'On the topic' is the file's own reading of the indexed record: privacy, learning and an NG-IoT setting,
    # published from 2020, not a preprint.
    cov = read(P / 'CORPUS-COVERAGE-2026-10-04.csv')
    on_topic = lambda r: r['reason'] == 'in the results' or r['reason'].startswith('on the topic, missed')
    kp = [r for r in cov if r['kind'] == 'primary study' and on_topic(r)]
    s['kn_prim_topic'] = len(kp)
    s['kn_prim_found'] = sum(r['reason'] == 'in the results' for r in kp)
    s['kn_prim_missed_title'] = sum('privacy not in the title' in r['reason'] for r in kp)
    s['kn_prim_missed_db'] = sum('not returned by the databases' in r['reason'] for r in kp)
    assert s['kn_prim_found'] + s['kn_prim_missed_title'] + s['kn_prim_missed_db'] == s['kn_prim_topic']
    s['kn_prim_missed'] = s['kn_prim_topic'] - s['kn_prim_found']
    missed = {r['id'] for r in kp if r['reason'] != 'in the results'}
    s['kn_prim_missed_included'] = sum(r['kind'] == 'primary' and r['via'] == 'other methods' and r['corpus_id'] in missed for r in fin)
    ks = [r for r in cov if r['kind'] == 'survey' and on_topic(r)]
    s['kn_sec_topic'] = len(ks)
    s['kn_sec_found'] = sum(r['reason'] == 'in the results' for r in ks)
    s['kn_sec_missed_db'] = sum('not returned by the databases' in r['reason'] for r in ks)
    assert s['kn_sec_found'] + s['kn_sec_missed_db'] == s['kn_sec_topic']
    years = collections.Counter(r['year'] for r in fin)
    for y in range(2020, 2027):
        s[f'y{y}'] = years.get(str(y), 0)
    s['y2024_on'] = sum(v for y, v in years.items() if int(y) >= 2024)
    s['first_year'], s['last_year'] = min(years), max(years)
    s['sec_before_2024'] = sum(1 for r in fin if r['kind'] == 'secondary' and int(r['year']) < 2024)
    first = {r['n']: r for r in read(P / 'AUTHOR-FULLTEXT-BEFORE-CORRECTIONS-2026-10-05.csv')}   # the author's own answers at full text
    now = {r['n']: r for r in read(P / 'AUTHOR-FULLTEXT-2026-10-05.csv')}
    ch = [(n, f) for n in first for f in ('privacy', 'ngiot', 'focus_parts', 'zk_proves') if n in now and first[n][f] != now[n][f]]
    s['corrections'] = len(ch)
    s['corrected_studies'] = len({n for n, _ in ch})
    s['corrections_round1'] = len(read(P / 'CORRECTIONS-2026-10-05.csv'))
    s['corrections_round2'] = len(read(P / 'CORRECTIONS-V2-2026-10-05.csv'))
    s['corrections_round2_studies'] = len({r['n'] for r in read(P / 'CORRECTIONS-V2-2026-10-05.csv')})
    s['corrections_earlier'] = s['corrections'] - s['corrections_round2']
    ver = read(P / 'VERIFY-DECISIONS-2026-10-05.csv')
    s['verified_answers'] = sum(v['status'] == 'VERIFIED' for v in ver)
    s['verify_answers'] = len(ver)
    marks = {r['corpus_id']: angle_marks(r) for r in fin}
    for a in ANG:
        s[f'angle_{slug(a)}'] = sum(1 for r in fin if marks[r['corpus_id']][a] == '●')
        for kind in ('primary', 'secondary'):
            s[f'angle_{kind[:3]}_{slug(a)}'] = sum(1 for r in fin if r['kind'] == kind and marks[r['corpus_id']][a] == '●')
        s[f'angle_sec_mentioned_{slug(a)}'] = sum(1 for r in fin if r['kind'] == 'secondary' and marks[r['corpus_id']][a] == '◐')
    # the reports excluded at full text, with their reasons, and the reports not retrieved (supplementary material; PRISMA
    # 2020 item 16b): the same sets that the PRISMA counts above are made from
    CODE = {'OFF-FOCUS': 'no focus in substance (EC7)', 'PRIVACY-INCIDENTAL': 'privacy incidental (EC4)', 'NO-LEARNING': 'learning incidental (EC5)',
            'NO-BLOCKCHAIN': 'no blockchain, primary study (EC9)', 'NOT-A-STUDY': 'not a study (EC6)', 'NOT-FINAL-VERSION': 'no final version (EC2)',
            'NO-NGIOT': 'NG-IoT setting incidental (EC5)', 'SURVEY-BEFORE-2024': 'survey before 2024 below the citation threshold (EC8)'}
    title = lambda n: (R.get(n) or {}).get('title', '') or (FT.get(n) or {}).get('title', '')
    rows = [[title(n), (R.get(n) or {}).get('year', ''), 'main searches', CODE.get(FT[n].get('code', ''), FT[n].get('code', '') or 'not recorded')]
            for n in db_inc if FT.get(n, {}).get('decision') == 'EXCLUDE']
    rows += [[title(n), (R.get(n) or {}).get('year', ''), 'main searches, reinstated by the tool', CODE.get(c, c or 'not recorded')]
             for n, (d, c) in final.items() if d == 'EXCLUDE']
    rows += [[k.get('title', ''), k.get('year', ''), 'other methods', CODE.get(D.get(n, {}).get('code', ''), D.get(n, {}).get('code', '') or 'not recorded')]
             for n, k in K.items() if D.get(n, {}).get('decision') == 'EXCLUDE']
    rdec, rnr = RS1.author()
    scr1 = RS1.screening()
    rows += [[(scr1.get(n) or {}).get('title', n), (scr1.get(n) or {}).get('year', ''), 'supplementary search R-S1', CODE.get(d.get('code', ''), d.get('code', '') or 'not recorded')]
             for n, d in rdec.items() if d.get('author') == 'EXCLUDE']
    assert len(rows) == s['ft_excluded'] + s['om_excluded'] + s['rs1_excluded'], (len(rows), s['ft_excluded'], s['om_excluded'], s['rs1_excluded'])
    md_table('excluded_fulltext', 'Reports excluded at full text, with the criterion that excluded each.', ['Title', 'Year', 'Found by', 'Reason'],
             sorted(rows, key=lambda r: (r[2], r[3], r[0].lower())), widths=[48, 10, 22, 20])
    s['ft_ex_no_ledger'] = sum(r[3] == CODE['NO-BLOCKCHAIN'] for r in rows)   # designs the ledger requirement alone excluded
    nr = [[title(n), (R.get(n) or {}).get('year', ''), 'main searches'] for n in sorted(not_ret)]
    nr += [[(scr1.get(n) or {}).get('title', n), (scr1.get(n) or {}).get('year', ''), 'supplementary search R-S1'] for n in sorted(rnr)]
    md_table('not_retrieved', 'Reports sought but not retrieved.', ['Title', 'Year', 'Found by'], nr, widths=[68, 10, 22])
    return s, fin


# ------------------------------------------------------------------ tables
def md_table(key, caption, head, rows, note='', widths=None):
    width = [max([len(str(h))] + [len(str(r[i])) for r in rows]) for i, h in enumerate(head)]
    total = sum(width) or 1
    dashes = widths or [max(8, round(72 * w / total)) for w in width]
    out = [f'Table: {caption}', '', '| ' + ' | '.join(head) + ' |', '|' + '|'.join('-' * d for d in dashes) + '|']
    out += ['| ' + ' | '.join(str(c).replace('|', '/').replace('\n', ' ') for c in r) + ' |' for r in rows]
    if note:
        out += ['', f'*{note}*']
    (B / 'tables' / f'{key}.md').write_text('\n'.join(out) + '\n', encoding='utf-8')


def declaration_tables():
    """Declarations as tables (the author, 12 October 2026: "Declarations - make it a table with approprite columns"); the
    use of generative AI in the form of Abertay's research policy (A §10, p. 13: name and version of the tool, its URL and
    a brief description of what it was used for), every use acknowledged; the facts are those of the audited declaration.
    The model versions are those recorded in the session logs of the review (a documentation lookup aside)."""
    md_table('declarations', 'Declarations', ['Declaration', 'Statement'], [
        ['Author contributions', 'TBD.'],
        ['Use of generative AI', 'Claude (Anthropic), used through Claude Code, versions 2.1.283 to 2.1.296 (https://code.claude.com), with the '
                                 'models Claude Opus 5.5, Claude Opus 4.8, Claude Sonnet 5.5 and Claude Fable 5.1. {{TAB:ai_use}} lists its uses and the checks on them.'],
        ['Registration and protocol', 'Registration: TBD. The protocol, search strings and eligibility criteria, with every '
                                      'refinement, are kept with the review records.'],
        ['Data availability', 'The search strings and their provenance, the screening and eligibility decisions, the extraction records with '
                              'their tags, the scripts that compute every count, table and figure, and the harnesses and run summaries of the first '
                              'experiment are maintained at <https://github.com/shakir1311/ppml-ngiot-review-tools> and archived at Zenodo under the MIT licence (DOI: <https://doi.org/10.5281/zenodo.23895402>). The quotations of the papers and the database '
                              'exports are not redistributed, under the publishers\' terms, and are available on request.'],
        ['Funding', 'TBD.'],
        ['Competing interests', 'TBD.']], widths=[22, 78])
    md_table('ai_use', 'Use of generative AI in the review', ['Stage', 'Use of the tool, and the check on it'], [
        ['Search', 'Drafted the search strings and the eligibility criteria and tested the strings against the studies the reviewer already knew; the reviewer approved them and ran every search.'],
        ['Screening', 'Wrote the screening scripts (a cue-word pre-fill, not a language model). As a second screener, re-screened blind every record excluded by default or by rule and assessed the full texts it reinstated; the reviewer decided every report.'],
        ['Extraction', 'Drafted the page-cited notes, the extraction answers with their quotations and the study paragraphs, and checked them against the full texts; a script found every quotation on its page, and the reviewer verified every answer and quotation against the PDF.'],
        ['Tables and figures', 'Wrote the scripts that compute the counts, tables and figures from the records; no image generator; a separate script recomputes every table.'],
        ['Text', 'Drafted a reference version of the article\'s text with its numbers from the records, and reviewed drafts for method and coherence. The reference design is the review\'s own; the reviewer is responsible for the content.']], widths=[14, 86])


def overlap_tables(s):
    """the overlap of the two tiers: which included primary studies each included survey cites, from public reference lists
    (scripts/paper_ppml/overlap.py; OpenAlex, looked up by DOI); the latest evidence file is read"""
    files = sorted((P / 'evidence' / 'overlap').glob('OPENALEX-OVERLAP-*.json'))
    if not files:
        return
    d = json.loads(files[-1].read_text(encoding='utf-8'))
    s['ov_surveys_with_refs'] = d['surveys_with_references']
    s['ov_designs_cited'] = len(d['designs_cited_by_any_survey'])
    s['ov_designs_not_cited'] = d['primary'] - len(d['designs_cited_by_any_survey'])
    s['ov_surveys_citing'] = len(d['surveys_citing_any_design'])
    s['ov_pairs'] = d['citations_pairs']
    rows = [[f'[@{k}]', str(v['year']), (', '.join(f'[@{x}]' for x in v['cites']) if v['cites'] else '–') if v['references_held']
             else 'reference list not held by OpenAlex'] for k, v in sorted(d['by_survey'].items())]
    md_table('overlap', 'The included primary studies that each included survey cites, from the reference lists that OpenAlex holds.',
             ['Survey', 'Year', 'Primary studies it cites'], rows, widths=[16, 10, 74],
             note=f"{s['ov_designs_cited']} of the {d['primary']} primary studies are cited by at least one survey; "
                  f"{s['ov_designs_not_cited']} by none.")


def method_tables(s):
    md_table('criteria', 'Eligibility criteria.', ['Code', 'Criterion'], [
        ['IC1', 'The subject includes the privacy of machine learning (of the data, the models or the updates) in a next-generation IoT setting: IoT together with 5G or 6G, edge, fog or multi-access edge computing, and the settings built on them (industrial, medical and vehicular IoT, smart grids, communication networks).'],
        ['IC2', 'Primary study: proposes, builds or evaluates a method, system, protocol or attack concerning the privacy of learning, or measures privacy leakage. Secondary study: a survey, systematic review or mapping study, systematisation of knowledge, or a tutorial or overview that reviews the literature.'],
        ['IC3', 'Deals, as part of its contribution, with at least one of: (a) verification of training, updates or aggregation by means other than zero-knowledge proofs; (b) zero-knowledge proofs about the learning, whether verified off or on the ledger; (c) a blockchain or distributed ledger as part of the design; (d) poisoning; (e) malicious or fake participants; (f) free riding. At screening, zero-knowledge proofs verified on the ledger were recorded as a part of their own; they are a subset of (b). A primary study must also build on a blockchain or distributed ledger (c). A secondary study must cover at least one of them in substance.'],
        ['IC4', 'Peer-reviewed journal, conference or magazine article.'],
        ['IC5', 'Published from January 2020 to the date of the search.'],
        ['IC6', 'In English, with the full text available.'],
        ['IC7', 'A secondary study is published in 2024 or later, or is cited at least 100 times in Scopus or IEEE Xplore at the date of the search (the higher of the two counts).'],
        ['EC1', 'Retracted.'], ['EC2', 'A duplicate or an earlier version of an included study; and, added at full text, a report of which only an unedited early-access version exists.'],
        ['EC3', 'Not a full paper: editorial, notice, talk, poster, extended abstract, thesis, book, or a book chapter that is not a paper in peer-reviewed conference proceedings.'],
        ['EC4', 'Privacy is incidental. Secondary study: privacy is named but not treated. Primary study: no privacy mechanism or privacy analysis of its own; federated learning alone does not count, whereas zero-knowledge proofs that show a property of the data or the update without revealing it do.'],
        ['EC5', 'The learning or the next-generation IoT setting is incidental.'],
        ['EC6', 'Neither a primary nor a secondary study (position, vision or opinion paper).'],
        ['EC7', 'Meets none of IC3 (a)–(f) in substance.'],
        ['EC8', 'A secondary study published before 2024 and cited fewer than 100 times, or with no citation count on record (IC7 not met).'],
        ['EC9', 'A primary study without a blockchain or distributed ledger in its design.']],
        widths=[8, 92])
    md_table('strings', 'The searches and the supplementary search R-S1. Each main search combines a privacy block, a learning block and a next-generation IoT block; R-S1 combines a data-protection block, a ledger block, a learning block and a next-generation IoT block. The full strings are given in Appendix A.',
             ['Search', 'Source', 'Study type sought', 'Fields and limits', 'Records'], [
        ['P-S1', 'Scopus', 'secondary', 'a survey term in the title, or the document type Review; privacy, learning and NG-IoT terms in title, abstract or keywords; 2020–2026; articles, conference papers and reviews; English', f"{s['rec_ps1']:,}"],
        ['P-A', 'IEEE Xplore', 'secondary', 'a survey term in the document title; privacy, learning and NG-IoT terms in all metadata; split into six queries by the limit of 25 terms per query; journals, conferences, magazines and early access, 2020–2026', f"{s['rec_pa']:,}"],
        ['P-C', 'ScienceDirect', 'secondary', 'a survey term in the title; privacy, learning and NG-IoT terms in title, abstract or keywords; split into eight queries by the limit of eight connectors per field; review and research articles, 2020–2026', f"{s['rec_pc']:,}"],
        ['P-S2', 'Scopus', 'primary', 'a privacy term in the title, or a privacy term together with a threat or verification term (poisoning, Byzantine, backdoor, Sybil, malicious, free riding, fake nodes or clients, model integrity, verifiable) in title, abstract or keywords; learning and NG-IoT terms; limits as P-S1', f"{s['rec_ps2']:,}"],
        ['P-B', 'IEEE Xplore', 'primary', 'privacy in the document title, or privacy together with a threat or verification term in the abstract; learning and NG-IoT terms in the abstract; one query exported in two year ranges (2020–2024, 2025–2026) because of the export limit of 1,000 records', f"{s['rec_pb']:,}"],
        ['Total', '', '', '', f"{s['id_total']:,}"],
        ['R-S1', 'Scopus', 'primary and secondary', 'a data-protection term (GDPR, the EDPB, data protection, the right to erasure, regulatory compliance, privacy or data protection by design, personal data), a ledger term, a learning term and an NG-IoT term in title, abstract or keywords; 2020–2026; articles, conference papers and reviews; English; a supplementary search', f"{s['rs1_records']:,}"]],
             widths=[9, 11, 10, 60, 10])
    # one string per search, as in the final run; IEEE Xplore (25 terms per query) and ScienceDirect (8 connectors per field)
    # took theirs in parts, given here combined; every part, as run, is kept with the review's records (scripts/search_ppml/strings.py)
    tq = lambda g: ' OR '.join(f'"Document Title":{x}' for x in g)
    mq = lambda g: ' OR '.join(f'"All Metadata":{x}' for x in g)
    ieee_one = (f'({tq([x for part in STR.IEEE_SUR_PARTS for x in part])}) AND ({mq(STR.IEEE_PPML)}) AND ({mq(STR.IEEE_ML)}) '
                f'AND ({mq([x for part in STR.IEEE_NGIOT_PARTS for x in part])})')
    sd_one = ('Title: ' + STR.SD_TITLE + ' · Title, abstract or keywords: ("privacy-preserving" OR "privacy preserving" OR "data privacy" OR '
              '"differential privacy" OR "homomorphic encryption" OR "secure aggregation" OR "privacy-preserving machine learning" OR PPML) AND '
              '("machine learning" OR "federated learning" OR "deep learning" OR "distributed learning" OR "collaborative learning" OR '
              '"edge intelligence") AND ("next generation IoT" OR "NG-IoT" OR "Internet of Things" OR IoT OR IIoT OR "edge computing" OR '
              '"fog computing" OR 5G OR 6G)')
    rows = [['P-S1', 'Scopus', STR.scopus()],
            ['P-A', 'IEEE Xplore (command search; run as six queries of at most 25 terms)', ieee_one],
            ['P-C', 'ScienceDirect (Title; Title, abstract or keywords; run as eight shorter strings from these terms)', sd_one],
            ['P-S2', 'Scopus', STR.scopus_primary()],
            ['P-B', 'IEEE Xplore (command search; exported in two year ranges)', STR.ieee_primary()[0]],
            ['R-S1', 'Scopus (supplementary search)', SREG.scopus()['R-S1']]]
    md_table('strings_full', 'Search strings of the final searches and of the supplementary search R-S1, one per search. IEEE Xplore took its string in six parts (two halves of the survey terms by three thirds of the setting terms), which together equal the string shown; ScienceDirect took eight shorter strings built from the terms shown, each with at most eight connectors. Every part, as run, is kept with the review records.',
             ['Search', 'Source and fields', 'String'], rows, widths=[8, 17, 75])
    md_table('items', 'Data items: the extraction form and the survey question each item serves.', ['Item', 'Studies', 'What is recorded', 'SQ'], [
        ['P1', 'primary', 'setting, enablers (5G/6G, edge, fog, MEC), arrangement of learning, roles and tiers; cost measured on device-class hardware or over a real or emulated network link', 'SQ1'],
        ['P2', 'primary', 'privacy mechanisms, what each hides and from whom, reported cost', 'SQ2'],
        ['P3', 'primary', 'ledger type, platform, consensus, what is written on-chain, what the ledger does', 'SQ3'],
        ['P4', 'primary', 'what is checked about updates, training or aggregation, by whom, whether the checker sees the update; zero-knowledge proof system, statement, verifier, on-chain or not', 'SQ3'],
        ['P5', 'primary', 'threats claimed and threats tested by an attack in an experiment or simulation, attacker share, defences', 'SQ4'],
        ['P6', 'primary', 'data sets, models, baselines compared, metrics and results, hardware, code availability', 'SQ1, SQ4'],
        ['P7', 'primary', 'laws and guidelines named, personal data on the chain, erasure', 'SQ5'],
        ['P8', 'primary', 'limitations and future work stated by the authors', 'all'],
        ['S1', 'secondary', 'subject, databases, period, number of studies', 'all'],
        ['S2', 'secondary', 'whether each of the five layers is a subject of its own, mentioned or absent', 'SQ1–SQ5'],
        ['S3', 'secondary', 'privacy mechanisms covered', 'SQ2'],
        ['S4', 'secondary', 'poisoning, malicious or fake participants, free riding, verification, zero-knowledge proofs, blockchain: subject, mentioned or absent', 'SQ3, SQ4'],
        ['S5', 'secondary', 'laws and guidelines named; EDPB guidelines and EU AI Act', 'SQ5'],
        ['S6', 'secondary', 'conclusions on privacy against checking, the role of the ledger, resistance to poisoning', 'SQ3, SQ4'],
        ['S7', 'secondary', 'open issues and future directions', 'all'],
        ['S8', 'secondary', 'limitations of the survey', 'all']], widths=[6, 14, 66, 14])


def prisma_checklist():
    """PRISMA 2020 checklist (Page et al. 2021, Table 1) with the place of each item in the paper."""
    T = lambda k: '{{TAB:' + k + '}}'
    Fg = lambda k: '{{FIG:' + k + '}}'
    rows = [
        ['Title', '1', 'Identify the report as a systematic review.', 'Title'],
        ['Abstract', '2', 'Structured summary (PRISMA 2020 for Abstracts).', 'Abstract'],
        ['Introduction', '3', 'Rationale.', 'Sections I-A, I-B'],
        ['', '4', 'Objectives or questions.', f"Section II-A, {T('sq')}"],
        ['Methods', '5', 'Eligibility criteria and how studies were grouped.', f"Section II-C, Appendix A, {T('criteria')}"],
        ['', '6', 'Information sources and date last searched.', 'Section II-B; the dates are kept in the search records'],
        ['', '7', 'Full search strategies.', f"Appendix A, {T('strings_full')}"],
        ['', '8', 'Selection process: reviewers, independence, automation tools.', 'Section II-C, Declarations'],
        ['', '9', 'Data collection process.', 'Section II-D'],
        ['', '10a–b', 'Data items: outcomes and other variables.', 'Section II-D'],
        ['', '11', 'Study risk of bias assessment.', f"Section II-E, {T('qa_checklist')}, Appendix B"],
        ['', '12', 'Effect measures.', 'Section II-E (not applicable: no effect measures)'],
        ['', '13a–f', 'Synthesis methods.', 'Section II-E (incl. the sensitivity check)'],
        ['', '14', 'Reporting bias assessment.', 'Section X'],
        ['', '15', 'Certainty assessment.', 'Sections IV-C, VII-A'],
        ['Results', '16a', 'Study selection, with a flow diagram.', f"Section II-C, {Fg('prisma')}"],
        ['', '16b', 'Studies that might appear to meet the criteria but were excluded, and why.', f"{Fg('prisma')} (reasons at full text)"],
        ['', '17', 'Study characteristics.', 'Section IV-B; Sections V-A, VI-A'],
        ['', '18', 'Risk of bias in studies.', 'Section IV-C, Appendix B'],
        ['', '19', 'Results of individual studies.', 'Sections V-A, VI-A'],
        ['', '20a–d', 'Results of syntheses.', 'Sections V-B to V-D, VI-B to VI-F'],
        ['', '21', 'Reporting biases.', 'Section X'],
        ['', '22', 'Certainty of evidence.', 'Sections IV-C, VII-A'],
        ['Discussion', '23a–d', 'Interpretation, limitations of the evidence and of the review, implications.', 'Sections VII–X'],
        ['Other information', '24a–c', 'Registration and protocol; amendments.', 'Declarations (protocol and refinements kept with the records)'],
        ['', '25', 'Support.', 'Declarations'],
        ['', '26', 'Competing interests.', 'Declarations'],
        ['', '27', 'Availability of data, code and other materials.', 'Declarations']]
    md_table('prisma_checklist', 'PRISMA 2020 checklist: where each item is reported.', ['Section', 'Item', 'Topic', 'Where reported'], rows, widths=[14, 8, 48, 30])


ANG = ['poisoning', 'malicious or fake participants', 'free riding', 'verification', 'zero-knowledge proofs', 'blockchain', 'ZK on blockchain']
S4KEY = {'poisoning': 'poisoning', 'malicious or fake participants': 'malicious_fake', 'free riding': 'free_riding', 'verification': 'verification',
         'zero-knowledge proofs': 'zkp', 'blockchain': 'blockchain'}


def _sheet(cid):
    f = ROOT / 'search-ppml' / 'evidence' / 'sheets' / f'{cid}.json'
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else {'answers': {}}


CHECKS_OF_LEARNING = {'test-accuracy-quality', 'similarity-distance', 'norm-bound', 'correct-training', 'correct-aggregation',
                      'anomaly-detection', 'contribution-reputation'}
ZK_COVERS = {'training': 'correct-training', 'bounded': 'norm-bound', 'aggregation': 'correct-aggregation', 'similarity': 'similarity-distance'}


def angle_marks(r):
    """● / ◐ / '' for each focus angle, from the full-text records (claims audit V38), so that the angles agree with the thematic
    tables. A survey: S4 (a subject of its own ●, mentioned ◐). A primary study: poisoning, malicious or fake participants and
    free riding when it claims to counter or tests the threat (an identity check that decides who takes part also counts for
    fake participants, as consistency rule R2); verification when it checks updates, training or aggregation by means other
    than a ZKP; ZKPs when it uses them; ZK on blockchain when its proofs are verified on the ledger; blockchain when it has one."""
    a = _sheet(r['corpus_id'])['answers']
    if r['kind'] == 'secondary':
        v = (a.get('S4', {}) or {}).get('values', {}) or {}
        return {x: ({'subject': '●', 'mentioned': '◐'}.get(v.get(S4KEY[x], ''), '') if x in S4KEY else '') for x in ANG}
    val = lambda q, f: ((a.get(q, {}) or {}).get('values', {}) or {}).get(f)
    lst = lambda q, f: (val(q, f) if isinstance(val(q, f), list) else ([val(q, f)] if val(q, f) not in (None, '') else []))
    import thematic as TH                              # a Byzantine claim about the consensus is not about participants (V56)
    sh = _sheet(r['corpus_id'])
    threats = TH.threats_of(r['corpus_id'], sh, 'claimed') | TH.threats_of(r['corpus_id'], sh, 'tested')
    zk = val('P4', 'zk_used') is True
    shows = {str(x).split(':')[0].strip() for x in lst('P4', 'zk_shows')} if zk else set()
    checks = set(lst('P4', 'checked')) & CHECKS_OF_LEARNING
    if zk:
        checks -= {ZK_COVERS[x] for x in shows if x in ZK_COVERS}
    on = {'poisoning': bool(threats & {'poisoning', 'backdoor'}),
          'malicious or fake participants': bool(threats & {'byzantine-malicious', 'sybil-fake'}) or 'identity-membership' in lst('P4', 'checked'),
          'free riding': 'free-riding' in threats,
          'verification': TH.verification_yes(r['corpus_id'], sh),          # the rule of the spine table (II-A; V57)
          'zero-knowledge proofs': zk,
          'blockchain': val('P3', 'ledger') not in (None, '', 'none'),
          'ZK on blockchain': zk and val('P4', 'zk_on_chain') == 'yes'}
    return {x: ('●' if on[x] else '') for x in ANG}


def prisma_tables(s, fin):
    """The tables of the PRISMA and themes record (Docs/PPML-REVIEW-PRISMA-AND-THEMES-V5): reasons for exclusion at
    screening, the focus angles across the included studies, what the zero-knowledge proofs show, and the included studies
    with their angles. All from the author's answers."""
    D = {d['n']: d for d in read(P / 'AUTHOR-DECISIONS-2026-10-04.csv')}
    R = {r['n']: r for r in read(P / 'MERGED-RECORDS-2026-10-04.csv')}
    screen = [n for n, r in R.items() if not r['auto_excluded']]
    name = {'PRIVACY-INCIDENTAL': 'privacy incidental (EC4)', 'NO-NGIOT': 'NG-IoT setting incidental (EC5)', 'OFF-FOCUS': 'none of the focus angles (EC7)',
            'SURVEY-BEFORE-2024': 'survey before 2024, fewer than 100 citations or no count on record (EC8)', 'OTHER': 'other', '': 'reason not recorded (not required at this stage)'}
    codes = collections.Counter(D[n]['code'] for n in screen if D.get(n, {}).get('decision') == 'EXCLUDE')

    def implied_reason(d):                   # no code recorded: the reason the author's own answers give
        if d['type'] not in ('primary', 'secondary'):
            return 'kind of study unclear'
        if d['privacy'] == 'no':
            return name['PRIVACY-INCIDENTAL']
        if d['ngiot'] == 'no':
            return name['NO-NGIOT']
        if d['focus'] == 'no':
            return name['OFF-FOCUS']
        if d['privacy'] != 'yes' or d['ngiot'] != 'yes':
            return 'privacy or setting not established (EC4, EC5)'
        return 'answers met the criteria; no reason recorded'
    implied = collections.Counter(implied_reason(D[n]) for n in screen if D.get(n, {}).get('decision') == 'EXCLUDE' and not D[n]['code'])
    rows = [['By the author, reason recorded: ' + name.get(c, c), f'{v:,}'] for c, v in codes.most_common() if c]
    rows += [['By the author, reason given by the answers: ' + r, f'{v:,}'] for r, v in implied.most_common()]
    rows += [['Default exclusion accepted by the author: survey before 2024, fewer than 100 citations or no count on record (EC8)', f"{s['default_date']:,}"],
             ['Default exclusion accepted by the author: none of the focus angles (EC7)', f"{s['default_angle']:,}"],
             ['Total excluded at screening', f"{s['ta_excluded']:,}"]]
    s['excl_on_reading'] = implied.get('answers met the criteria; no reason recorded', 0)
    md_table('excl_reasons', 'Records excluded at title-and-abstract screening, by reason. Where the author recorded no reason, the reason is the one the author\'s own answers to the screening questions give.',
             ['Reason', 'Records'], rows, widths=[82, 18])
    A = ['verification', 'zero-knowledge proofs', 'blockchain', 'poisoning', 'malicious or fake participants', 'free riding']   # the six focus angles, by layer
    LAYER_OF = {'verification': 'SQ3 Trust plane', 'zero-knowledge proofs': 'SQ3 Trust plane', 'blockchain': 'SQ3 Trust plane',
                'poisoning': 'SQ4 Attacks and defences', 'malicious or fake participants': 'SQ4 Attacks and defences',
                'free riding': 'SQ4 Attacks and defences'}
    SH = {'poisoning': 'Poisoning', 'malicious or fake participants': 'Malicious or fake participants', 'free riding': 'Free riding',
          'verification': 'Verification of learning', 'zero-knowledge proofs': 'ZKPs', 'blockchain': 'Blockchain'}
    cnt = lambda kind, a: sum(1 for r in fin if (kind is None or r['kind'] == kind) and angle_marks(r)[a] == '●')
    for a in A:                                                   # the focus angles in numbers, for the text (Section II-A)
        s[f"ang_prim_{a.split()[0].replace('-', '_')}"] = cnt('primary', a)
        s[f"ang_sec_{a.split()[0].replace('-', '_')}"] = cnt('secondary', a)
    # the focus angles by tier (V34 Table 10, V55 Table V), restored at the author's request of 13 October 2026; the two tiers
    # are never counted together, so the earlier "All" column is not restored
    md_table('angles', 'The focus angles across the included studies, from their full-text records: a primary study counts for an '
             'angle as defined in Section II-A (verification: the content of updates, their training or the aggregation checked by means '
             'other than a ZKP, the column "Updates checked (not by ZKP)" of {{TAB:prim_cover}}), a survey for an angle it treats as a subject '
             'of its own ({{TAB:surveys}}; verification of the learning by any means); the two tiers are counted apart, and a study can have several.',
             ['Layer', 'Focus angle', f"Primary studies ({s['primary']})", f"Surveys ({s['secondary']})"],
             [[LAYER_OF[a], SH[a], cnt('primary', a), cnt('secondary', a)] for a in A], widths=[30, 30, 20, 20])
    def zk(r):                                                    # what the proofs show, from the full-text record (P4), as in Section VI-D
        v = {kk: vv for a in _sheet(r['corpus_id'])['answers'].values() for kk, vv in ((a or {}).get('values') or {}).items()}   # merged answers (15 Oct 2026)
        return [str(x).split(':')[0].strip() for x in (v.get('zk_shows') or [])] if v.get('zk_used') is True else []
    tick = lambda r, a: angle_marks(r)[a] or ('–' if r['kind'] == 'secondary' else '')
    order = {'primary': 0, 'secondary': 1}
    rows = [[f"[@{r['corpus_id']}]", r['kind'], r['year']] + [tick(r, a) for a in A] + [', '.join(zk(r)) or '–']
            for r in sorted(fin, key=lambda r: (order[r['kind']], r['year'], r['corpus_id']))]
    md_table('included_angles', 'The included studies and their focus angles, from their full-text records (primary studies: ● as defined in Section IV-B; surveys: ● a subject of its own, ◐ mentioned, – absent; ZK shows: what the zero-knowledge proofs of a primary study show).',
             ['Study', 'Kind', 'Year', 'Verif.', 'ZKPs', 'Chain', 'Pois.', 'Mal./fake', 'Free r.', 'ZK shows'], rows,
             widths=[8, 15, 8, 7, 7, 7, 7, 8, 7, 26])


def main():
    s, fin = prisma_stats()
    prisma_tables(s, fin)
    method_tables(s)
    overlap_tables(s)
    declaration_tables()
    prisma_checklist()
    S = sheets()
    import thematic                                    # counts and tables of the synthesis (needs the sheets)
    s.update(thematic.stats(S, fin))
    thematic.tables(S, fin, s, md_table)
    s.update(thematic.qa_stats(S, fin))
    thematic.qa_tables(S, fin, s, md_table)
    (B / 'cites.json').write_text(json.dumps(thematic.cite_lists(S, fin), indent=1), encoding='utf-8')
    import figures
    figures.main(s, S, fin)
    (B / 'stats.json').write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding='utf-8')
    print(len(s), 'numbers;', len(list((B / 'tables').glob('*.md'))), 'tables;', len(list((B / 'figures').glob('*.png'))), 'figures')


if __name__ == '__main__':
    main()
