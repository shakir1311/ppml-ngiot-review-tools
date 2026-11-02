#!/usr/bin/env python3
"""Overlap between the two tiers of the PPML review: which of the included primary studies each included survey cites.

A survey that cites a design summarises it, so the surveys' conclusions are not independent of the designs reviewed beside
them. The check uses public citation metadata only (OpenAlex reference lists, looked up by DOI); no paper is opened. A
survey whose reference list OpenAlex does not hold is reported as such, and a design published after a survey cannot be
cited by it.

Output: search-ppml/evidence/overlap/OPENALEX-OVERLAP-<date>.json (every lookup, reference list and match) and the numbers
read by data.py. An existing output is never overwritten.

Usage: python3 scripts/paper_ppml/overlap.py <date>
"""
import csv
import datetime
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
FINAL = ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv'
OUT = ROOT / 'search-ppml' / 'evidence' / 'overlap'
API = 'https://api.openalex.org/works/doi:'


def lookup(doi):
    url = API + urllib.parse.quote(doi.strip().lower(), safe='/')
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'ppml-review-overlap-check'}), timeout=30) as r:
                w = json.loads(r.read().decode('utf-8'))
            return {'openalex': w.get('id'), 'year': w.get('publication_year'), 'referenced_works': w.get('referenced_works') or [],
                    'referenced_works_count': w.get('referenced_works_count')}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {'openalex': None, 'error': 'not found'}
            time.sleep(2 + attempt * 3)
        except Exception as e:                                   # network hiccups: retry, then record the failure
            time.sleep(2 + attempt * 3)
            last = str(e)
    return {'openalex': None, 'error': 'lookup failed'}


def main(date):
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f'OPENALEX-OVERLAP-{date}.json'
    if out.exists():
        sys.exit(f'{out.name} exists; never overwritten')
    fin = list(csv.DictReader(open(FINAL, encoding='utf-8')))
    prim = {r['corpus_id']: r for r in fin if r['kind'] == 'primary'}
    surv = {r['corpus_id']: r for r in fin if r['kind'] != 'primary'}
    look = {}
    for k, r in sorted({**prim, **surv}.items()):
        look[k] = lookup(r['doi']) if r.get('doi') else {'openalex': None, 'error': 'no DOI'}
        time.sleep(0.15)
    pid = {k: look[k]['openalex'] for k in prim if look[k].get('openalex')}
    rows = {}
    for s_, r in sorted(surv.items()):
        refs = set(look[s_].get('referenced_works') or [])
        cited = sorted(k for k, oid in pid.items() if oid in refs)
        older = sorted(k for k in prim if int(prim[k]['year']) <= int(r['year']))      # designs that a survey of that year could cite
        rows[s_] = {'year': int(r['year']), 'references_held': bool(refs), 'references_count': len(refs), 'cites': cited,
                    'citable_designs': len(older)}
    held = [s_ for s_, v in rows.items() if v['references_held']]
    cited_any = sorted({k for v in rows.values() for k in v['cites']})
    res = {'date': date, 'made_at': datetime.datetime.now().isoformat(timespec='seconds'), 'source': 'OpenAlex reference lists by DOI',
           'primary': len(prim), 'surveys': len(surv), 'primary_found': len(pid), 'surveys_with_references': len(held),
           'designs_cited_by_any_survey': cited_any, 'surveys_citing_any_design': sorted(s_ for s_, v in rows.items() if v['cites']),
           'citations_pairs': sum(len(v['cites']) for v in rows.values()), 'by_survey': rows, 'lookups': look}
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f"{out.relative_to(ROOT)}: {len(pid)}/{len(prim)} designs and {len(held)}/{len(surv)} surveys with reference lists found; "
          f"{len(cited_any)} designs cited by at least one survey; {res['citations_pairs']} survey-design citations")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
