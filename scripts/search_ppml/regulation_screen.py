#!/usr/bin/env python3
"""AI pre-screening of groups A and C of the R-S1 records new to the PPML search (8 October 2026), for the author to confirm.

The author: "ok proceed. with A and C". Two independent AI screeners decide every record against the review's criteria
(search-ppml/CRITERIA-V9-2026-10-05.md) from title, abstract and keywords, blind to each other; Claude Code reconciles the
disagreements on the abstracts; the author confirms or overrides every decision.

  packets          screening/input.jsonl (the records of groups A and C, ids RS1-<row of the export>);
                   with SCREEN_SET=B every command works on group B in screening/B/ (asked by the author, 8 October 2026)
  check <file>     a screener's output: one valid line per record
  agree            screening/AGREEMENT.json (agreement and Cohen's kappa on INCLUDE / UNSURE / EXCLUDE)
  final            screening/DECISIONS-A-C.csv from the two outputs and screening/RECONCILE.json (the decisions where they differ)

Usage: python3 scripts/search_ppml/regulation_screen.py packets | check <file> | agree | final
"""
import csv, json, os, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import regulation_reading as RR                                    # noqa: E402
import strings_regulation as SR                                    # noqa: E402

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
EV = ROOT / 'search-ppml' / 'evidence' / 'regulation-search'
OUT = EV / 'screening' / os.environ.get('SCREEN_SET', '')                    # SCREEN_SET=B: group B in screening/B/
GROUPS = os.environ.get('SCREEN_SET') if os.environ.get('SCREEN_SET') in ('B', 'D', 'E') else 'AC'   # D added when R-S1 became a recorded search
# E (claims audit V42): R-S1 records that the review's searches had returned but set aside before screening by an automated
# rule (the IEEE Xplore rule), so that no one had screened them
EXPORT = EV / 'exports' / 'scopus-R-S1-export_f49ca5ca-5cd6-40a2-8abf-94aa93c80d01_2026-10-07T233145.csv'
CODES = {'', 'PRIVACY-INCIDENTAL', 'NO-NGIOT', 'NO-LEARNING', 'OFF-FOCUS', 'NO-BLOCKCHAIN', 'NOT-A-STUDY', 'NOT-FULL-PAPER',
         'SURVEY-BEFORE-2024', 'OTHER'}
ANGLES = {'poisoning', 'malicious or fake participants', 'free riding', 'verification', 'zero-knowledge proofs', 'blockchain', 'ZK on blockchain'}


