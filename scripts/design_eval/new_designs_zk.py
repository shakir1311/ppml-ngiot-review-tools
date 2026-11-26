#!/usr/bin/env python3
"""Finds designs outside the corpus that combine zero-knowledge proofs with a blockchain in privacy-preserving learning, publish their code, and defend against the PhD's threats.

Two routes. From the papers: OpenAlex searches (abstract fields removed) for 2020-onward works whose titles join zero-knowledge
(or zk-SNARK, proof of learning, verifiable) with learning; for each, its code is looked for by exact title and DOI in the
Papers with Code archive, Hugging Face Papers and GitHub. From the code: GitHub searches for zero-knowledge toolchains
(circom, ZoKrates, Groth16, EZKL, zkML) used with federated learning or a blockchain. Each repository is then checked as in
new_designs.py (licence, activity, the paper its README names, a published version) and read by its README for the themes:
zero-knowledge, blockchain, a privacy mechanism, the PhD's threats (poisoning, malicious or Sybil participants, free riding,
backdoors, verification of training or aggregation), an NG-IoT setting. Nothing of any paper is read. Writes
design-evaluation/new-designs/_search/ZK-CANDIDATES.json and .csv; requests and answers under design-evaluation/new-designs/_search/evidence/.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/new_designs_zk.py
"""
import base64, csv, json, pathlib, re, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, Recorder, save_json, now   # noqa: E402
from check_licence import PERMISSIVE, COPYLEFT   # noqa: E402
from new_designs import OUT, PWC, PAPER_LINK, corpus_titles, norm, themes   # noqa: E402

OA_QUERIES = ['zero-knowledge federated learning', 'zero knowledge proof federated learning blockchain', 'zk-SNARK federated learning',
              'zero-knowledge machine learning blockchain', 'verifiable federated learning zero-knowledge', 'proof of learning blockchain',
              'zkML blockchain', 'zero-knowledge proof model training verification', 'zero-knowledge aggregation federated',
              'zero-knowledge proof poisoning federated', 'zero-knowledge proof sybil federated learning', 'zk rollup federated learning']
GH_QUERIES = ['zero-knowledge federated learning', 'zk federated learning blockchain', 'zkfl', 'zk-snark federated learning',
              'circom federated learning', 'zokrates federated learning', 'groth16 federated learning', 'ezkl federated learning',
              'zkml federated', 'zero knowledge proof machine learning blockchain', 'verifiable federated learning blockchain',
              'proof of learning blockchain', 'zero-knowledge poisoning defense', 'zk proof sybil federated']
