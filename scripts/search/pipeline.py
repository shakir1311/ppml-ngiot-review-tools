#!/usr/bin/env python3
"""The mechanical steps of the systematic search, screening, full-text and map stages (2 October 2026), as one
re-runnable script. Judgement steps (screening, full-text reading, map classification, survey comparison) are done by
readers following the guides and the prompts in search/prompts/; this script builds their inputs and collects their
outputs. Every step reads saved files and writes saved files, so any step can be re-run and checked.

    python3 scripts/search/pipeline.py <step> [--out DIR]

--out writes the outputs under DIR instead of the workspace (paths kept), so a re-run can be compared with the files
already in the workspace (see `verify`). Steps, in order:

  r1-batches        round-1 screening inputs: calibration batch-00 (corpus records + 37 random, seed 20261002) and
                    batches 01-10                       -> search/screening/input/, search/screening/calibration-key.json
  r1-collect        round-1 decisions -> search/SCREENING-TA-2026-10-02.csv (off-topic surveys coded otherwise are
                    normalised to SURVEY-OFF-TOPIC, as the guide says)
  r2-batches        scope-A screening inputs: records passing round 1, NOT-IOT exclusions, and off-topic surveys that
                    mention a ledger with FL or verification     -> search/screening2/input/
  r2-collect        -> search/SCREENING-A-2026-10-02.csv
  x5-batches        records new after the X5 search (not screened before)  -> search/screening3/input/
  x5-collect        -> search/SCREENING-X5-2026-10-02.csv
  agreement-sample  stratified sample for the second screener (seed 20261009) -> search/check/input/, sample-key.json
  agreement         agreement and Cohen's kappa                          -> search/check/AGREEMENT-2026-10-02.json
  candidates        in-depth candidates (zero-knowledge proofs, journal articles) from rounds A and X5
                    -> search/INDEPTH-CANDIDATES-PART1/2-2026-10-02.json (open-access fields kept from the saved files)
  fulltext-collect  full-text decisions from the evidence sheets and the recorded borderline judgements
                    -> search/FULLTEXT-DECISIONS-2026-10-02.csv, search/fulltext/DECISIONS.json
  map-batches       map inputs (scope-A primary studies not excluded at full text) -> search/map/input/
  map-collect       map batches + consistency review -> search/map/MAP-2026-10-02.csv
  verify            re-run the offline steps into a scratch folder and compare every output with the workspace

Network steps (the database exports, OpenAlex lookups, open-access fetches, SJR matching) are not re-run here: their
saved results are the record (search/exports/, search/citation/, search/quality/).
"""
import collections, csv, filecmp, glob, json, os, pathlib, random, re, shutil, sys, tempfile

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT
D = '2026-10-02'


def src(p):
    return ROOT / p


def dst(p):
    q = OUT / p
    q.parent.mkdir(parents=True, exist_ok=True)
    return q


def read_csv(p):
    return list(csv.DictReader(open(src(p), encoding='utf-8')))