def records():
    rows = list(csv.DictReader(open(EXPORT, encoding='utf-8-sig')))
    P = list(csv.DictReader(open(ROOT / 'search-ppml' / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8', errors='ignore')))
    pdoi = {r['doi'].lower() for r in P if r.get('doi')}
    ptit = {RR.norm(r['title']) for r in P}
    ix = {r['doi'].lower(): r for r in csv.DictReader(open(ROOT / 'search-ppml' / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))
          if r.get('doi')}
    ta = lambda r: r['Title'] + ' ' + r.get('Abstract', '')
    out = []
    aside = {(x['doi'] or '').lower() for x in P if x.get('auto_excluded') and x.get('doi')} | {RR.norm(x['title']) for x in P if x.get('auto_excluded')}
    for i, r in enumerate(rows, 1):
        if GROUPS == 'E':
            if (r['DOI'].lower() in aside and r['DOI']) or RR.norm(r['Title']) in aside:
                c = ix.get(r['DOI'].lower())
                out.append({'n': f'RS1-{i:03d}', 'group': 'E', 'title': r['Title'], 'year': r['Year'], 'document_type': r['Document Type'],
                            'venue': r['Source title'], 'doi': r['DOI'], 'cited_by_scopus_7oct2026': r.get('Cited by', ''),
                            'abstract': r.get('Abstract', ''), 'keywords': r.get('Author Keywords', ''),
                            'corpus_folder': str(pathlib.Path((c or {}).get('pdf', '')).parent) if c else ''})
            continue
        if r['DOI'].lower() in pdoi or RR.norm(r['Title']) in ptit:
            continue
        g = ('A' if RR.FL.search(ta(r)) and RR.MECH.search(ta(r)) and SR.hit(SR.REG, ta(r)) else
             'B' if RR.MECH.search(ta(r)) else 'C' if r['Document Type'] == 'Review' or SR.hit(SR.SUR, r['Title']) else 'D')
        if g in GROUPS:
            c = ix.get(r['DOI'].lower())
            out.append({'n': f'RS1-{i:03d}', 'group': g, 'title': r['Title'], 'year': r['Year'], 'document_type': r['Document Type'],
                        'venue': r['Source title'], 'doi': r['DOI'], 'cited_by_scopus_7oct2026': r.get('Cited by', ''),
                        'abstract': r.get('Abstract', ''), 'keywords': r.get('Author Keywords', ''),
                        'corpus_folder': str(pathlib.Path((c or {}).get('pdf', '')).parent) if c else ''})
    return out


def read(f):
    return [json.loads(l) for l in pathlib.Path(f).read_text(encoding='utf-8').splitlines() if l.strip()]


def check(f):
    want = {r['n'] for r in read(OUT / 'input.jsonl')}
    probs, seen = [], set()
    for d in read(f):
        n = d.get('n')
        seen.add(n)
        if n not in want:
            probs.append(f'{n}: not a record of the input')
        if d.get('decision') not in ('INCLUDE', 'EXCLUDE', 'UNSURE'):
            probs.append(f'{n}: decision must be INCLUDE, EXCLUDE or UNSURE')
        if d.get('code', '') not in CODES or (d.get('decision') == 'EXCLUDE' and not d.get('code')):
            probs.append(f'{n}: code missing or unknown ({d.get("code")})')
        if d.get('kind') not in ('primary', 'secondary', 'neither'):
            probs.append(f'{n}: kind must be primary, secondary or neither')
        if set(d.get('angles', [])) - ANGLES:
            probs.append(f'{n}: unknown angle {set(d.get("angles", [])) - ANGLES}')
        if not str(d.get('reason', '')).strip() or not str(d.get('quote', '')).strip():
            probs.append(f'{n}: reason and quote required')
    for n in want - seen:
        probs.append(f'{n}: no decision')
    print(f'{len(probs)} problem(s)')
    for p in probs[:30]:
        print('   ', p)
    return len(probs)


def agree():
    a = {d['n']: d for d in read(OUT / 'rater-1.jsonl')}
    b = {d['n']: d for d in read(OUT / 'rater-2.jsonl')}
    ns = sorted(a)
    cats = ['INCLUDE', 'UNSURE', 'EXCLUDE']
    po = sum(a[n]['decision'] == b[n]['decision'] for n in ns) / len(ns)
    pe = sum((sum(a[n]['decision'] == c for n in ns) / len(ns)) * (sum(b[n]['decision'] == c for n in ns) / len(ns)) for c in cats)
    k = (po - pe) / (1 - pe) if pe < 1 else 1.0
    dis = [n for n in ns if a[n]['decision'] != b[n]['decision']]
    res = {'records': len(ns), 'agreement': round(po, 3), 'kappa': round(k, 3), 'disagreements': dis,
           'rater_1': {c: sum(a[n]['decision'] == c for n in ns) for c in cats}, 'rater_2': {c: sum(b[n]['decision'] == c for n in ns) for c in cats}}
    (OUT / 'AGREEMENT.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res, indent=1))


def final():
    inp = {r['n']: r for r in read(OUT / 'input.jsonl')}
    a = {d['n']: d for d in read(OUT / 'rater-1.jsonl')}
    b = {d['n']: d for d in read(OUT / 'rater-2.jsonl')}
    rec = json.loads((OUT / 'RECONCILE.json').read_text(encoding='utf-8')) if (OUT / 'RECONCILE.json').exists() else {}
    rows = []
    for n, r in inp.items():
        if a[n]['decision'] == b[n]['decision']:
            d, how = a[n], 'both screeners'
        else:
            if n not in rec:
                sys.exit(f'{n}: the screeners differ and RECONCILE.json has no decision')
            d, how = rec[n], 'reconciled by Claude Code'
        rows.append({'n': n, 'group': r['group'], 'title': r['title'], 'year': r['year'], 'document_type': r['document_type'], 'venue': r['venue'],
                     'doi': r['doi'], 'cited_by': r['cited_by_scopus_7oct2026'], 'kind': d.get('kind', a[n]['kind']),
                     'ai_decision': d['decision'], 'ai_code': d.get('code', ''), 'angles': '; '.join(d.get('angles', [])),
                     'reason': d['reason'], 'quote': d.get('quote', ''), 'decided_by': how,
                     'rater_1': f"{a[n]['decision']} {a[n].get('code', '')}".strip(), 'rater_2': f"{b[n]['decision']} {b[n].get('code', '')}".strip(),
                     'author_decision': '', 'corpus_folder': r['corpus_folder']})
    with open(OUT / f'DECISIONS-{"-".join(GROUPS)}.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f'DECISIONS-{"-".join(GROUPS)}.csv:', Counter(r['ai_decision'] for r in rows), Counter(r['ai_code'] for r in rows if r['ai_code']))


def fulltext_check(ids):
    """search-ppml/evidence/regulation-search/fulltext/<id>.json: the fields, IC1-IC7, and every quotation on its page"""
    sys.path.insert(0, str(ROOT / 'scripts' / 'paper_ppml'))
    import check_sheets as CS
    FT = EV / 'fulltext'
    probs = []
    for rid in ids or sorted(f.stem for f in FT.glob('RS1-*.json')):
        f = FT / f'{rid}.json'
        if not f.exists():
            probs.append(f'{rid}: no record'); continue
        d = json.loads(f.read_text(encoding='utf-8'))
        if d.get('proposed_decision') not in ('INCLUDE', 'EXCLUDE'):
            probs.append(f'{rid}: proposed_decision must be INCLUDE or EXCLUDE')
        if d.get('proposed_decision') == 'EXCLUDE' and d.get('code') not in CODES - {''}:
            probs.append(f'{rid}: an EXCLUDE needs a known code')
        if not str(d.get('reason', '')).strip():
            probs.append(f'{rid}: reason missing')
        pages = ROOT / 'corpus' / 'ppmlcorpus' / 'check-rs1' / rid / 'text' / 'pages'
        for c in ('IC1', 'IC2', 'IC3', 'IC4', 'IC5', 'IC6', 'IC7'):
            x = (d.get('conditions') or {}).get(c)
            if not isinstance(x, dict) or 'met' not in x or not str(x.get('note', '')).strip():
                probs.append(f'{rid} {c}: met and note required'); continue
            for e in x.get('evidence', []) or []:
                if e.get('source') in ('image', 'table'):
                    continue
                pf = pages / f"page_{int(e.get('page', 0)):04d}.txt"
                if not pf.exists() or not CS.found(e.get('quote', ''), pf.read_text(encoding='utf-8', errors='ignore')):
                    probs.append(f"{rid} {c}: quotation not on p{e.get('page')}: {e.get('quote', '')[:70]!r}")
    print(f'{len(probs)} problem(s)')
    for p_ in probs[:30]:
        print('   ', p_)
    return len(probs)


if __name__ == '__main__':
    cmd = sys.argv[1:2]
    if cmd == ['fulltext-check']:
        sys.exit(1 if fulltext_check(sys.argv[2:]) else 0)
    if cmd == ['packets']:
        OUT.mkdir(parents=True, exist_ok=True)
        recs = records()
        (OUT / 'input.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
        print(f'{OUT.relative_to(EV)}/input.jsonl: {len(recs)} records ' + str({g: sum(r["group"] == g for r in recs) for g in GROUPS}))
    elif cmd == ['check']:
        sys.exit(1 if check(sys.argv[2]) else 0)
    elif cmd == ['agree']:
        agree()
    elif cmd == ['final']:
        final()
    else:
        sys.exit(__doc__)
