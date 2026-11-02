#!/usr/bin/env python3
"""Reframe the evidence sheets for the three review questions of 15 October 2026 (EXTRACTION-GUIDE-V2-2026-10-15.md).

Primary sheets: three answers are added, drafted from the design's own page-cited notes (notes/NOTES.md, our words) and
the extracted pages (text/pages/page_NNNN.txt): the notes' statements on the subject give the pages, and the quotations
are copied character for character from those pages (hyphenation at line ends joined). The tags come from the notes'
wording and the sheet's P1; the answer text carries the notes' statements. Where the notes do not settle an answer it
reads "Not stated (not settled from the notes …)" with the terms searched, for the author or a reader to settle.
  P1b  cost at the edge and on the ledger     (costs_reported, cost_where)
  P3b  parties still trusted                  (trusted)
  P6b  evaluation environment and scale       (environment, scale)
The P4 tags zk_on_chain and verification_other_means are removed.
Secondary sheets: S2 and S4 are kept (S4 without the verification and zkp tags; sentences of its answer that speak only
of verification or proofs are dropped); S1, S3, S5, S6, S7 and S8 are removed.

Every sheet changed is first copied to notes-verifier/history/<id>/ (SHEET-original.json if absent, and
SHEET-before-reframe-<stamp>.json). The Sheet Reviewer's record (notes-verifier/data/sheet-review.json, copied first to
notes-verifier/history/_sheet-review-before-reframe-<stamp>.json) gets an unticked entry per new answer (new_on), so a
new answer is never ticked by default; entries of removed answers stay as an audit trail. The log is
search-ppml/evidence/REFRAME-2026-10-15.jsonl, one line per sheet. Nothing of the papers' text is printed: counts only.

Usage: python3 scripts/paper_ppml/reframe_sheets.py [--dry-run]
"""
import csv, datetime, json, pathlib, re, sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
SHEETS = P / 'evidence' / 'sheets'
HIST = ROOT / 'notes-verifier' / 'history'
RECORD = ROOT / 'notes-verifier' / 'data' / 'sheet-review.json'
LOG = P / 'evidence' / 'REFRAME-2026-10-15.jsonl'
STAMP = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
NOW = datetime.datetime.now().isoformat(timespec='seconds')

ORDER_P = ['P1', 'P1b', 'P2', 'P3', 'P3b', 'P4', 'P5', 'P6', 'P6b', 'P7', 'P8']
ORDER_S = ['S2', 'S4']
DROP_P4 = ('zk_on_chain', 'verification_other_means')
DROP_S4 = ('verification', 'zkp')

TAG = re.compile(r'\[(p\d+[^\[\]]*)\]')
PAGE = re.compile(r'p(\d+)(?:\s*[–-]\s*p?(\d+))?')

# ---- what the notes say, by subject (patterns on our own words) ------------------------------------------------------
COSTS = {
    'computation-time': r'\b(computation(al)? (time|cost|overhead)|training time|running time|execution time|proving time|verification time|'
                        r'encryption time|aggregation time|time per round|takes (about |around )?[\d.]+ ?(s|ms|seconds|minutes)\b|\b[\d.]+ ?(ms|s|seconds) (per|for|longer))',
    'latency': r'\blatenc', 'throughput': r'\bthroughput|\bTPS\b|transactions per second',
    'storage': r'\bstorage|block size|ledger size|chain size|memory (use|usage|footprint)|\bRAM\b|\bmemory\b',
    'communication': r'communication (cost|overhead|volume|rounds)|\b(bytes|kB|KB|MB) per (round|iteration|client|user|training)|payload|upload|bandwidth',
    'gas': r'\bgas\b', 'energy': r'\benergy|\bjoule|power (consumption|meter)|\bmW\b'}
