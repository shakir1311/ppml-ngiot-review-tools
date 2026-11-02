#!/usr/bin/env python3
"""Run the review's four search strings (Table IV of V15) and record the date and number of hits per source.

Sources: the publishers behind IEEE Xplore, the ACM Digital Library, ScienceDirect, SpringerLink and MDPI, searched
through OpenAlex restricted to each publisher (their own sites refuse or forbid scripted searches); arXiv through its
official query API. Every term is searched in title and abstract, publication dates 2020-01-01 to the run date.
Results are written after every query, so an interrupted run keeps what it has.

Usage: scripts/.venv/bin/python scripts/review/search_counts.py <out.json> [--arxiv-only]
  --arxiv-only keeps the OpenAlex counts already in <out.json> and re-runs arXiv alone.
"""
import datetime, json, re, sys, time, urllib.error, urllib.parse, urllib.request

UA = {'User-Agent': 'slr-search-count/1.0'}
TODAY = datetime.date.today().isoformat()


def Q(*terms):
    return '(' + ' OR '.join(terms) + ')'


GROUPS = {
    'L': Q('"federated learning"', '"decentralised learning"', '"decentralized learning"', '"distributed learning"',
           '"split learning"', '"swarm learning"', '"machine learning"', '"deep learning"', '"edge intelligence"'),
    'P': Q('privacy', '"homomorphic encryption"', '"multi-party computation"', '"secret sharing"', '"secure aggregation"',
           '"trusted execution"', '"zero-knowledge"'),
    'A': Q('poisoning', 'backdoor', 'Byzantine', 'Sybil', '"free-riding"', '"membership inference"', '"inference attack"'),
    'B': Q('blockchain', '"distributed ledger"', '"smart contract"'),
    'T': Q('"Internet of Things"', 'IoT', 'IIoT', '"edge computing"', '"fog computing"', '5G', '6G', 'Bluetooth', 'Zigbee',
           'LoRaWAN', 'WPA3'),
    'S': Q('security', 'attack', 'DDoS', '"denial of service"', 'jamming'),
    'G': Q('GDPR', '"General Data Protection Regulation"', '"right to be forgotten"', 'unlearning'),
}
STRINGS = {
    '1': f"{GROUPS['L']} AND ({GROUPS['P']} OR {GROUPS['A']})",
    '2': f"{GROUPS['B']} AND ({GROUPS['L']} OR {GROUPS['P']})",
    '3': f"{GROUPS['T']} AND {GROUPS['S']}",
    '4': f"{GROUPS['G']} AND ({GROUPS['B']} OR {GROUPS['L']})",
}
STRINGS['any'] = ' OR '.join(f'({v})' for v in STRINGS.values())
PUBLISHERS = {   # OpenAlex publisher IDs (publisher_lineage includes imprints)
    'IEEE (IEEE Xplore)': 'P4310319808',
    'ACM (ACM Digital Library)': 'P4310319798',
    'Elsevier (ScienceDirect)': 'P4310320990',
    'Springer Nature (SpringerLink)': 'P4310319965',
    'MDPI': 'P4310310987',
}


def fetch(url, as_json=True, tries=30, data=None):
    for _ in range(tries):
        try:
            body = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=300).read()
            return json.loads(body) if as_json else body.decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
            wait = int(e.headers.get('Retry-After') or 40) + 5
            print(f'  waiting {wait}s (HTTP {e.code})', flush=True)
            time.sleep(wait)
        except urllib.error.URLError:
            time.sleep(30)
    raise SystemExit(f'gave up on {url[:120]}')


def arxiv_term(term):
    t = term.strip('"')
    t = f'"{t}"' if (' ' in t or '-' in t) else t
    return f'(ti:{t} OR abs:{t})'


def arxiv_group(g):
    terms = [t for t in re.findall(r'"[^"]+"|[^\s()]+', GROUPS[g]) if t != 'OR']
    if g == 'S':                      # attack* in the table: the arXiv API has no wildcard
        terms = [t for t in terms if t != 'attack'] + ['attack', 'attacks']
    return '(' + ' OR '.join(arxiv_term(t) for t in terms) + ')'


ARXIV = {
    '1': f"{arxiv_group('L')} AND ({arxiv_group('P')} OR {arxiv_group('A')})",
    '2': f"{arxiv_group('B')} AND ({arxiv_group('L')} OR {arxiv_group('P')})",
    '3': f"{arxiv_group('T')} AND {arxiv_group('S')}",
    '4': f"{arxiv_group('G')} AND ({arxiv_group('B')} OR {arxiv_group('L')})",
}
ARXIV['any'] = ' OR '.join(f'({v})' for v in ARXIV.values())


def main(out, arxiv_only=False):
    run = {'run_started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
           'period': f'2020-01-01 to {TODAY}', 'fields': 'title and abstract',
           'strings': STRINGS, 'openalex': {}, 'arxiv': {}}
    if arxiv_only:
        with open(out, encoding='utf-8') as f:
            run = json.load(f)
        run['arxiv'] = {}

    def save():
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(run, f, indent=1, ensure_ascii=False)
    for name, pid in ({} if arxiv_only else PUBLISHERS).items():
        run['openalex'][name] = {}
        for k, q in STRINGS.items():
            flt = (f'title_and_abstract.search:{q},from_publication_date:2020-01-01,to_publication_date:{TODAY},'
                   f'primary_location.source.publisher_lineage:{pid}')
            url = 'https://api.openalex.org/works?per-page=1&select=id&filter=' + urllib.parse.quote(flt, safe=':,()')
            n = fetch(url)['meta']['count']
            run['openalex'][name][k] = {'count': n, 'queried_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'url': url}
            save()
            print(f'{name} string {k}: {n}', flush=True)
            time.sleep(5)
    for k, q in ARXIV.items():
        full = f'({q}) AND submittedDate:[202001010000 TO {TODAY.replace("-", "")}2359]'
        # sent as POST: the combined string is too long for a GET URL; max_results=0 now fails with an
        # internal error, and one result returns the same total
        url = 'https://export.arxiv.org/api/query'
        x = fetch(url, as_json=False, data=urllib.parse.urlencode({'search_query': full, 'max_results': 1}).encode())
        if '/api/errors' in x:
            raise SystemExit(f'arXiv returned an error for string {k}')
        m = re.search(r'<opensearch:totalResults[^>]*>(\d+)<', x)
        run['arxiv'][k] = {'count': int(m.group(1)) if m else None, 'query': full,
                           'queried_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
        save()
        print(f'arXiv string {k}: {run["arxiv"][k]["count"]}', flush=True)
        time.sleep(4)
    run['run_finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    save()
    print('done', flush=True)


if __name__ == '__main__':
    main(sys.argv[1], '--arxiv-only' in sys.argv[2:])
