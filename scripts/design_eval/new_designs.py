#!/usr/bin/env python3
"""Finds designs outside the review's corpus that publish their code under an open licence and fit the PhD (privacy-preserving learning for NG-IoT security), and records the evidence for each.

Sources, outside the corpus and the review's search records: the Papers with Code archive (last snapshot, 28 July 2025),
filtered by title for federated or decentralised learning with privacy and a threat or verification theme, or with a
blockchain; GitHub repository searches on the PhD's themes; and a short list of known designs given as seeds. Every
candidate is checked from GitHub (the repository's licence, activity, language, and whether its README names a paper) and
from OpenAlex (a published, peer-reviewed version: venue, year, type, citations; abstract fields removed). Fit to the PhD is
read from the title and the README only, never from a paper: a privacy mechanism (DP, HE, secure aggregation, secret
sharing, MPC, ZKP, TEE); a threat or check (poisoning, Byzantine, malicious or Sybil participants, free riding, backdoors,
verification); a blockchain or ledger; an IoT, edge or vehicular setting; zero-knowledge proofs. Candidates already in the
corpus or among the 75 included studies are dropped. Writes design-evaluation/new-designs/_search/CANDIDATES.json and .csv, with
every request and answer under design-evaluation/new-designs/_search/evidence/.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/new_designs.py
"""
import base64, csv, json, pathlib, re, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, Recorder, save_json, now   # noqa: E402
from check_licence import classify, PERMISSIVE, COPYLEFT   # noqa: E402

OUT = EVAL / 'new-designs' / '_search'
PWC = EVAL / '_sources' / 'pwc-archive' / 'links-between-paper-and-code.parquet'
FL = re.compile(r'federat|decentrali[sz]ed learning|collaborative learning|distributed learning|swarm learning', re.I)
THEMES = {
    'privacy': r'privacy|private|secure aggregation|homomorphic|differential(ly)? priva|\bDP\b|encrypt|secret[- ]shar|multi[- ]?party|\bMPC\b|\bSMPC\b|\bTEE\b|enclave|\bSGX\b|confidential',
    'threat_or_check': r'poison|byzantine|malicious|sybil|free[- ]?rid|backdoor|robust aggregation|robust federated|verifiab|verification|integrity|reputation|untrusted|adversar|attack',
    'blockchain': r'blockchain|distributed ledger|smart contract|ethereum|hyperledger|solidity|consensus',
    'ngiot': r'\bIoT\b|internet of things|\bIIoT\b|edge|fog|vehic|\bIoV\b|5G|6G|smart grid|healthcare|\bIoMT\b|drone|UAV|mobile',
    'zk': r'zero[- ]knowledge|\bzk|snark|stark|bulletproof|groth16|circom|zokrates|ezkl',
}
QUERIES = ['blockchain federated learning privacy', 'blockchain federated learning poisoning', 'blockchain federated learning byzantine',
           'privacy-preserving federated learning poisoning', 'privacy-preserving byzantine-robust federated learning',
           'secure aggregation byzantine federated learning', 'secure aggregation malicious clients federated learning',
           'verifiable federated learning', 'zero-knowledge federated learning', 'zkp federated learning',
           'federated learning sybil defense', 'free-rider federated learning', 'differential privacy federated learning poisoning',
           'homomorphic encryption federated learning poisoning', 'federated learning IoT privacy poisoning',
           'decentralized federated learning blockchain incentive', 'federated learning intrusion detection blockchain privacy']
SEEDS = ['https://github.com/DistributedML/Biscotti', 'https://github.com/pps-lab/rofl-project-code', 'https://github.com/ucbsky/elsa',
         'https://github.com/encryptogroup/SAFEFL']
