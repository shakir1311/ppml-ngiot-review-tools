#!/usr/bin/env python3
"""The steps of 2 October 2026 that read live sources (OpenAlex, publisher open-access links, the SJR files the author
downloaded) or the author's Downloads folder, kept as code so the method is on record and can be repeated.

Re-running a network step queries the live source again, and the answer may differ from that day's, because records
are added, corrected or retracted. The saved outputs of that day are the record of the review; a re-run writes its
outputs with the tag given by --tag (default: today's date), so nothing saved is overwritten.

    python3 scripts/search/network_steps.py <step> [--tag TAG]

  sjr-quartiles     SJR 2025 (deciding) and 2024 quartiles of the in-depth candidates, matched by ISSN from OpenAlex,
                    title as fallback          -> search/quality/CANDIDATE-QUARTILES-<tag>.json
  map-quartiles     SJR 2025 quartile of every map study and survey -> search/quality/MAP-QUARTILES-<tag>.json
  oa-status         open-access status and best PDF link of the candidates (OpenAlex) -> search/OA-STATUS-<tag>.json
  citation-search   backward (references) and forward (citing) works of the included studies, then the review's
                    filters                    -> search/citation/CITATION-POOL-<tag>.json, CITATION-FILTER-<tag>.json
  file-pdfs LIST    file PDFs from the Downloads folder: deduplicate by SHA-256, extract with extract_paper.py, identify by
                    the DOI (or title) on the first pages, copy one copy per paper into corpus/searchcorpus/papers/<id>/
                    with PROVENANCE.json; LIST is a text file of file names in /Volumes/Stuff/Downloads
"""
import csv, datetime, hashlib, json, pathlib, re, shutil, subprocess, sys, time, urllib.parse, urllib.request

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
D = '2026-10-02'
UA = {'User-Agent': 'slr-search/1.0'}
DOWNLOADS = pathlib.Path('/Volumes/Stuff/Downloads')


def get(url, tries=5):
    for _ in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
        except Exception:
            time.sleep(5)
    raise SystemExit('failed: ' + url)


def sjr_index(year):
    idx, tidx = {}, {}
    for r in csv.DictReader(open(ROOT / 'search' / 'quality' / f'scimagojr-{year}.csv', encoding='utf-8'), delimiter=';'):
        for i in re.findall(r'\w{8}', r['Issn'].replace('-', '')):
            idx[i.upper()] = r
        tidx[re.sub(r'[^a-z0-9]', '', r['Title'].lower())] = r
    return idx, tidx


def issns(dois):
    out = {}
    for i in range(0, len(dois), 40):
        url = ('https://api.openalex.org/works?per-page=50&select=doi,primary_location&filter=doi:'
               + urllib.parse.quote('|'.join(dois[i:i + 40]), safe=':|/'))
        for w in get(url)['results']:
            s = (w.get('primary_location') or {}).get('source') or {}
            out[w['doi'].replace('https://doi.org/', '').lower()] = {'issn': s.get('issn') or [], 'name': s.get('display_name'),
                                                                   'type': s.get('type')}
        time.sleep(1)
    return out


def quartile(issn_list, name, venue, year):
    idx, tidx = SJR[year]
    hit = next((idx[i.replace('-', '').upper()] for i in issn_list if i.replace('-', '').upper() in idx), None)
    hit = hit or tidx.get(re.sub(r'[^a-z0-9]', '', (name or venue or '').lower()))
    return hit


def sjr_quartiles(tag):
    cand = sum((json.load(open(ROOT / 'search' / f'INDEPTH-CANDIDATES-{p}-{D}.json')) for p in ('PART1', 'PART2')), [])
    iss = issns([c['doi'] for c in cand])
    out = []
    for c in cand:
        o = iss.get(c['doi'].lower(), {'issn': [], 'name': None})
        row = {'n': c['n'], 'doi': c['doi'], 'venue': c['venue'], 'corpus_id': c['corpus_id'], 'issn': o['issn']}
        for y in (2024, 2025):
            h = quartile(o['issn'], o['name'], c['venue'], y)
            row[f'sjr{y}_title'], row[f'q{y}'], row[f'cats{y}'] = (h['Title'], h['SJR Best Quartile'], h['Categories']) if h else ('', 'not ranked', '')
        out.append(row)
    json.dump(out, open(ROOT / 'search' / 'quality' / f'CANDIDATE-QUARTILES-{tag}.json', 'w'), indent=1, ensure_ascii=False)