ZK_TITLE = re.compile(r'zero[- ]knowledge|\bzk|snark|stark|bulletproof|proof[- ]of[- ]learning|proof[- ]of[- ]training|zkml', re.I)
LEARN = re.compile(r'learning|\bML\b|model|training|neural|inference|aggregation', re.I)
LISTS = re.compile(r'(?i)awesome|paper-?list|papers\b|reading|survey|curated|resources')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rec = Recorder({'folder': OUT}, pause=0.4)
    corpus = corpus_titles()
    papers = {}
    for q in OA_QUERIES:
        for page in (1, 2):
            st, j = rec.fetch(f'openalex-zk-{q}-{page}', 'https://api.openalex.org/works',
                              params={'search': q, 'filter': 'from_publication_date:2020-01-01', 'per_page': 100, 'page': page})
            for w in (j or {}).get('results', []) if isinstance(j, dict) else []:
                t = w.get('title') or ''
                if ZK_TITLE.search(t) and LEARN.search(t) and norm(t) not in corpus:
                    locs = [((l.get('source') or {}).get('display_name'), (l.get('source') or {}).get('type')) for l in w.get('locations', [])]
                    pub = [n for n, ty in locs if ty in ('journal', 'conference') and n and 'arxiv' not in n.lower()]
                    papers.setdefault(norm(t), {'paper_title': t, 'year': w.get('publication_year'),
                                                'doi': (w.get('doi') or '').replace('https://doi.org/', ''),
                                                'venue': pub[0] if pub else ((w.get('primary_location') or {}).get('source') or {}).get('display_name'),
                                                'peer_reviewed': bool(pub), 'cited_by': w.get('cited_by_count'),
                                                'arxiv': next((re.search(r'(\d{4}\.\d{4,5})', l.get('landing_page_url') or '').group(1)
                                                               for l in w.get('locations', []) if re.search(r'arxiv\.org/abs/\d{4}\.\d{4,5}', l.get('landing_page_url') or '')), None)})
    print(f'{len(papers)} zero-knowledge learning papers (2020 on, outside the corpus)', flush=True)
    # code for each paper: the Papers with Code archive (title, arXiv id), then GitHub by exact title
    import pyarrow.parquet as pq
    pwc = {}
    for x in pq.read_table(PWC, columns=['paper_title', 'paper_arxiv_id', 'repo_url', 'is_official']).to_pylist():
        pwc.setdefault(norm(x['paper_title']), []).append(x)
        if x['paper_arxiv_id']:
            pwc.setdefault('arxiv:' + x['paper_arxiv_id'], []).append(x)
    repos = {}
    for k, p in papers.items():
        for x in pwc.get(k, []) + (pwc.get('arxiv:' + p['arxiv'], []) if p.get('arxiv') else []):
            repos.setdefault(x['repo_url'].rstrip('/').lower(), {'repo': x['repo_url'].rstrip('/'), 'found_by': [], **p})['found_by'].append(
                'papers_with_code_archive' + (' (official)' if x['is_official'] else ''))
        st, j = rec.fetch('gh-title', 'https://api.github.com/search/repositories', github=True,
                          params={'q': f'"{p["paper_title"][:200]}" in:readme,description', 'per_page': 10})
        for it in (j or {}).get('items', []) if isinstance(j, dict) else []:
            repos.setdefault(it['html_url'].lower(), {'repo': it['html_url'], 'found_by': [], **p})['found_by'].append('github: exact title in README')
        time.sleep(2.1)
    for q in GH_QUERIES:
        st, j = rec.fetch(f'gh-zk-{q}', 'https://api.github.com/search/repositories', github=True,
                          params={'q': q, 'sort': 'stars', 'order': 'desc', 'per_page': 30})
        for it in (j or {}).get('items', []) if isinstance(j, dict) else []:
            repos.setdefault(it['html_url'].lower(), {'repo': it['html_url'], 'found_by': []})['found_by'].append(f'github_search: {q}')
        time.sleep(2.1)
    out = []
    for key, c in sorted(repos.items()):
        m = re.match(r'https://github\.com/([^/]+)/([^/#?]+)', c['repo'], re.I)
        if not m:
            continue
        owner, name = m.groups()
        st, meta = rec.fetch(f'repo-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}', github=True)
        if st != 200 or not isinstance(meta, dict):
            continue
        st, rd = rec.fetch(f'readme-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}/readme', github=True)
        readme = base64.b64decode(rd['content']).decode('utf-8', 'replace') if isinstance(rd, dict) and rd.get('content') else ''
        spdx = (meta.get('license') or {}).get('spdx_id')
        text = ' '.join([c.get('paper_title', ''), meta.get('description') or '', readme[:30000]])
        th = themes(text)
        c.update({'repo': meta['html_url'], 'description': meta.get('description') or '', 'licence': spdx,
                  'open_licence': spdx in PERMISSIVE or spdx in COPYLEFT, 'stars': meta.get('stargazers_count'),
                  'created': (meta.get('created_at') or '')[:10], 'last_push': (meta.get('pushed_at') or '')[:10],
                  'language': meta.get('language'), 'fork': meta.get('fork'), 'themes': th,
                  'reading_list': bool(LISTS.search(name + ' ' + (meta.get('description') or ''))),
                  'readme_names_paper': bool(PAPER_LINK.search(readme)),
                  'readme_dois': sorted(set(re.findall(r'10\.\d{4,9}/[^\s)\]>"\']+', readme)))[:5],
                  'in_corpus': norm(c.get('paper_title', '')) in corpus if c.get('paper_title') else False})
        c['zk_blockchain_threat'] = {'zk', 'blockchain', 'threat_or_check'} <= set(th)
        out.append(c)
    save_json(OUT / 'ZK-CANDIDATES.json', {'about': 'Repositories of zero-knowledge learning designs outside the corpus, with licence, '
                                           'published version and themes (from titles and READMEs only).', 'made': now(),
                                           'openalex_queries': OA_QUERIES, 'github_queries': GH_QUERIES, 'papers_found': list(papers.values()),
                                           'candidates': out})
    cols = ['repo', 'paper_title', 'year', 'venue', 'peer_reviewed', 'doi', 'licence', 'open_licence', 'zk_blockchain_threat', 'themes',
            'stars', 'last_push', 'language', 'fork', 'reading_list', 'in_corpus', 'readme_names_paper', 'found_by', 'description']
    with open(OUT / 'ZK-CANDIDATES.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for c in out:
            w.writerow({k: (';'.join(v) if isinstance(v, list) else v) for k, v in c.items()})
    good = [c for c in out if c['zk_blockchain_threat'] and c['open_licence'] and not c['fork'] and not c['reading_list'] and not c['in_corpus']]
    print(f'{len(out)} repositories checked; ZK + blockchain + a threat or check, open licence, not a fork or list, outside the corpus: {len(good)}')


if __name__ == '__main__':
    main()