def jsonl(p, rows):
    with open(dst(p), 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def rec(r):
    return {'n': int(r['n']), 'title': r['title'], 'year': r['year'], 'venue': r['venue'], 'type': r['type'],
            'keywords': r['keywords'][:600], 'abstract': r['abstract']}


def load_outputs(folder, k):
    out = {}
    for i in range(k[0], k[1] + 1):
        for o in json.load(open(src(f'{folder}/output/batch-{i:02d}.json'))):
            o['batch'] = f'{i:02d}'
            out[o['n']] = o
    return out


# ------------------------------------------------------------------ round 1
def r1_batches():
    rows = [r for r in read_csv(f'search/MERGED-RECORDS-{D}.csv') if not r['auto_excluded']]
    random.seed(20261002)
    corpus = [r for r in rows if r['corpus_id']]
    others = [r for r in rows if not r['corpus_id']]
    random.shuffle(others)
    calib = corpus + others[:37]
    rest = others[37:]
    random.shuffle(calib)
    jsonl('search/screening/input/batch-00.jsonl', [rec(r) for r in sorted(calib, key=lambda r: int(r['n']))])
    rest.sort(key=lambda r: int(r['n']))
    size = -(-len(rest) // 10)
    for i in range(10):
        jsonl(f'search/screening/input/batch-{i + 1:02d}.jsonl', [rec(r) for r in rest[i * size:(i + 1) * size]])
    json.dump({r['n']: r['corpus_id'] for r in corpus}, open(dst('search/screening/calibration-key.json'), 'w'), indent=1)


def r1_collect():
    allo = load_outputs('search/screening', (0, 10))
    rows = [r for r in read_csv(f'search/MERGED-RECORDS-{D}.csv') if not r['auto_excluded']]
    surv = re.compile(r'\b(survey|review|sok|systematic literature|systematization|systematisation|overview|tutorial)\b', re.I)
    with open(dst(f'search/SCREENING-TA-{D}.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['n', 'decision', 'code', 'route', 'reason', 'batch', 'title', 'year', 'venue', 'type', 'doi', 'sources',
                    'corpus_id', 'code_note'])
        for r in sorted(rows, key=lambda r: int(r['n'])):
            o = allo[int(r['n'])]
            code, note = o['code'], ''
            if o['decision'] == 'EXCLUDE' and code in ('NOT-FL', 'NOT-SCOPE', 'NOT-IOT') and (r['type'] == 'Review' or surv.search(r['title'])):
                note = f'survey: code {code} normalised to SURVEY-OFF-TOPIC (guide clarification of 2 Oct)'
                code = 'SURVEY-OFF-TOPIC'
            w.writerow([r['n'], o['decision'], code, o['route'], o['reason'], o['batch'], r['title'], r['year'], r['venue'],
                        r['type'], r['doi'], r['sources'], r['corpus_id'], note])


# ------------------------------------------------------------------ round 2 (scope A)
def r2_batches():
    d = {int(x['n']): x for x in read_csv(f'search/SCREENING-TA-{D}.csv')}
    m = {int(r['n']): r for r in read_csv(f'search/MERGED-RECORDS-{D}.csv')}
    T = lambda n: (m[n]['title'] + ' ' + m[n]['abstract'] + ' ' + m[n]['keywords']).lower()
    fw = [n for n, x in d.items() if x['decision'] != 'EXCLUDE']
    notiot = [n for n, x in d.items() if x['decision'] == 'EXCLUDE' and x['code'] == 'NOT-IOT']
    surv = [n for n, x in d.items() if x['decision'] == 'EXCLUDE' and x['code'] == 'SURVEY-OFF-TOPIC'
            and re.search(r'blockchain|block-chain|distributed ledger|smart contract', T(n))
            and re.search(r'federated|zero.?knowledge|verifiab', T(n))]
    S = sorted(set(fw) | set(notiot) | set(surv))
    size = -(-len(S) // 6)
    for i in range(6):
        jsonl(f'search/screening2/input/batch-{i + 1:02d}.jsonl', [rec(m[n]) for n in S[i * size:(i + 1) * size]])
    json.dump({'forward': sorted(fw), 'not_iot': sorted(notiot), 'surveys_rechecked': sorted(surv)},
              open(dst('search/screening2/SELECTION.json'), 'w'), indent=1)


def collect_scope_a(folder, k, out, first_round=True):
    allo = load_outputs(folder, k)
    d1 = {int(x['n']): x for x in read_csv(f'search/SCREENING-TA-{D}.csv')} if first_round else {}
    m = {int(r['n']): r for r in read_csv(f'search/MERGED-RECORDS-{D}-X5.csv' if not first_round else f'search/MERGED-RECORDS-{D}.csv')}
    with open(dst(out), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        head = ['n', 'decision', 'code', 'iot', 'check', 'reason', 'batch']
        head += ['first_round_decision'] if first_round else []
        head += ['title', 'year', 'venue', 'type', 'doi', 'sources', 'corpus_id']
        w.writerow(head)
        for n in sorted(allo):
            o = allo[n]
            x = d1[n] if first_round else m[n]
            row = [n, o['decision'], o['code'], o['iot'], o.get('check', ''), o['reason'], o['batch']]
            row += [x['decision']] if first_round else []
            row += [x['title'], x['year'], x['venue'], x['type'], x['doi'], x['sources'], x['corpus_id']]
            w.writerow(row)


def r2_collect():
    collect_scope_a('search/screening2', (1, 6), f'search/SCREENING-A-{D}.csv')


def x5_batches():
    new = {r['n']: r for r in read_csv(f'search/MERGED-RECORDS-{D}-X5.csv')}
    screened = {r['n'] for r in read_csv(f'search/SCREENING-TA-{D}.csv')}
    todo = sorted([n for n, r in new.items() if not r['auto_excluded'] and n not in screened], key=int)
    half = -(-len(todo) // 2)
    for i, part in enumerate((todo[:half], todo[half:]), 1):
        jsonl(f'search/screening3/input/batch-{i:02d}.jsonl', [rec(new[n]) for n in part])


def x5_collect():
    collect_scope_a('search/screening3', (1, 2), f'search/SCREENING-X5-{D}.csv', first_round=False)


# ------------------------------------------------------------------ agreement check
def agreement_sample():
    L = read_csv(f'search/RECORD-LEDGER-{D}.csv')
    m = {r['n']: r for r in read_csv(f'search/MERGED-RECORDS-{D}.csv')}
    random.seed(20261002 + 7)
    prim = [r for r in L if r['status'] == 'scope A, primary']
    surv = [r for r in L if r['status'] == 'survey (related work)']
    exc = [r for r in L if r['status'].startswith('excluded')]
    s = random.sample(prim, 60) + random.sample(surv, 20) + random.sample(exc, 120)
    random.shuffle(s)
    jsonl('search/check/input/sample.jsonl', [rec(m[r['n']]) for r in s])
    json.dump({'note': 'Stratified random sample for an independent second screening (seed 20261009): 60 of 273 scope-A primary '
                       'candidates, 20 of 63 surveys, 120 of 1,958 excluded records. The key is kept apart from the screener.',
               'strata': {r['n']: r['status'] for r in s}}, open(dst('search/check/sample-key.json'), 'w'), indent=1)


def agreement():
    key = json.load(open(src('search/check/sample-key.json')))['strata']
    sec = json.load(open(src('search/check/output/second-screen.json')))
    first = lambda s: 'EXCLUDE' if s.startswith('excluded') else 'FORWARD'
    second = lambda d: 'EXCLUDE' if d == 'EXCLUDE' else 'FORWARD'
    b = [(first(key[str(o['n'])]) == 'FORWARD', second(o['decision']) == 'FORWARD') for o in sec]
    n = len(b)
    po = sum(1 for a, c in b if a == c) / n
    p1, p2 = sum(a for a, _ in b) / n, sum(c for _, c in b) / n
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    res = {'n': n, 'agreement_percent': round(100 * po, 1), 'cohen_kappa': round((po - pe) / (1 - pe), 2),
           'excluded_by_first_marked_forward_by_second': sum(1 for a, c in b if not a and c),
           'excluded_sampled': sum(1 for a, _ in b if not a),
           'forward_by_first_excluded_by_second': sum(1 for a, c in b if a and not c)}
    json.dump(res, open(dst('search/check/AGREEMENT-COMPUTED.json'), 'w'), indent=1)
    print(res)


# ------------------------------------------------------------------ in-depth candidates
ZK = re.compile(r'zero.?knowledge|zk-?snark|\bzkp|bulletproof|range proof|zk-?stark|\bplonk|groth', re.I)
CONF = re.compile(r'conference|symposium|workshop|proceedings|congress|lecture notes', re.I)


def candidates():
    m = {r['n']: r for r in read_csv(f'search/MERGED-RECORDS-{D}-X5.csv')}
    for part, f in (('PART1', f'search/SCREENING-A-{D}.csv'), ('PART2', f'search/SCREENING-X5-{D}.csv')):
        saved = {c['n']: c for c in json.load(open(src(f'search/INDEPTH-CANDIDATES-{part}-{D}.json')))}
        out = []
        for r in read_csv(f):
            if r['decision'] not in ('INCLUDE-PRIMARY', 'UNSURE'):
                continue
            x = m[r['n']]
            if not ZK.search(' '.join([r['check'], r['reason'], x['title'], x['abstract'], x['keywords']])):
                continue
            if CONF.search(x['venue']) or x['type'].lower().startswith('conference'):
                continue
            c = {'n': int(r['n']), 'decision': r['decision'], 'title': x['title'], 'year': x['year'], 'venue': x['venue'],
                 'doi': x['doi'], 'corpus_id': x['corpus_id']}
            for k in ('oa', 'oa_pdf', 'fetched'):          # network results kept from the saved file
                if k in saved.get(c['n'], {}):
                    c[k] = saved[c['n']][k]
            out.append(c)
        json.dump(out, open(dst(f'search/INDEPTH-CANDIDATES-{part}-{D}.json'), 'w'), indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ full-text decisions
def fulltext_collect():
    chk = {r['id']: r for r in json.load(open(src('search/fulltext/CHECK-SHEETS.json')))}
    st = {r['id']: r for r in read_csv(f'search/INDEPTH-STATUS-{D}.csv')}
    border = json.load(open(src(f'search/fulltext/BORDERLINE-{D}.json')))
    rows = []
    for f in sorted(glob.glob(str(src('search/fulltext/sheets/*.json')))):
        s = json.load(open(f))
        i = s['id']
        rec_, code = s['eligibility']['decision'], s['eligibility'].get('code', '')
        b = border.get(i)
        final = rec_ if not b else ('INCLUDE' if b[0] == 'include' else 'EXCLUDE')
        fcode = code if not b or b[0] == 'include' else 'NO-CHECK'
        rows.append({'id': i, 'corpus_id': s.get('corpus_id', ''), 'title': st[i]['title'], 'venue': st[i]['venue'],
                     'year': st[i]['year'], 'reader_decision': rec_, 'reader_code': code, 'recommended': final,
                     'recommended_code': fcode, 'reason': s['eligibility']['reason'], 'borderline_note': b[1] if b else '',
                     'quotes': chk[i]['quotes'], 'table_image_values': len(chk[i]['manual']),
                     'table_image_checked': 'yes' if chk[i]['manual'] else ''})
    with open(dst(f'search/FULLTEXT-DECISIONS-{D}.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    json.dump(rows, open(dst('search/fulltext/DECISIONS.json'), 'w'), indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ map
def map_batches():
    L = read_csv(f'search/RECORD-LEDGER-{D}-X5.csv')
    m = {r['n']: r for r in read_csv(f'search/MERGED-RECORDS-{D}-X5.csv')}
    keep = [r for r in L if r['status'] in ('scope A, primary', 'included in depth') or r['status'].startswith('excluded IC7')]
    keep.sort(key=lambda r: int(r['n']))
    size = -(-len(keep) // 4)
    for i in range(4):
        jsonl(f'search/map/input/batch-{i + 1:02d}.jsonl',
              [{k: v for k, v in rec(m[r['n']]).items() if k != 'type'} for r in keep[i * size:(i + 1) * size]])


def map_collect():
    M = {}
    for f in sorted(glob.glob(str(src('search/map/output/batch-*.json')))):
        for o in json.load(open(f)):
            o['type'], o['reviewed'] = 'primary', False
            M[o['n']] = o
    for o in json.load(open(src('search/map/consolidate/output.json'))):
        o['reviewed'] = True
        M[o['n']] = o
    Q = json.load(open(src(f'search/quality/MAP-QUARTILES-{D}.json')))
    L = {r['n']: r for r in read_csv(f'search/RECORD-LEDGER-{D}-X5.csv')}
    rows = []
    for n, o in sorted(M.items()):
        r = L[str(n)]
        rows.append({'n': n, 'title': r['title'], 'year': r['year'], 'venue': r['venue'], 'quartile': Q[str(n)]['q2025'],
                     'status': r['status'], 'type': o.get('type', 'primary'),
                     **{k: '; '.join(o[k]) for k in ('privacy', 'check', 'checked_property', 'threats', 'ledger', 'setting', 'evaluation')},
                     'note': o.get('note', ''), 'consistency_reviewed': o['reviewed']})
    with open(dst(f'search/map/MAP-{D}.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


# ------------------------------------------------------------------ verify
OFFLINE = {
    'r1-batches': ['search/screening/input/batch-%02d.jsonl' % i for i in range(11)] + ['search/screening/calibration-key.json'],
    'r1-collect': [f'search/SCREENING-TA-{D}.csv'],
    'r2-batches': ['search/screening2/input/batch-%02d.jsonl' % i for i in range(1, 7)] + ['search/screening2/SELECTION.json'],
    'r2-collect': [f'search/SCREENING-A-{D}.csv'],
    'x5-batches': ['search/screening3/input/batch-01.jsonl', 'search/screening3/input/batch-02.jsonl'],
    'x5-collect': [f'search/SCREENING-X5-{D}.csv'],
    'agreement-sample': ['search/check/input/sample.jsonl', 'search/check/sample-key.json'],
    'candidates': [f'search/INDEPTH-CANDIDATES-PART1-{D}.json', f'search/INDEPTH-CANDIDATES-PART2-{D}.json'],
    'fulltext-collect': [f'search/FULLTEXT-DECISIONS-{D}.csv', 'search/fulltext/DECISIONS.json'],
    'map-batches': ['search/map/input/batch-%02d.jsonl' % i for i in range(1, 5)],
    'map-collect': [f'search/map/MAP-{D}.csv'],
}


def same(a, b):
    if a.suffix == '.json':
        return json.load(open(a)) == json.load(open(b))
    return filecmp.cmp(a, b, shallow=False)


def verify():
    global OUT
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='pipeline-verify-'))
    OUT = tmp
    report = {}
    for step, files in OFFLINE.items():
        STEPS[step]()
        report[step] = {f: ('identical' if same(tmp / f, ROOT / f) else 'DIFFERENT') for f in files}
        ok = all(v == 'identical' for v in report[step].values())
        print(f'{step:18} {"identical" if ok else "DIFFERENT"} ({len(files)} file(s))')
        for f, v in report[step].items():
            if v != 'identical':
                print('   ', f)
    agreement()
    shutil.rmtree(tmp)
    OUT = ROOT
    json.dump(report, open(ROOT / 'search' / 'PIPELINE-VERIFY.json', 'w'), indent=1)


STEPS = {'r1-batches': r1_batches, 'r1-collect': r1_collect, 'r2-batches': r2_batches, 'r2-collect': r2_collect,
         'x5-batches': x5_batches, 'x5-collect': x5_collect, 'agreement-sample': agreement_sample, 'agreement': agreement,
         'candidates': candidates, 'fulltext-collect': fulltext_collect, 'map-batches': map_batches,
         'map-collect': map_collect, 'verify': verify}

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] not in STEPS:
        sys.exit(__doc__)
    if '--out' in a:
        OUT = pathlib.Path(a[a.index('--out') + 1]).resolve()
    STEPS[a[0]]()