def map_quartiles(tag):
    L = list(csv.DictReader(open(ROOT / 'search' / f'RECORD-LEDGER-{D}-X5.csv', encoding='utf-8')))
    sel = [r for r in L if r['status'] in ('scope A, primary', 'included in depth', 'survey (related work)') or r['status'].startswith('excluded IC7')]
    iss = issns([r['doi'] for r in sel if r['doi']])
    out = {}
    for r in sel:
        o = iss.get(r['doi'].lower(), {'issn': [], 'name': None, 'type': None})
        h = quartile(o['issn'], o['name'], r['venue'], 2025)
        conf = bool(re.search(r'conference|symposium|workshop|proceedings|congress|lecture notes', r['venue'], re.I)) or o.get('type') == 'conference'
        out[r['n']] = {'q2025': h['SJR Best Quartile'] if h else ('conference' if conf else 'not ranked'), 'source_type': o.get('type')}
    json.dump(out, open(ROOT / 'search' / 'quality' / f'MAP-QUARTILES-{tag}.json', 'w'), indent=1)


def oa_status(tag):
    cand = sum((json.load(open(ROOT / 'search' / f'INDEPTH-CANDIDATES-{p}-{D}.json')) for p in ('PART1', 'PART2')), [])
    dois = [c['doi'] for c in cand if c['doi']]
    out = {}
    for i in range(0, len(dois), 40):
        url = ('https://api.openalex.org/works?per-page=50&select=doi,open_access,best_oa_location&filter=doi:'
               + urllib.parse.quote('|'.join(dois[i:i + 40]), safe=':|/'))
        for w in get(url)['results']:
            loc = w.get('best_oa_location') or {}
            out[w['doi'].replace('https://doi.org/', '').lower()] = {'is_oa': w['open_access']['is_oa'], 'pdf': loc.get('pdf_url')}
        time.sleep(1)
    json.dump(out, open(ROOT / 'search' / f'OA-STATUS-{tag}.json', 'w'), indent=1)


def citation_search(tag):
    dec = [r for r in csv.DictReader(open(ROOT / 'search' / f'FULLTEXT-DECISIONS-{D}.csv', encoding='utf-8')) if r['recommended'] == 'INCLUDE']
    st = {r['id']: r for r in csv.DictReader(open(ROOT / 'search' / f'INDEPTH-STATUS-{D}.csv', encoding='utf-8'))}
    seeds, back, fwd = [], set(), set()
    for r in dec:
        w = get('https://api.openalex.org/works/doi:' + urllib.parse.quote(st[r['id']]['doi'], safe='/:'))
        seeds.append({'id': r['id'], 'openalex': w['id'], 'refs': len(w.get('referenced_works', [])), 'cited_by': w.get('cited_by_count', 0)})
        back |= set(w.get('referenced_works', []))
        cur = '*'
        while cur:
            page = get(f"https://api.openalex.org/works?filter=cites:{w['id'].split('/')[-1]}&per-page=200&select=id&cursor={cur}")
            fwd |= {x['id'] for x in page['results']}
            cur = page['meta'].get('next_cursor') if page['results'] else None
    json.dump({'seeds': seeds, 'backward': sorted(back), 'forward': sorted(fwd)},
              open(ROOT / 'search' / 'citation' / f'CITATION-POOL-{tag}.json', 'w'), indent=1)
    ids = sorted(back | fwd)
    works = []
    for i in range(0, len(ids), 50):
        chunk = '|'.join(x.split('/')[-1] for x in ids[i:i + 50])
        works += get(f'https://api.openalex.org/works?filter=openalex:{chunk}&per-page=50&select=id,doi,title,publication_year,type,primary_location,abstract_inverted_index')['results']
    merged = list(csv.DictReader(open(ROOT / 'search' / f'MERGED-RECORDS-{D}-X5.csv', encoding='utf-8')))
    nt = lambda t: re.sub(r'[^a-z0-9]', '', (t or '').lower())
    known_doi, known_t = {m['doi'].lower() for m in merged if m['doi']}, {nt(m['title']) for m in merged}
    ZK = re.compile(r'zero.?knowledge|zk-?snark|\bzkp|bulletproof|range proof|zk-?stark|plonk|groth|halo2', re.I)
    FL = re.compile(r'federated|decentrali[sz]ed learning|collaborative learning|swarm learning|distributed learning', re.I)
    LED = re.compile(r'blockchain|block chain|distributed ledger|smart contract|ethereum|hyperledger', re.I)
    rows = []
    for w in works:
        inv = w.get('abstract_inverted_index') or {}
        ab = ' '.join(t for _, t in sorted((p, k) for k, v in inv.items() for p in v))
        doi = (w.get('doi') or '').replace('https://doi.org/', '').lower()
        s = (w.get('primary_location') or {}).get('source') or {}
        h = quartile(s.get('issn') or [], s.get('display_name'), '', 2025)
        r = {'openalex': w['id'], 'doi': doi, 'title': w.get('title'), 'year': w.get('publication_year'), 'venue': s.get('display_name'),
             'q2025': h['SJR Best Quartile'] if h else 'not ranked'}
        text = (w.get('title') or '') + ' ' + ab
        if doi in known_doi or nt(w.get('title')) in known_t:
            r['stage'] = 'already found by the database search'
        elif not w.get('publication_year') or w['publication_year'] < 2022:
            r['stage'] = 'before 2022'
        elif s.get('type') != 'journal':
            r['stage'] = 'not a journal article'
        elif not (FL.search(text) and LED.search(text) and ZK.search(text)):
            r['stage'] = 'not federated learning + ledger + zero-knowledge proofs in title/abstract'
        elif r['q2025'] != 'Q1':
            r['stage'] = f"journal below Q1 ({r['q2025']})"
        else:
            r['stage'] = 'CANDIDATE: screen on title/abstract'
        r['abstract'] = ab
        rows.append(r)
    json.dump(rows, open(ROOT / 'search' / 'citation' / f'CITATION-FILTER-{tag}.json', 'w'), indent=1, ensure_ascii=False)


