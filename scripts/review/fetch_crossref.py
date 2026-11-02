#!/usr/bin/env python3
"""Fetch the Crossref record of every corpus paper that prints a DOI, for the reference list of the review.

Records are cached in myliteraturereviewpaper/_src/V14/crossref/<ID>.json; a cached record is not fetched again.
Usage: scripts/.venv/bin/python scripts/review/fetch_crossref.py
"""
import csv, json, pathlib, time, urllib.request, urllib.parse, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'crossref'
OUT.mkdir(parents=True, exist_ok=True)
UA = {'User-Agent': 'slr-reference-check/1.0 (literature review reference list)'}

def doi_of(s):
    m = re.search(r'10\.\d{4,9}/\S+', s or '')
    return m.group(0).rstrip('.;,') if m else None

def fetch(doi):
    url = 'https://api.crossref.org/works/' + urllib.parse.quote(doi, safe='/')
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)['message']

papers = list(csv.DictReader(open(ROOT / 'corpus' / '_extraction' / 'papers.csv', encoding='utf-8')))
ok = fail = skip = 0
for p in papers:
    doi = doi_of(p['doi'])
    if not doi:
        skip += 1
        continue
    f = OUT / f"{p['id']}.json"
    if f.exists():
        ok += 1
        continue
    try:
        msg = fetch(doi)
        f.write_text(json.dumps(msg, ensure_ascii=False, indent=1), encoding='utf-8')
        ok += 1
    except Exception as e:
        fail += 1
        print('FAIL', p['id'], doi, e, file=sys.stderr)
    time.sleep(0.3)
print(f'fetched or cached {ok}, failed {fail}, no DOI {skip}')