PAPER_LINK = re.compile(r'doi\.org/10\.\S+|arxiv\.org/(abs|pdf)/\d{4}\.\d{4,5}|\b(IEEE|ACM|USENIX|NDSS|CCS|S&P|INFOCOM|TDSC|TIFS|TPDS|IoT Journal|AAAI|NeurIPS|ICML|ICLR|Elsevier|Springer|MDPI)\b', re.I)


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def corpus_titles():
    """Titles of everything in the corpus folders and the 75 included studies, normalised."""
    out = set()
    for f in (ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv',):
        out |= {norm(r['title']) for r in csv.DictReader(open(f, encoding='utf-8-sig'))}
    for p in (ROOT / 'corpus').rglob('*'):
        if p.is_dir() and re.match(r'^\d{4} - ', p.name):
            out.add(norm(re.sub(r'^\d{4} - |\s*\([^)]*\)\s*$', '', p.name)))
    return {t for t in out if len(t) > 20}


def themes(text):
    return sorted(k for k, rx in THEMES.items() if re.search(rx, text or '', re.I))


def from_pwc():
    import pyarrow.parquet as pq
    rows = pq.read_table(PWC).to_pylist()
    out = {}
    for x in rows:
        ti = x['paper_title'] or ''
        if not FL.search(ti) or not x['is_official']:
            continue
        th = themes(ti)
        if not (('privacy' in th and 'threat_or_check' in th) or ('blockchain' in th and ('privacy' in th or 'threat_or_check' in th))):
            continue
        aid = x['paper_arxiv_id'] or ''
        if re.match(r'\d{4}\.', aid) and int(aid[:2]) < 20:
            continue
        key = x['repo_url'].rstrip('/').lower()
        out.setdefault(key, {'repo': x['repo_url'].rstrip('/'), 'found_by': [], 'paper_title': ti, 'arxiv': aid})['found_by'].append('papers_with_code_archive')
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rec = Recorder({'folder': OUT}, pause=0.5)
    cands = from_pwc()
    for q in QUERIES:
        st, j = rec.fetch(f'gh-search-{q}', 'https://api.github.com/search/repositories', github=True,
                          params={'q': q, 'sort': 'stars', 'order': 'desc', 'per_page': 30})
        for it in (j or {}).get('items', []) if isinstance(j, dict) else []:
            cands.setdefault(it['html_url'].lower(), {'repo': it['html_url'], 'found_by': []})['found_by'].append(f'github_search: {q}')
        time.sleep(2.1)
    for s in SEEDS:
        cands.setdefault(s.lower(), {'repo': s, 'found_by': []})['found_by'].append('seed: known design')
    corpus = corpus_titles()
    kept = []
    for key, c in sorted(cands.items()):
        m = re.match(r'https://github\.com/([^/]+)/([^/#?]+)', c['repo'], re.I)
        if not m:
            continue
        owner, name = m.groups()
        st, meta = rec.fetch(f'repo-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}', github=True)
        if st != 200 or not isinstance(meta, dict):
            c['status'] = f'repository answers {st}'
            kept.append(c)
            continue
        spdx = (meta.get('license') or {}).get('spdx_id')
        st, rd = rec.fetch(f'readme-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}/readme', github=True)
        readme = base64.b64decode(rd['content']).decode('utf-8', 'replace') if isinstance(rd, dict) and rd.get('content') else ''
        klass, meaning = classify(spdx, [])
        c.update({'repo': meta['html_url'], 'description': meta.get('description') or '', 'licence': spdx, 'licence_class': klass,
                  'open_licence': spdx in PERMISSIVE or spdx in COPYLEFT, 'stars': meta.get('stargazers_count'),
                  'created': (meta.get('created_at') or '')[:10], 'last_push': (meta.get('pushed_at') or '')[:10],
                  'language': meta.get('language'), 'fork': meta.get('fork'), 'archived': meta.get('archived'),
                  'size_kb': meta.get('size'),
                  'readme_names_paper': bool(PAPER_LINK.search(readme)),
                  'readme_dois': sorted(set(re.findall(r'10\.\d{4,9}/[^\s)\]>"\']+', readme)))[:5],
                  'readme_arxiv': sorted(set(re.findall(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})', readme)))[:5]})
        text = ' '.join([c.get('paper_title', ''), c['description'], readme[:20000]])
        c['themes'] = themes(text)
        c['in_corpus'] = norm(c.get('paper_title', '')) in corpus if c.get('paper_title') else False
        kept.append(c)
    # a published version: OpenAlex by DOI from the README, else by the paper's title
    for c in kept:
        if not c.get('open_licence') or c.get('fork'):
            continue
        q = None
        if c.get('readme_dois'):
            q = ('doi', c['readme_dois'][0].rstrip('.,;'))
        elif c.get('paper_title'):
            q = ('title', c['paper_title'])
        if not q:
            continue
        if q[0] == 'doi':
            st, w = rec.fetch('openalex-doi', f'https://api.openalex.org/works/doi:{q[1]}')
        else:
            st, w = rec.fetch('openalex-title', 'https://api.openalex.org/works', params={'search': q[1], 'per_page': 3})
            res = (w or {}).get('results', []) if isinstance(w, dict) else []
            w = next((r for r in res if norm(r.get('title')) == norm(q[1])), None)
            if w is None:
                # the archive's title may be the preprint's: take the best match only if the words agree closely
                w = res[0] if res and len(set(norm(res[0].get('title', ''))) ^ set(norm(q[1]))) < 3 else None
        if isinstance(w, dict) and w.get('id'):
            loc = w.get('primary_location') or {}
            src = loc.get('source') or {}
            locs = [((l.get('source') or {}).get('display_name'), (l.get('source') or {}).get('type')) for l in w.get('locations', [])]
            pub = [(n, t) for n, t in locs if t in ('journal', 'conference') and n and 'arxiv' not in n.lower()]
            c.update({'paper_title': c.get('paper_title') or w.get('title'), 'year': w.get('publication_year'),
                      'doi': (w.get('doi') or '').replace('https://doi.org/', ''), 'venue': pub[0][0] if pub else src.get('display_name'),
                      'peer_reviewed': bool(pub), 'cited_by': w.get('cited_by_count')})
            c['in_corpus'] = c['in_corpus'] or norm(c['paper_title']) in corpus
    # the PhD fit: privacy and a threat or check are required; blockchain, NG-IoT and ZK add to it
    for c in kept:
        th = set(c.get('themes', []))
        c['fits_phd'] = 'privacy' in th and 'threat_or_check' in th
        c['fit_score'] = 2 * c['fits_phd'] + len(th & {'blockchain', 'ngiot', 'zk'})
    save_json(OUT / 'CANDIDATES.json', {'about': 'Designs outside the corpus with code, their licence, published version and fit to the PhD.',
                                        'made': now(), 'queries': QUERIES, 'seeds': SEEDS, 'candidates': kept})
    cols = ['repo', 'paper_title', 'year', 'venue', 'peer_reviewed', 'doi', 'licence', 'open_licence', 'fits_phd', 'fit_score', 'themes',
            'stars', 'last_push', 'language', 'fork', 'in_corpus', 'readme_names_paper', 'found_by']
    with open(OUT / 'CANDIDATES.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for c in kept:
            w.writerow({k: (';'.join(v) if isinstance(v, list) else v) for k, v in c.items()})
    good = [c for c in kept if c.get('open_licence') and c.get('fits_phd') and not c.get('fork') and not c.get('in_corpus')]
    print(f"{len(kept)} repositories checked; open licence {sum(1 for c in kept if c.get('open_licence'))}; fit the PhD {sum(1 for c in kept if c.get('fits_phd'))}; "
          f"both, not a fork, not in the corpus: {len(good)}; of those with a peer-reviewed version: {sum(1 for c in good if c.get('peer_reviewed'))}")


if __name__ == '__main__':
    main()