def file_pdfs(listfile, tag):
    cand = sum((json.load(open(ROOT / 'search' / f'INDEPTH-CANDIDATES-{p}-{D}.json')) for p in ('PART1', 'PART2')), [])
    want = {f"n{c['n']:04d}": c for c in cand}
    names = [l.rstrip('\n') for l in open(listfile, encoding='utf-8') if l.strip().endswith('.pdf')]
    stage = ROOT / 'corpus' / 'searchcorpus' / '_incoming' / f'stage-{tag}'
    stage.mkdir(parents=True, exist_ok=True)
    seen, log = {}, []
    for nm in names:
        b = (DOWNLOADS / nm).read_bytes()
        h = hashlib.sha256(b).hexdigest()
        if h in seen:
            log.append({'download': nm, 'duplicate_of': seen[h]})
            continue
        seen[h] = nm
        k = stage / h[:10]
        k.mkdir(exist_ok=True)
        shutil.copy2(DOWNLOADS / nm, k / f'{h[:10]}.pdf')
        subprocess.run([str(ROOT / 'scripts/.venv/bin/python'), str(ROOT / 'scripts/extract_paper.py'), str(k / f'{h[:10]}.pdf'), '--quiet'], capture_output=True)
        t = (k / 'text' / 'full.txt').read_text(encoding='utf-8')[:8000].lower()
        nt = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
        hit = [i for i, c in want.items() if c['doi'] and c['doi'].lower() in t] or [i for i, c in want.items() if nt(c['title'])[:60] in nt(t)]
        log.append({'download': nm, 'sha256': h, 'match': hit[0] if len(hit) == 1 else None, 'chars': len(t)})
    json.dump(log, open(stage / 'STAGING.json', 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(log, indent=1)[:2000])
    print('Review STAGING.json, then copy each matched PDF into corpus/searchcorpus/papers/<id>/<id>.pdf with a PROVENANCE.json '
          '(original name, sha256, how obtained, date) and run extract_paper.py and ocr_scanned.py on it.')


SJR = {}
if __name__ == '__main__':
    a = sys.argv[1:]
    tag = a[a.index('--tag') + 1] if '--tag' in a else datetime.date.today().isoformat()
    if not a:
        sys.exit(__doc__)
    if a[0] in ('sjr-quartiles', 'map-quartiles', 'citation-search'):
        SJR = {2024: sjr_index(2024), 2025: sjr_index(2025)}
    {'sjr-quartiles': lambda: sjr_quartiles(tag), 'map-quartiles': lambda: map_quartiles(tag), 'oa-status': lambda: oa_status(tag),
     'citation-search': lambda: citation_search(tag), 'file-pdfs': lambda: file_pdfs(a[1], tag)}.get(a[0], lambda: sys.exit(__doc__))()