COST_WHERE = {'simulation': r'simulat', 'server-workstation': r'\b(server|workstation|desktop|laptop|GPU|RTX|Xeon|cluster|PC|computer|machine)\b'}
TRUSTED = {
    'trusted-authority-key-centre': r'trusted (authority|third party|party|key|set-?up server)|key (generation |distribution )?(cent(re|er)|authority)|\bKGC\b|issues (all )?(the )?keys|key centre|key center',
    'certificate-authority': r'certificate authorit|\bCA\b|registers each (device|client|participant)',
    'server-aggregator': r'(server|aggregator|publisher|cloud provider|analyst|curator)[^.;]{0,60}\b(trusted|honest[- ]but[- ]curious|semi-honest)|honest[- ]but[- ]curious[^.;]{0,30}(server|aggregator|publisher)|trusted (server|aggregator)|holds the (only )?(private )?key|only the (task )?publisher can decrypt',
    'non-colluding-servers': r'non-?colluding|two (non-colluding )?servers|helper server|assisting server',
    'enclave-TEE': r'\bSGX\b|enclave|\bTEE\b|trusted execution|attestation',
    'committee-honest-majority': r'honest majority|majority (of|are) honest|two[- ]thirds|fewer than half|less than (a third|one third|1/3)|at most \S+ (colluding|malicious)|\b(committee|validators|nodes|miners) (are|is) (assumed )?honest|honest (committee|validators|nodes)',
    'trusted-setup': r'trusted set-?up',
    'none': r'no (trusted|central) (party|authority|curator|server)|without (any |a )?trusted (party|third party|authority)|no curator is trusted|trustless|no party is trusted|not trusted'}
ENV = {
    'real-devices': r'Raspberry|Jetson|test ?bed|real (devices|hardware|deployment|vehicles|edge devices)|prototype (deployed|built|run)|\b(edge|IoT|end) devices\b[^.;]{0,30}(measured|timed|run|ran)|Cortex|smartphone|boards|microcontroller',
    'emulation': r'emulat', 'simulation': r'simulat|\bNS-?3\b|\bSUMO\b|OMNeT|TOSSIM',
    'server-experiment': r'(on|using) (one|a single|an?) (server|machine|computer|desktop|laptop|workstation|GPU|PC)|\b(GPU|RTX|Xeon|workstation|desktop|laptop|server)\b[^.;]{0,40}(timed|measured|run|ran|trained|experiment)|experiments? (ran|run|were run) on',
    'none': r'no experiment|not evaluated|no (evaluation|results? (is|are) reported)|four lemmas|no (dataset|data set), timing or hardware|no result is reported'}
EVAL_WORDS = r'simulat|emulat|evaluat|experiment|test ?bed|tested|accuracy|data ?set|clients|nodes|vehicles|Raspberry|Jetson|devices|workers|participants|users'
SCALE_UNIT = r'\s*(clients|nodes|devices|vehicles|workers|participants|users|hospitals|edge servers|validators|miners|organisations|organizations|parties|contributors|peers|institutions|boards|providers)\b'

SEARCHED = {'P1b': ['latency', 'throughput', 'storage', 'communication', 'gas', 'energy', 'time'],
            'P3b': ['trusted', 'honest-but-curious', 'key', 'authority', 'enclave', 'collud'],
            'P6b': ['simulation', 'emulation', 'testbed', 'Raspberry', 'Jetson', 'clients', 'nodes']}


