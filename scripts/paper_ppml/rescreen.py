#!/usr/bin/env python3
"""Full second screening of every record excluded at screening without the author's own decision (5 October 2026).

The author: "rescan all records and decide on whether to include or exclude them. dont bother me with doing that. just
record everything correctly and ask me to review." The population is every record excluded by a default (survey before
2024 with fewer than 100 citations, or no focus angle) or set aside by the automated focus rule: 3,483 records. The 150
records of the earlier sample (SCREENING-CHECK-SAMPLE-2026-10-05.csv) are screened again with the rest, without being
marked, so that the agreement between the two independent runs can be reported. The author's own exclusions (2,776) and
the IEEE Xplore and not-a-paper rules are not part of it.

Screening is done by separate Claude runs, blind (no stratum, no pre-fill, no author answers), with the criteria of the
sample's guide copied word for word (checks/SECOND-SCREENING-GUIDE.md) into rescreen/RESCREEN-GUIDE.md.

  prepare   population (rescreen/POPULATION-2026-10-05.csv, with stratum and batch) and 30 blind input batches
            (rescreen/input/batch-NN.jsonl, random order, seed 20261006); writes the guide. Refuses to overwrite.
  check     validates rescreen/output/batch-NN.jsonl against the inputs: one line per record, same order, allowed values,
            and each quote found in its own record (title, abstract, keywords) unless the record is held in the corpus.
  result    merges the outputs: decisions by stratum; IC7 settled by script from the citation counts of the export;
            agreement with the sample run; the records flagged for full text, with their corpus folder if held
            (rescreen/RESCREEN-RESULT-2026-10-05.json, rescreen/RESCREEN-DECISIONS-2026-10-05.csv).

  fulltext-check  every full-text record in rescreen/fulltext/ has its fields and its quotations on the pages cited.
  fulltext-result merges the full-text records and the consistency rules into rescreen/RESCREEN-FULLTEXT-2026-10-05.csv.

Usage: python3 scripts/paper_ppml/rescreen.py prepare|check|result|fulltext-check|fulltext-result
"""
import collections, csv, json, pathlib, random, re, sys, unicodedata

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
RS = P / 'evidence' / 'rescreen'
IN, OUT = RS / 'input', RS / 'output'
SEED, BATCHES = 20261006, 30
DECISIONS = {'INCLUDE', 'EXCLUDE', 'UNSURE'}
CODES = {'', 'PRIVACY-INCIDENTAL', 'NO-NGIOT', 'NO-LEARNING', 'OFF-FOCUS', 'NOT-A-STUDY', 'NOT-FULL-PAPER', 'SURVEY-BEFORE-2024', 'OTHER'}
ANGLES = ['poisoning', 'malicious or fake participants', 'free riding', 'verification', 'zero-knowledge proofs', 'blockchain', 'ZK on blockchain']


def squash(s):
    s = unicodedata.normalize('NFKC', s or '').lower()
    return re.sub(r'[^a-z0-9]', '', s)


def rows(f, **kw):
    return list(csv.DictReader(open(f, encoding='utf-8'), **kw))


def population():
    R = {r['n']: r for r in rows(P / 'MERGED-RECORDS-2026-10-04.csv')}
    F = {r['n']: r for r in rows(P / 'PREFILL-2026-10-04.csv')}
    D = {d['n']: d for d in rows(P / 'AUTHOR-DECISIONS-2026-10-04.csv')}
    pop = {}
    for n, r in R.items():
        if r['auto_excluded'].startswith('outside the PhD focus'):
            pop[n] = 'automated focus rule'
        elif not r['auto_excluded'] and not D.get(n, {}).get('decision'):
            typ = D.get(n, {}).get('type') or F[n]['type']
            y, c = int(r['year'] or 0), r['cited']
            pop[n] = 'default: survey before 2024' if typ == 'secondary' and y < 2024 and (not c or int(c) < 100) else 'default: no focus angle'
    return R, pop


def corpus_folders():
    out = {}
    for m in rows(P / 'CORPUS-MATCHES-2026-10-04.csv'):
        if m['pdf']:
            out[m['n']] = str(pathlib.Path(m['pdf']).parent)
    return out


GUIDE_HEAD = """# Guide: full second screening of the excluded records (5 October 2026)

Purpose: every record that was excluded at screening by a default or by an automated rule, rather than by the author's own
decision, is screened again. You screen records **blind**: you are not told how a record was excluded, and you do not see
the author's answers or the pre-fill. Decide each record against the criteria below, from its title, abstract and
keywords. If the record has a `corpus_folder`, read in this order and only as far as needed: `notes/SUMMARY.md`, then
`notes/NOTES.md`, then single full-text pages (`text/pages/`).

The criteria and output are those of the earlier sample (checks/SECOND-SCREENING-GUIDE.md), copied below word for word,
with three additions: each output line also gives `"kind": "primary" | "secondary" | "neither"`; the angles use exactly
these names — """ + '; '.join(f'"{a}"' for a in ANGLES) + """; and every UNSURE names in its reason the criterion that
the abstract cannot settle.

"""


def prepare():
    if IN.exists() and any(IN.glob('*.jsonl')):
        sys.exit('rescreen/input exists; the population is drawn once')
    R, pop = population()
    sample = {r['n'] for r in rows(P / 'evidence' / 'SCREENING-CHECK-SAMPLE-2026-10-05.csv')}
    cf = corpus_folders()
    order = sorted(pop, key=int)
    random.Random(SEED).shuffle(order)
    IN.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)
    size = -(-len(order) // BATCHES)
    with open(RS / 'POPULATION-2026-10-05.csv', 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['n', 'stratum', 'in_earlier_sample', 'batch', 'corpus_folder'])
        for b in range(BATCHES):
            part = order[b * size:(b + 1) * size]
            with open(IN / f'batch-{b + 1:02d}.jsonl', 'w', encoding='utf-8') as out:
                for n in part:
                    r = R[n]
                    out.write(json.dumps({'n': n, 'title': r['title'], 'year': r['year'], 'venue': r['venue'], 'type': r['type'],
                                          'abstract': r['abstract'], 'keywords': r['keywords'], 'corpus_folder': cf.get(n, '')},
                                         ensure_ascii=False) + '\n')
                    w.writerow([n, pop[n], 'yes' if n in sample else '', f'{b + 1:02d}', cf.get(n, '')])
    g = (P / 'evidence' / 'checks' / 'SECOND-SCREENING-GUIDE.md').read_text(encoding='utf-8')
    body = g[g.index('## Criteria'):]
    (RS / 'RESCREEN-GUIDE.md').write_text(GUIDE_HEAD + body, encoding='utf-8')
    c = collections.Counter(pop.values())
    print(f'{len(order)} records in {BATCHES} batches of up to {size}:', dict(c), f'; {len(sample & set(pop))} from the earlier sample')


def load_out(b):
    f = OUT / f'batch-{b:02d}.jsonl'
    if not f.exists():
        return None
    return [json.loads(l) for l in f.read_text(encoding='utf-8').splitlines() if l.strip()]


def check(quiet=False):
    bad, done = 0, 0
    for b in range(1, BATCHES + 1):
        recs = [json.loads(l) for l in (IN / f'batch-{b:02d}.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
        ins = [r['n'] for r in recs]
        text = {r['n']: squash(' '.join((r['title'], r['abstract'], r['keywords']))) for r in recs}
        held = {r['n'] for r in recs if r['corpus_folder']}
        out = load_out(b)
        if out is None:
            print(f'batch-{b:02d}: no output')
            bad += 1
            continue
        probs = []
        if [o.get('n') for o in out] != ins:
            got = [o.get('n') for o in out]
            probs.append(f'{len(got)} lines for {len(ins)} records' if len(got) != len(ins) else 'records out of order or different')
        for o in out:
            if o.get('kind') not in ('primary', 'secondary', 'neither'):
                probs.append(f"{o.get('n')}: kind {o.get('kind')!r}")
            if o.get('decision') not in DECISIONS:
                probs.append(f"{o.get('n')}: decision {o.get('decision')!r}")
            if o.get('code', '') not in CODES:
                probs.append(f"{o.get('n')}: code {o.get('code')!r}")
            if o.get('decision') == 'EXCLUDE' and not o.get('code'):
                probs.append(f"{o.get('n')}: EXCLUDE without a code")
            if any(a not in ANGLES for a in o.get('angles', [])):
                probs.append(f"{o.get('n')}: angle {[a for a in o.get('angles', []) if a not in ANGLES]}")
            if not o.get('reason'):
                probs.append(f"{o.get('n')}: no reason")
            q = squash(o.get('quote', ''))
            if o.get('n') in text and o.get('n') not in held and (not q or q not in text[o['n']]):
                probs.append(f"{o.get('n')}: quote not in the record")   # catches an answer written against the wrong record
        if probs:
            bad += 1
            print(f'batch-{b:02d}: ' + '; '.join(probs[:6]))
        else:
            done += 1
            if not quiet:
                print(f'batch-{b:02d}: ok ({len(out)})')
    print(f'{done}/{BATCHES} batches complete and valid')
    return bad


def result():
    if check(quiet=True):
        sys.exit('not every batch is complete and valid')
    R, _ = population()
    pop = {r['n']: r for r in rows(RS / 'POPULATION-2026-10-05.csv')}
    out = {o['n']: o for b in range(1, BATCHES + 1) for o in load_out(b)}
    first = {}
    for f in sorted((P / 'evidence' / 'checks').glob('screen-output-*.jsonl')):
        for l in f.read_text(encoding='utf-8').splitlines():
            if l.strip():
                o = json.loads(l)
                first[o['n']] = o
    ck = {c['n']: c for c in rows(P / 'CHECK-DECISIONS-2026-10-05.csv')}      # decided at full text after the sample
    recs = []
    for n, o in out.items():
        r, p = R[n], pop[n]
        dec, code, note = o['decision'], o.get('code', ''), ''
        flagged = dec in ('INCLUDE', 'UNSURE')
        if flagged and (code == 'SURVEY-BEFORE-2024' or (o.get('kind') == 'secondary' and int(r['year'] or 0) < 2024)):
            if r['cited'] and int(r['cited']) >= 100:
                note = f"IC7 met: cited {r['cited']} times"
            elif r['cited']:
                dec, code, note = 'EXCLUDE', 'SURVEY-BEFORE-2024', f"IC7 not met: cited {r['cited']} times (EC8), settled by script"
            else:
                note = 'IC7 open: no citation count in the export'
        recs.append({'n': n, 'stratum': p['stratum'], 'in_earlier_sample': p['in_earlier_sample'], 'batch': p['batch'],
                     'title': r['title'], 'year': r['year'], 'venue': r['venue'], 'doi': r['doi'], 'cited': r['cited'],
                     'kind': o.get('kind', ''), 'ai_decision': o['decision'], 'ai_code': code, 'angles': '; '.join(o.get('angles', [])),
                     'reason': o.get('reason', ''), 'quote': o.get('quote', ''), 'ic7_note': note,
                     'after_ic7': dec, 'final_code': code if dec == 'EXCLUDE' else '',
                     'full_text_needed': 'yes' if dec in ('INCLUDE', 'UNSURE') and n not in ck else '',
                     'already_decided': (f"{ck[n]['decision']} at full text after the sample ({ck[n]['corpus_id'] or 'not retrieved'})" if n in ck else ''),
                     'corpus_folder': p['corpus_folder'], 'author': ''})
    recs.sort(key=lambda x: int(x['n']))
    old = RS / 'RESCREEN-DECISIONS-2026-10-05.csv'
    if old.exists():                                              # never lose the author's overrules on a rerun
        prev = {r['n']: r.get('author', '') for r in rows(old)}
        for x in recs:
            x['author'] = prev.get(x['n'], '')
    with open(RS / 'RESCREEN-DECISIONS-2026-10-05.csv', 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)
    by = collections.defaultdict(collections.Counter)
    for x in recs:
        by[x['stratum']][x['after_ic7']] += 1
        by['all'][x['after_ic7']] += 1
    codes = collections.Counter(x['final_code'] for x in recs if x['after_ic7'] == 'EXCLUDE')
    agree = collections.Counter()
    for x in recs:
        if x['n'] in first:
            a, b = first[x['n']]['decision'], x['ai_decision']
            agree['same decision' if a == b else f'{a} then {b}'] += 1
    flagged = [x for x in recs if x['full_text_needed']]
    res = {'records': len(recs), 'by_stratum': {k: dict(v) for k, v in by.items()}, 'exclusion_codes': dict(codes),
           'ic7_settled_by_script': sum(1 for x in recs if x['ic7_note'].startswith('IC7 not met')),
           'ic7_open_no_count': [x['n'] for x in recs if x['ic7_note'].startswith('IC7 open')],
           'agreement_with_sample_run': dict(agree), 'sample_compared': sum(agree.values()),
           'flagged_already_decided': sum(1 for x in recs if x['already_decided'] and x['after_ic7'] in ('INCLUDE', 'UNSURE')),
           'flagged_for_full_text': len(flagged), 'flagged_in_corpus': sum(1 for x in flagged if x['corpus_folder']),
           'flagged_to_download': sum(1 for x in flagged if not x['corpus_folder'])}
    (RS / 'RESCREEN-RESULT-2026-10-05.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(res, indent=1, ensure_ascii=False))


def folder_of(fid):
    """The folder of a full-text record: p<record> in corpus/ppmlcorpus/check, r<record> a record held elsewhere in the corpus."""
    if fid.startswith('p'):
        return ROOT / 'corpus' / 'ppmlcorpus' / 'check' / fid
    pop = {r['n']: r for r in rows(RS / 'POPULATION-2026-10-05.csv')}
    return ROOT / pop[str(int(fid[1:]))]['corpus_folder']


def fulltext_check():
    """Every full-text record (rescreen/fulltext/<id>.json): the fields of the guide, and every quotation found on its page."""
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from check_sheets import found
    bad = 0
    for f in sorted((RS / 'fulltext').glob('*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        probs, pages = [], folder_of(f.stem) / 'text' / 'pages'
        if d.get('proposed_decision') not in ('INCLUDE', 'EXCLUDE'):
            probs.append(f"proposed_decision {d.get('proposed_decision')!r}")
        if d.get('proposed_decision') == 'EXCLUDE' and not d.get('code'):
            probs.append('EXCLUDE without a code')
        for k, c in (d.get('conditions') or {}).items():
            for ev in c.get('evidence', []):
                pg = pages / f"page_{int(ev['page']):04d}.txt"
                if not pg.exists() or not found(ev['quote'], pg.read_text(encoding='utf-8', errors='ignore')):
                    probs.append(f"{k}: quote not on p{ev['page']}: {ev['quote'][:60]}")
        bad += bool(probs)
        print(f"{f.stem}: {'ok' if not probs else '; '.join(probs[:5])}")
    print(f'{bad} record(s) with problems')
    return bad


def fulltext_result():
    """Merge the full-text records (rescreen/fulltext/<id>.json) with the consistency rules (ADJUDICATION) into
    rescreen/RESCREEN-FULLTEXT-2026-10-05.csv: one row per assessed report, with the proposed decision, the decision after the
    rules, the angles, the reason, any version note, and whether its brief notes pass the checker. Counts are printed."""
    if fulltext_check():
        sys.exit('fix the full-text records first')
    adj = json.loads((RS / 'ADJUDICATION-2026-10-05.json').read_text(encoding='utf-8'))
    changed = {n: c for r in adj['rules'] for n, c in r.get('changes', {}).items()}
    dec = {r['n']: r for r in rows(RS / 'RESCREEN-DECISIONS-2026-10-05.csv')}
    out = []
    for f in sorted((RS / 'fulltext').glob('*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        n = str(d['record'])
        folder = folder_of(f.stem)
        prov = folder / 'PROVENANCE.json'
        chk = folder / 'notes' / 'check.json'
        final, code = d['proposed_decision'], d.get('code', '')
        if n in changed:
            final, code = changed[n]['to'].split()[0], re.sub(r'[()]', '', changed[n]['to'].split(' ', 1)[1]) if ' ' in changed[n]['to'] else ''
        ic3 = (d.get('conditions') or {}).get('IC3') or {}
        out.append({'id': f.stem, 'n': n, 'title': dec.get(n, {}).get('title', ''), 'year': dec.get(n, {}).get('year', ''),
                    'kind': d.get('kind', ''), 'screening': dec.get(n, {}).get('after_ic7', ''),
                    'proposed': d['proposed_decision'], 'decision': final, 'code': code, 'rule': 'R1' if n in changed else '',
                    'angles': '; '.join(ic3.get('angles', [])), 'reason': d.get('reason', ''),
                    'borderline': 'yes' if re.search(r'borderline|may judge|author may|you may', json.dumps(d), re.I) else '',
                    'version_note': json.loads(prov.read_text(encoding='utf-8')).get('version_note', '') if prov.exists() else '',
                    'notes': ('pass' if json.loads(chk.read_text(encoding='utf-8')).get('passed') else 'FAIL') if chk.exists() else 'none',
                    'author': ''})
    f = RS / 'RESCREEN-FULLTEXT-2026-10-05.csv'
    if f.exists():                                                # keep the author's column on a rerun
        prev = {r['id']: r.get('author', '') for r in rows(f)}
        for x in out:
            x['author'] = prev.get(x['id'], '')
    appf = RS / 'AUTHOR-RESCREEN-DECISIONS-2026-10-05.csv'      # decisions taken in the screening app (--rescreen)
    if appf.exists():
        app = {r['n']: r for r in rows(appf)}
        for x in out:
            a = app.get(x['n'])
            if a and a['decision'] in ('INCLUDE', 'EXCLUDE'):
                x['author'] = f"{a['decision']}{(' ' + a['code']) if a['decision'] == 'EXCLUDE' and a['code'] else ''}: " \
                              f"{a['comment'].strip() or 'decided in the screening app'} ({a['decided_at'][:10]})"
            elif a and a['decision'] == 'UNSURE':
                x['author'] = f"UNSURE in the screening app: {a['comment'].strip()}"
    for x in out:                                                 # the author's decision stands over the proposal
        m = re.match(r'^(INCLUDE|EXCLUDE)(?:\s+([A-Z-]+))?\s*:', x['author'] or '')
        if m:
            x['decision'], x['code'] = m.group(1), (m.group(2) or '') if m.group(1) == 'EXCLUDE' else ''
    with open(f, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    c = collections.Counter((x['decision'], x['kind']) for x in out)
    print(f'{len(out)} reports assessed:', dict(c))
    print('exclusion codes:', dict(collections.Counter(x['code'] for x in out if x['decision'] == 'EXCLUDE')))
    print('angles of the included:', dict(collections.Counter(a for x in out if x['decision'] == 'INCLUDE' for a in x['angles'].split('; ') if a)))
    print('notes:', dict(collections.Counter(x['notes'] for x in out)), '| not final versions:', [x['id'] for x in out if x['version_note']])
    print('flagged borderline by the readers:', dict(collections.Counter(x['decision'] for x in out if x['borderline'])))


if __name__ == '__main__':
    {'prepare': prepare, 'check': check, 'result': result, 'fulltext-check': fulltext_check,
     'fulltext-result': fulltext_result}[sys.argv[1]]()