def studies():
    return {r['corpus_id']: r for r in csv.DictReader(open(P / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8'))}


def folders():
    return {r['corpus_id']: ROOT / r['folder'] for r in csv.DictReader(open(ROOT / 'corpus' / 'ppmlcorpus' / 'included' / 'INDEX.csv', encoding='utf-8'))}


# ---- the notes ------------------------------------------------------------------------------------------------------
def notes(folder):
    """(front matter dict, [(statement text, [pages])]) from notes/NOTES.md; a statement is a line or a sentence, with the
    pages of the nearest [pN] tag after it in its line (else before)"""
    f = folder / 'notes' / 'NOTES.md'
    if not f.exists():
        return {}, []
    t = f.read_text(encoding='utf-8', errors='replace')
    fm = {}
    if t.startswith('---'):
        head, _, t = t[3:].partition('\n---')
        for line in head.splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                fm[k.strip()] = v.strip().strip('"')
    out = []
    for line in t.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        tags = [(m.start(), pages_of(m.group(1))) for m in TAG.finditer(line)]
        if not tags:
            continue
        plain = line.lstrip('-*• ').strip()
        for s in re.split(r'(?<=[.!?\]])\s+(?=[A-Z(])', plain):
            s = s.strip()
            if len(s) < 12:
                continue
            pos = line.find(s[:30])
            after = [pg for p0, pg in tags if p0 >= pos]
            before = [pg for p0, pg in tags if p0 < pos]
            pg = (after[0] if after else before[-1]) if (after or before) else []
            own = [pages_of(m.group(1)) for m in TAG.finditer(s)]
            pages = sorted({x for lst in (own or [pg]) for x in lst})
            out.append((TAG.sub('', s).strip(), pages))
    return fm, out


def pages_of(tag):
    pages = []
    for m in PAGE.finditer(tag):
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        pages += list(range(a, min(b, a + 6) + 1))
    return pages


# ---- the pages ------------------------------------------------------------------------------------------------------
_PAGES = {}


def page_text(folder, n):
    k = (str(folder), n)
    if k not in _PAGES:
        t = ''
        for d in ('pages', 'pages_ocr'):
            f = folder / 'text' / d / f'page_{n:04d}.txt'
            if f.exists():
                t = f.read_text(encoding='utf-8', errors='ignore')
                if t.strip():
                    break
        t = re.sub(r'-\s*\n\s*', '', t)                      # a word broken over a line end is one word
        _PAGES[k] = re.sub(r'\s+', ' ', t).strip()
    return _PAGES[k]


def quotes_on(folder, n, pattern, limit=2):
    """verbatim sentences of page n that match the pattern, cut to at most 40 words around the match"""
    out = []
    for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9(])', page_text(folder, n)):
        m = re.search(pattern, s, re.I)
        if not m:
            continue
        words = s.split()
        if len(words) < 5:
            continue
        if len(words) > 40:
            at = len(s[:m.start()].split())
            lo = max(0, min(at - 15, len(words) - 40))
            words = words[lo:lo + 40]
        q = ' '.join(words).strip(' ,;:')
        if '…' in q or '...' in q:
            continue
        out.append(q)
        if len(out) >= limit:
            break
    return out


def pages_all(folder):
    return sorted(int(re.search(r'(\d+)', f.name).group(1)) for f in (folder / 'text' / 'pages').glob('page_*.txt'))


def evidence_for(folder, statements, pattern, limit=3):
    """quotations for a subject: from the pages the matching statements cite, in order; then from any page of the paper
    (counts only are reported); returns (evidence, how)"""
    pages, seen = [], set()
    for text, pg in statements:
        for n in pg:
            if n not in seen:
                seen.add(n)
                pages.append(n)
    ev = []
    for n in pages[:6]:
        for q in quotes_on(folder, n, pattern):
            ev.append({'page': n, 'quote': q})
            if len(ev) >= limit:
                return ev, 'cited pages'
    if ev:
        return ev, 'cited pages'
    for n in pages_all(folder):
        for q in quotes_on(folder, n, pattern, limit=1):
            ev.append({'page': n, 'quote': q})
            if len(ev) >= 2:
                return ev, 'other pages'
    return ev, ('other pages' if ev else 'none')


ASIDE = r'dismiss|comparator|related work|as options|named only|only in (related|passing)|mentioned only|in passing|for future work|future work|not used|no (TEE|enclave|SGX)'


def hits(statements, pattern):
    """statements that speak of the subject, leaving out those that only compare, dismiss or defer it"""
    return [(t, pg) for t, pg in statements if re.search(pattern, t, re.I) and not re.search(ASIDE, t, re.I)]


def words(text, n=45):
    w = text.split()
    return ' '.join(w[:n]) + ('…' if len(w) > n else '')


def not_stated(key):
    return {'answer': 'Not stated (not settled from the notes; to be settled from the paper).', 'values': {},
            'evidence': [], 'located_via': 'notes', 'searched': SEARCHED[key]}


# ---- the three new answers --------------------------------------------------------------------------------------------
def p1b(sheet, folder, fm, st):
    found = {k: hits(st, pat) for k, pat in COSTS.items()}
    costs = [k for k, h in found.items() if h]
    if not costs:
        a = not_stated('P1b'); a['values'] = {'costs_reported': ['none'], 'cost_where': 'not-stated'}
        a['answer'] = 'Not stated (the notes report no cost of the learning, the protection or the ledger).'
        return a, 'none'
    cost_st = sorted({(t, tuple(pg)) for h in found.values() for t, pg in h}, key=lambda x: (-bool(re.search(r'\d', x[0])), x[0]))
    cost_st = [(t, list(pg)) for t, pg in cost_st]
    p1 = (sheet['answers'].get('P1') or {}).get('values') or {}
    joined = ' '.join(t for t, _ in cost_st)
    if p1.get('device_measured') == 'yes':
        where = 'device-class'
    elif re.search(COST_WHERE['simulation'], joined, re.I):
        where = 'simulation'
    elif re.search(COST_WHERE['server-workstation'], joined, re.I):
        where = 'server-workstation'
    else:
        where = 'not-stated'
    pattern = '|'.join(COSTS[k] for k in costs)
    ev, how = evidence_for(folder, cost_st, pattern)
    WHERE = {'device-class': 'on device-class hardware', 'simulation': 'in simulation', 'server-workstation': 'on servers or workstations', 'not-stated': 'where not stated'}
    ans = f"Costs reported: {', '.join(costs)}; measured {WHERE[where]}. " + words(' '.join(t for t, _ in cost_st[:2]), 50)
    return {'answer': ans, 'values': {'costs_reported': costs, 'cost_where': where}, 'evidence': ev, 'located_via': 'notes', 'searched': []}, how


def p3b(sheet, folder, fm, st):
    found = {k: hits(st, pat) for k, pat in TRUSTED.items()}
    trusted = [k for k, h in found.items() if h and k != 'none']
    none = bool(found['none']) and not trusted
    if not trusted and not none:
        a = not_stated('P3b'); a['values'] = {'trusted': ['not-stated']}
        return a, 'none'
    vals = ['none'] if none else trusted
    sts = sorted({(t, tuple(pg)) for k in (['none'] if none else trusted) for t, pg in found[k]})
    sts = [(t, list(pg)) for t, pg in sts]
    pattern = '|'.join(TRUSTED[k] for k in (['none'] if none else trusted))
    ev, how = evidence_for(folder, sts, pattern)
    ans = f"Trusted: {', '.join(vals)}. " + words(' '.join(t for t, _ in sts[:2]), 50)
    return {'answer': ans, 'values': {'trusted': vals}, 'evidence': ev, 'located_via': 'notes', 'searched': []}, how


def p6b(sheet, folder, fm, st):
    ev_st = hits(st, EVAL_WORDS)
    found = {k: hits(ev_st, pat) for k, pat in ENV.items()}
    env = [k for k in ('real-devices', 'emulation', 'simulation', 'server-experiment') if found[k]]
    et = fm.get('evaluation_type', '')
    if not env and 'prototype or testbed' in et:
        env = ['real-devices']
    if not env and ('experiment on datasets' in et or hits(ev_st, r'accuracy|data ?set')):
        env = ['server-experiment']
    if found['none'] and not env:
        env = ['none']
    scale = 0
    for t, _ in ev_st:
        for m in re.finditer(r'(?<![\d.%])(\d{1,6})(?![\d%])(?: to \d{1,6})?' + SCALE_UNIT, t, re.I):
            n = int(re.findall(r'\d+', m.group(0))[-1]) if ' to ' in m.group(0) else int(m.group(1))
            if 1 <= n <= 100000 and not (1990 <= n <= 2030):
                scale = max(scale, n)
    if not env:
        a = not_stated('P6b'); a['values'] = {'environment': ['not-stated'], 'scale': 'not stated'}
        return a, 'none'
    sts = sorted({(t, tuple(pg)) for k in env for t, pg in found.get(k, [])} | {(t, tuple(pg)) for t, pg in ev_st if re.search(SCALE_UNIT, t, re.I)})
    sts = [(t, list(pg)) for t, pg in sts] or ev_st[:3]
    pattern = '|'.join(ENV[k] for k in env if k != 'server-experiment') or EVAL_WORDS
    ev, how = evidence_for(folder, sts, pattern)
    ans = f"Environment: {', '.join(env)}; largest scale in the evaluation: {scale if scale else 'not stated'}. " + words(' '.join(t for t, _ in sts[:2]), 50)
    return {'answer': ans, 'values': {'environment': env, 'scale': scale if scale else 'not stated'}, 'evidence': ev, 'located_via': 'notes', 'searched': []}, how


# ---- the secondary sheets ----------------------------------------------------------------------------------------------
def trim_s4(answer):
    keep = []
    for s in re.split(r'(?<=[.!?;])\s+', answer):
        only_dropped = re.search(r'verif|zero[- ]knowledge|\bZKP|proof', s, re.I) and not re.search(
            r'poison|malicious|fake|sybil|byzantine|free[- ]rid|blockchain|ledger|chain', s, re.I)
        if not only_dropped:
            keep.append(s)
    return ' '.join(keep).strip() or answer


# ---- the run --------------------------------------------------------------------------------------------------------
def main(dry):
    S, F = studies(), folders()
    record = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.exists() else {}
    log, totals = [], {'added': 0, 'unsettled': {'P1b': 0, 'P3b': 0, 'P6b': 0}, 'from_other_pages': 0, 'removed_answers': 0, 'removed_tags': 0, 'quotes': 0}
    for cid in sorted(S):
        path = SHEETS / f'{cid}.json'
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        sheet = json.loads(text)
        A = sheet['answers']
        entry = {'id': cid, 'kind': S[cid]['kind'], 'added': {}, 'removed': [], 'unsettled': []}
        if S[cid]['kind'] == 'primary':
            fm, st = notes(F[cid])
            for key, fn in (('P1b', p1b), ('P3b', p3b), ('P6b', p6b)):
                if key in A:
                    continue
                a, how = fn(sheet, F[cid], fm, st)
                A[key] = a
                entry['added'][key] = {'values': a['values'], 'quotes': len(a['evidence']), 'quotes_from': how}
                totals['added'] += 1; totals['quotes'] += len(a['evidence'])
                if a['answer'].lower().startswith('not stated'):
                    entry['unsettled'].append(key); totals['unsettled'][key] += 1
                if how == 'other pages':
                    totals['from_other_pages'] += 1
            for tag in DROP_P4:
                if tag in ((A.get('P4') or {}).get('values') or {}):
                    del A['P4']['values'][tag]; entry['removed'].append(f'P4.{tag}'); totals['removed_tags'] += 1
            sheet['answers'] = {k: A[k] for k in ORDER_P if k in A}
        else:
            for key in list(A):
                if key not in ORDER_S:
                    del A[key]; entry['removed'].append(key); totals['removed_answers'] += 1
            for tag in DROP_S4:
                if tag in ((A.get('S4') or {}).get('values') or {}):
                    del A['S4']['values'][tag]; entry['removed'].append(f'S4.{tag}'); totals['removed_tags'] += 1
            if 'S4' in A and A['S4'].get('answer'):
                A['S4']['answer'] = trim_s4(A['S4']['answer'])
            sheet['answers'] = {k: A[k] for k in ORDER_S if k in A}
        for key in entry['added']:
            record.setdefault(cid, {}).setdefault(key, {'verified': False, 'new_on': NOW, 'how': 'new fact'})
        log.append(entry)
        if not dry:
            hist = HIST / cid
            hist.mkdir(parents=True, exist_ok=True)
            if not (hist / 'SHEET-original.json').exists():
                (hist / 'SHEET-original.json').write_text(text, encoding='utf-8')
            (hist / f'SHEET-before-reframe-{STAMP}.json').write_text(text, encoding='utf-8')
            indent = re.match(r'\{\n( +)"', text)
            path.write_text(json.dumps(sheet, indent=len(indent.group(1)) if indent else 1, ensure_ascii=False) + ('\n' if text.endswith('\n') else ''), encoding='utf-8')
    if not dry:
        if RECORD.exists():
            (HIST / f'_sheet-review-before-reframe-{STAMP}.json').write_text(RECORD.read_text(encoding='utf-8'), encoding='utf-8')
        RECORD.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding='utf-8')
        with open(LOG, 'a', encoding='utf-8') as fh:
            for e in log:
                fh.write(json.dumps({'on': NOW, **e}, ensure_ascii=False) + '\n')
    n_p = sum(1 for e in log if e['kind'] == 'primary'); n_s = len(log) - n_p
    print(f"{'DRY RUN: ' if dry else ''}{n_p} primary sheets: {totals['added']} answers added ({totals['quotes']} quotations; "
          f"{totals['from_other_pages']} answers quoted from pages the notes did not cite), unsettled from the notes: "
          f"P1b {totals['unsettled']['P1b']}, P3b {totals['unsettled']['P3b']}, P6b {totals['unsettled']['P6b']}; "
          f"{totals['removed_tags']} tags removed; {n_s} survey sheets: {totals['removed_answers']} answers removed")
    from collections import Counter
    for key in ('P1b', 'P3b', 'P6b'):
        c = Counter()
        for e in log:
            v = e['added'].get(key, {}).get('values', {})
            for k, x in v.items():
                for y in (x if isinstance(x, list) else [x]):
                    if k != 'scale':
                        c[f'{k}={y}'] += 1
        print(f'  {key}:', dict(c.most_common()))
    sc = [e['added'].get('P6b', {}).get('values', {}).get('scale') for e in log if e['kind'] == 'primary']
    print('  P6b scale found for', sum(1 for x in sc if isinstance(x, int)), 'designs')
    print('  quotations per new answer:', dict(Counter(e['added'][k]['quotes'] for e in log for k in e['added'])))


if __name__ == '__main__':
    main('--dry-run' in sys.argv)
