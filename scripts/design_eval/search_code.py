#!/usr/bin/env python3
"""Searches every public place where a design's code could be, or could once have been, and records each request and its answer.

For one design (or all, one after the other) it asks, in order: Crossref and OpenAlex (authors, ORCIDs, relations, preprints),
arXiv and Hugging Face Papers (a preprint's code link), the Papers with Code archive (last snapshot, 28 July 2025, kept in
design-evaluation/_sources/), DataCite, Zenodo and OpenAIRE Scholexplorer (software or data deposits linked to the DOI),
GitHub (repositories by the design's name and title, code that cites the DOI or title, the authors' own accounts and
repositories), ORCID (the authors' listed websites and software works), GitLab and Gitee (by name), Software Heritage and the
Wayback Machine (code that once existed). Every response is saved under the design's evidence/raw/ without abstract or summary
fields; evidence/log.jsonl lists every request with its checksum. The candidates, each with the sources that found it and
the signs that tie it to the paper (README cites the DOI, the title or the authors; owner is an author), go to
evidence/10-candidates.json for the reviewer's judgement. No paper text is read: the names searched for are the title's own
short name and the coined names counted by scan_paper.py.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/search_code.py [<id> ...]   (all 45 in order when no id is given)
"""
import base64, json, pathlib, re, sys, time, urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, Recorder, load_designs, save_json, now   # noqa: E402

PWC = EVAL / '_sources' / 'pwc-archive' / 'links-between-paper-and-code.parquet'
STOPWORDS = set('a an and the of for in on with via to by from using based towards toward its their over under into at as '
                'is are be or scheme framework approach system systems model novel new efficient secure privacy preserving '
                'privacy-preserving enabled enhanced driven aware'.split())
DOMAIN = ('federat', 'blockchain', 'privacy', 'zero-knowledge', 'zkp', 'zk', 'secure', 'aggregat', 'ledger', 'homomorph',
          'differential', 'poison', 'byzantine', 'iot', 'vehic', 'edge', 'smart contract', 'fl-', '-fl', 'bcfl', 'bfl')
OWN_ACCOUNTS = {'shakir1311'}
REPO_RE = re.compile(r'https?://(?:www\.)?(github\.com|gitlab\.com|gitee\.com|bitbucket\.org)/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)', re.I)


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def repo_key(url):
    m = REPO_RE.match(url.strip())
    if not m:
        return None
    host, owner, name = m.group(1).lower(), m.group(2), re.sub(r'\.git$', '', m.group(3))
    return f'https://{host}/{owner}/{name}'


def title_words(title):
    return [w for w in re.findall(r'[A-Za-z][A-Za-z0-9\-]+', title.lower()) if w not in STOPWORDS and len(w) > 2]


def arxiv_feed(text):
    """An arXiv Atom feed reduced to id, title, comments, journal ref, DOI and links (no abstracts)."""
    ns = {'a': 'http://www.w3.org/2005/Atom', 'x': 'http://arxiv.org/schemas/atom'}
    out = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {'unparsed': True}
    for e in root.findall('a:entry', ns):
        out.append({'id': (e.findtext('a:id', '', ns) or '').strip(),
                    'title': ' '.join((e.findtext('a:title', '', ns) or '').split()),
                    'comment': (e.findtext('x:comment', '', ns) or '').strip(),
                    'journal_ref': (e.findtext('x:journal_ref', '', ns) or '').strip(),
                    'doi': (e.findtext('x:doi', '', ns) or '').strip(),
                    'links': [l.get('href') for l in e.findall('a:link', ns)]})
    return out


class Search:
    def __init__(self, d):
        self.d = d
        self.rec = Recorder(d, pause=0.6)
        self.cands = {}
        self.authors = []          # [{'name', 'given', 'family', 'orcid'}]
        self.names = []            # names to search: acronym + coined names
        self.notes = []            # what each source said, in one line each
        self.links_text = []       # URLs met in metadata (comments, relations)

    # ---- candidates -------------------------------------------------------------------------------------------
    def add(self, url, source, **signs):
        k = repo_key(url)
        if not k or k.lower().split('/')[3] in OWN_ACCOUNTS:      # the reviewer's own repositories cite the papers
            return
        c = self.cands.setdefault(k, {'repo': k, 'found_by': [], 'signs': {}})
        if source not in c['found_by']:
            c['found_by'].append(source)
        c['signs'].update({s: v for s, v in signs.items() if v})

    # ---- sources ----------------------------------------------------------------------------------------------
    def crossref(self):
        st, j = self.rec.fetch('crossref-work', f"https://api.crossref.org/works/{self.d['doi']}")
        msg = (j or {}).get('message', {}) if isinstance(j, dict) else {}
        for a in msg.get('author', []):
            self.authors.append({'name': ' '.join(x for x in (a.get('given'), a.get('family')) if x),
                                 'given': a.get('given', ''), 'family': a.get('family', ''),
                                 'orcid': (a.get('ORCID') or '').rsplit('/', 1)[-1]})
        rel = msg.get('relation', {})
        for kind, items in rel.items():
            for it in items:
                self.links_text.append(f"crossref relation {kind}: {it.get('id')}")
        self.notes.append(f"Crossref: {st}; {len(self.authors)} authors; relations: {sorted(rel) or 'none'}")
        return msg

    def openalex(self):
        st, j = self.rec.fetch('openalex-work', f"https://api.openalex.org/works/doi:{self.d['doi']}")
        arx = []
        if isinstance(j, dict):
            for a in j.get('authorships', []):
                nm = a.get('author', {}).get('display_name', '')
                oc = (a.get('author', {}).get('orcid') or '').rsplit('/', 1)[-1]
                hit = next((x for x in self.authors if norm(x['family']) and norm(x['family']) in norm(nm)), None)
                if hit and oc and not hit['orcid']:
                    hit['orcid'] = oc
                elif not hit and not self.authors_from_crossref:
                    self.authors.append({'name': nm, 'given': ' '.join(nm.split()[:-1]), 'family': nm.split()[-1] if nm else '', 'orcid': oc})
            for loc in j.get('locations', []):
                u = (loc.get('landing_page_url') or '') + ' ' + (loc.get('pdf_url') or '')
                m = re.search(r'arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})', u)
                if m:
                    arx.append(m.group(1))
        self.notes.append(f"OpenAlex: {st}; arXiv versions: {sorted(set(arx)) or 'none'}")
        return sorted(set(arx))

    def arxiv(self, known):
        q = 'ti:"' + re.sub(r'[^A-Za-z0-9 \-]', ' ', self.d['title']).strip() + '"'
        st, feed = self.rec.fetch('arxiv-title', 'https://export.arxiv.org/api/query',
                                  params={'search_query': q, 'max_results': 5}, transform=arxiv_feed)
        ids = set(known)
        for e in feed if isinstance(feed, list) else []:
            if norm(e['title']) == norm(self.d['title']) or (e.get('doi') or '').lower() == self.d['doi'].lower():
                ids.add(e['id'].rsplit('/', 1)[-1].split('v')[0])
                for u in re.findall(r'https?://\S+', e.get('comment', '')):
                    self.links_text.append(f'arXiv comment: {u}')
                    self.add(u, 'arxiv_comment', linked_by_authors=True)
        self.notes.append(f"arXiv: {st}; same-title preprints: {sorted(ids) or 'none'}")
        time.sleep(3)
        return sorted(ids)

    def huggingface(self, arxiv_ids):
        found = []
        for a in arxiv_ids:
            st, j = self.rec.fetch(f'hf-paper-{a}', f'https://huggingface.co/api/papers/{a}')
            if isinstance(j, dict) and j.get('githubRepo'):
                found.append(j['githubRepo'])
                self.add(j['githubRepo'], 'huggingface_papers', linked_to_preprint=True)
        st, j = self.rec.fetch('hf-papers-search', 'https://huggingface.co/api/papers/search', params={'q': self.d['title']})
        for item in j if isinstance(j, list) else []:
            p = item.get('paper', item)
            if norm(p.get('title')) == norm(self.d['title']) and p.get('githubRepo'):
                found.append(p['githubRepo'])
                self.add(p['githubRepo'], 'huggingface_papers', linked_to_preprint=True)
        self.notes.append(f"Hugging Face Papers: code links {found or 'none'}")

    def pwc(self, arxiv_ids):
        import pyarrow.parquet as pq
        t = pq.read_table(PWC, columns=['paper_title', 'paper_arxiv_id', 'repo_url', 'is_official', 'mentioned_in_paper'])
        nt = norm(self.d['title'])
        rows = [r for r in t.to_pylist() if norm(r['paper_title']) == nt or (r['paper_arxiv_id'] and r['paper_arxiv_id'] in arxiv_ids)]
        save_json(self.d['folder'] / 'evidence' / 'raw' / 'pwc-archive-matches.json',
                  {'source': str(PWC.relative_to(EVAL.parent)), 'matched_on': 'normalised title or arXiv id', 'rows': rows})
        for r in rows:
            self.add(r['repo_url'], 'papers_with_code_archive', pwc_official=r['is_official'], mentioned_in_paper=r['mentioned_in_paper'])
        self.notes.append(f"Papers with Code archive: {len(rows)} rows")

    def deposits(self):
        doi = self.d['doi']
        st, j = self.rec.fetch('datacite-related', 'https://api.datacite.org/dois',
                               params={'query': f'relatedIdentifiers.relatedIdentifier:"{doi}"', 'page[size]': 50})
        n_dc = 0
        for it in (j or {}).get('data', []) if isinstance(j, dict) else []:
            at = it.get('attributes', {})
            n_dc += 1
            kind = (at.get('types') or {}).get('resourceTypeGeneral')
            self.links_text.append(f"DataCite {kind}: {at.get('doi')} {at.get('url')}")
            for ri in at.get('relatedIdentifiers', []):
                self.add(ri.get('relatedIdentifier', ''), 'datacite', deposit_cites_doi=True)
        st2, z = self.rec.fetch('zenodo-doi', 'https://zenodo.org/api/records', params={'q': f'"{doi}"', 'size': 25})
        n_z = 0
        for h in ((z or {}).get('hits', {}) or {}).get('hits', []) if isinstance(z, dict) else []:
            n_z += 1
            md = h.get('metadata', {})
            self.links_text.append(f"Zenodo {md.get('resource_type', {}).get('type')}: {h.get('doi')} {h.get('links', {}).get('self_html')}")
            for ri in md.get('related_identifiers', []):
                self.add(ri.get('identifier', ''), 'zenodo', deposit_cites_doi=True)
        st3, s = self.rec.fetch('scholexplorer-links', 'https://api.scholexplorer.openaire.eu/v3/Links', params={'sourcePid': doi})
        soft = 0
        for x in (s or {}).get('result', []) if isinstance(s, dict) else []:
            t = x.get('target', {})
            ty = (t.get('Type') or t.get('type') or '').lower()
            if ty in ('software', 'dataset', 'other'):
                soft += 1
                for i in t.get('Identifier', t.get('identifier', [])):
                    idv = i.get('ID') or i.get('id') or ''
                    self.links_text.append(f'Scholexplorer {ty}: {idv}')
                    self.add(idv, 'scholexplorer', linked_research_object=True)
        self.notes.append(f"DataCite: {n_dc} deposits citing the DOI; Zenodo: {n_z} records naming it; "
                          f"Scholexplorer: {soft} software/data links")

    def github_repos(self):
        qs = []
        for nm in self.names:
            qs.append((f'gh-repos-name-{nm}', f'{nm} in:name,description,readme'))
        qs.append(('gh-repos-title', f'"{self.d["title"]}" in:readme,description'))
        qs.append(('gh-repos-doi', f'"{self.d["doi"]}" in:readme'))
        tw = title_words(self.d['title'])[:6]
        if len(tw) >= 4:
            qs.append(('gh-repos-titlewords', ' '.join(tw) + ' in:readme,description'))
        total = 0
        for label, q in qs:
            st, j = self.rec.fetch(label, 'https://api.github.com/search/repositories', github=True,
                                   params={'q': q, 'per_page': 15})
            items = (j or {}).get('items', []) if isinstance(j, dict) else []
            total += len(items)
            for it in items:
                self.add(it['html_url'], label.replace('gh-repos-', 'github_search_'))
            time.sleep(1.6)
        self.notes.append(f'GitHub repository search: {len(qs)} queries, {total} results')

    def github_code(self):
        total = 0
        for label, q in (('gh-code-doi', f'"{self.d["doi"]}"'), ('gh-code-title', f'"{self.d["title"]}"')):
            st, j = self.rec.fetch(label, 'https://api.github.com/search/code', github=True, params={'q': q, 'per_page': 30})
            items = (j or {}).get('items', []) if isinstance(j, dict) else []
            total += len(items)
            for it in items:
                path = it.get('path') or ''
                own = '/' not in path and re.match(r'(?i)^(readme|citation)(\.(md|rst|txt|cff|bib))?$', path)
                # a repository's own README or CITATION file citing the paper ties it; any other file is a mention
                self.add(it['repository']['html_url'], label.replace('gh-code-', 'github_code_cites_'),
                         **{('readme_or_citation_file_cites_' if own else 'other_file_mentions_') + label.split('-')[-1]: path})
            time.sleep(7)
        self.notes.append(f'GitHub code search (files citing the DOI or the exact title): {total} files')

    def github_authors(self):
        keys = [norm(n.split()[0]) for n in self.names] + [w for w in title_words(self.d['title']) if len(w) > 4][:8]
        users_seen, hits = 0, 0
        for a in self.authors[:10]:
            if len(a['name']) < 5:
                continue
            st, j = self.rec.fetch(f"gh-users-{a['family']}", 'https://api.github.com/search/users', github=True,
                                   params={'q': f'fullname:"{a["name"]}"', 'per_page': 5})
            time.sleep(1.6)
            for u in ((j or {}).get('items', []) if isinstance(j, dict) else [])[:5]:
                users_seen += 1
                st2, repos = self.rec.fetch(f"gh-user-repos-{u['login']}", f"https://api.github.com/users/{u['login']}/repos",
                                            github=True, params={'per_page': 100, 'sort': 'updated'})
                for r in repos if isinstance(repos, list) else []:
                    blob = norm(r.get('name', '')) + ' ' + (r.get('description') or '').lower()
                    named = any(k and k in blob for k in keys if len(k) > 3)
                    domain = sum(1 for k in DOMAIN if k in blob)
                    if named and domain >= 1 or (named and len([k for k in keys if k and k in blob]) >= 2):
                        hits += 1
                        self.add(r['html_url'], 'github_author_account', owner_name_matches_author=a['name'])
        self.notes.append(f'GitHub accounts named like the authors: {users_seen} accounts checked, {hits} matching repositories')

    def orcid(self):
        n, urls = 0, []
        for a in self.authors:
            if not a['orcid']:
                continue
            n += 1
            st, j = self.rec.fetch(f"orcid-urls-{a['orcid']}", f"https://pub.orcid.org/v3.0/{a['orcid']}/researcher-urls",
                                   accept='application/json')
            for ru in (j or {}).get('researcher-url', []) if isinstance(j, dict) else []:
                u = (ru.get('url') or {}).get('value', '')
                urls.append(u)
                if repo_key(u):
                    self.add(u, 'orcid_researcher_url', listed_by_author=a['name'])
                m = re.match(r'https?://(?:www\.)?github\.com/([A-Za-z0-9_\-]+)/?$', u)
                if m:
                    self.github_owner(m.group(1), a['name'])
            st, w = self.rec.fetch(f"orcid-works-{a['orcid']}", f"https://pub.orcid.org/v3.0/{a['orcid']}/works",
                                   accept='application/json')
            for g in (w or {}).get('group', []) if isinstance(w, dict) else []:
                for s in g.get('work-summary', []):
                    url = ((s.get('url') or {}) or {}).get('value', '') if s.get('url') else ''
                    if s.get('type') in ('software', 'data-set') or repo_key(url or ''):
                        self.links_text.append(f"ORCID {a['name']} {s.get('type')}: {url}")
                        self.add(url or '', 'orcid_work', listed_by_author=a['name'])
        self.notes.append(f'ORCID: {n} authors with an ORCID; websites listed: {len(urls)}')

    def github_owner(self, login, author):
        st, repos = self.rec.fetch(f'gh-user-repos-{login}', f'https://api.github.com/users/{login}/repos', github=True,
                                   params={'per_page': 100, 'sort': 'updated'})
        keys = [norm(n.split()[0]) for n in self.names] + [w for w in title_words(self.d['title']) if len(w) > 4][:8]
        for r in repos if isinstance(repos, list) else []:
            blob = norm(r.get('name', '')) + ' ' + (r.get('description') or '').lower()
            if any(k and len(k) > 3 and k in blob for k in keys):
                self.add(r['html_url'], 'github_account_listed_in_orcid', owner_is_author=author)

    def other_hosts(self):
        n = 0
        for nm in self.names:
            st, j = self.rec.fetch(f'gitlab-{nm}', 'https://gitlab.com/api/v4/projects', params={'search': nm, 'per_page': 20})
            for p in j if isinstance(j, list) else []:
                n += 1
                self.add(p.get('web_url', ''), 'gitlab_search')
            st, j = self.rec.fetch(f'gitee-{nm}', 'https://gitee.com/api/v5/search/repositories', params={'q': nm, 'per_page': 20})
            for p in j if isinstance(j, list) else []:
                n += 1
                self.add(p.get('html_url', ''), 'gitee_search')
        self.notes.append(f'GitLab and Gitee by name: {n} projects')

    def archives(self):
        n = 0
        for nm in self.names[:3]:
            st, j = self.rec.fetch(f'swh-search-{nm}', f'https://archive.softwareheritage.org/api/1/origin/search/{urllib.parse.quote(nm.split()[0])}/',
                                   params={'limit': 50}, timeout=40, retries=1)
            for o in j if isinstance(j, list) else []:
                n += 1
                self.add(o.get('url', ''), 'software_heritage_search')
            time.sleep(2)
        self.notes.append(f'Software Heritage origins by name: {n}')

    # ---- candidates: tie each to the paper -----------------------------------------------------------------------
    def tie(self):
        surn = [norm(a['family']) for a in self.authors if len(norm(a['family'])) > 2]
        nt, nd = norm(self.d['title']), self.d['doi'].lower()
        strong_sources = {'paper_link', 'huggingface_papers', 'papers_with_code_archive', 'datacite', 'zenodo', 'scholexplorer',
                          'orcid_researcher_url', 'orcid_work',
                          'github_account_listed_in_orcid', 'arxiv_comment', 'github_search_doi', 'github_search_title'}
        for c in self.cands.values():
            weak = not (set(c['found_by']) & strong_sources) and 'github_author_account' not in c['found_by']
            c['weak_only'] = weak
        # README of every candidate that is not a pure name hit, and of name hits only when few
        weak_list = [c for c in self.cands.values() if c['weak_only']]
        check = [c for c in self.cands.values() if not c['weak_only']] + weak_list[:10]
        for c in check:
            m = REPO_RE.match(c['repo'])
            host, owner, name = m.group(1).lower(), m.group(2), m.group(3)
            if host != 'github.com':
                continue
            st, meta = self.rec.fetch(f'gh-repo-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}', github=True)
            if st != 200:
                c['status'] = f'repository answers {st}'
                continue
            c['created'], c['pushed'] = meta.get('created_at'), meta.get('pushed_at')
            c['licence_detected'] = (meta.get('license') or {}).get('spdx_id')
            c['fork'], c['archived'] = meta.get('fork'), meta.get('archived')
            st, rd = self.rec.fetch(f'gh-readme-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}/readme', github=True)
            text = ''
            if isinstance(rd, dict) and rd.get('content'):
                text = base64.b64decode(rd['content']).decode('utf-8', 'replace')
            nr = norm(text)
            c['signs'].update({k: v for k, v in {
                'readme_cites_doi': nd in text.lower(),
                'readme_cites_title': bool(nt) and nt in nr,
                'readme_names_authors': sum(1 for s in surn if s in nr) if surn else 0,
                'owner_is_author_surname': any(s and s in norm(owner) for s in surn),
                'readme_names_design': [n for n in self.names if norm(n.split()[0]) in nr],
                'readme_title_word_share': round(sum(1 for w in set(title_words(self.d['title'])) if w in text.lower())
                                                 / max(1, len(set(title_words(self.d['title'])))), 2),
            }.items() if v})
        tie_signs = ('linked_in_paper_pages', 'pwc_official', 'readme_cites_doi', 'listed_by_author', 'owner_is_author',
                     'deposit_cites_doi', 'linked_by_authors', 'linked_to_preprint', 'readme_or_citation_file_cites_doi',
                     'readme_or_citation_file_cites_title')
        for c in self.cands.values():
            sg = c['signs']
            c['tied_to_paper'] = bool(any(sg.get(k) for k in tie_signs) or (sg.get('owner_is_author_surname') and sg.get('readme_names_design'))
                                      or (sg.get('readme_cites_title') and (sg.get('owner_is_author_surname') or sg.get('readme_names_design')
                                                                             or sg.get('readme_names_authors', 0) >= 2))
                                      or (sg.get('readme_names_authors', 0) >= 3
                                          and (sg.get('readme_names_design') or sg.get('readme_title_word_share', 0) >= 0.7)))
        # was it ever archived? (a repository may be gone from GitHub but kept by Software Heritage or the Wayback Machine)
        for c in self.cands.values():
            if not c['tied_to_paper'] and 'paper_link' not in c['found_by']:
                continue
            st, j = self.rec.fetch('swh-origin', f"https://archive.softwareheritage.org/api/1/origin/{c['repo']}/get/", timeout=40, retries=1)
            c['software_heritage'] = 'archived' if st == 200 else f'not archived ({st})'
            st, w = self.rec.fetch('wayback', 'https://archive.org/wayback/available', params={'url': c['repo'].split('://', 1)[1]})
            snap = ((w or {}).get('archived_snapshots') or {}).get('closest') if isinstance(w, dict) else None
            c['wayback'] = snap.get('timestamp') if snap else 'no snapshot'

    def run(self):
        msg = self.crossref()
        self.authors_from_crossref = bool(self.authors)
        arx = self.openalex()
        scan = json.load(open(self.d['folder'] / 'evidence' / '02-paper-links.json'))
        for l in scan['links']:
            if l['kind'] == 'code_host' and not l['in_references']:
                self.add(l['url'], 'paper_link', linked_in_paper_pages=l['pages'])
            m = re.match(r'https?://orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])', l['url'])
            if m and not any(a['orcid'] == m.group(1) for a in self.authors):
                self.authors.append({'name': '', 'given': '', 'family': '', 'orcid': m.group(1)})
        self.names = json.load(open(EVAL / 'names.json'))['names'][self.d['id']]
        arx = self.arxiv(arx)
        self.huggingface(arx)
        self.pwc(arx)
        self.deposits()
        self.github_repos()
        self.github_code()
        self.github_authors()
        self.orcid()
        self.other_hosts()
        self.archives()
        self.tie()
        out = {'about': 'Candidate repositories for the design\'s code, each with the sources that found it and the signs '
                        'that tie it to the paper. The reviewer decides in 11-code-verdict.json.',
               'made': now(), 'names_searched': self.names, 'authors': self.authors, 'arxiv_versions': arx,
               'sources': self.notes, 'links_in_metadata': self.links_text,
               'candidates': sorted(self.cands.values(), key=lambda c: (not c.get('tied_to_paper'), c.get('weak_only', True), c['repo']))}
        save_json(self.d['folder'] / 'evidence' / '10-candidates.json', out)
        return out


def main():
    ids = sys.argv[1:]
    for d in load_designs():
        if ids and d['id'] not in ids:
            continue
        o = Search(d).run()
        strong = [c for c in o['candidates'] if c.get('tied_to_paper') or 'paper_link' in c['found_by']]
        print(f"{d['id']:6} names {o['names_searched']}  authors {len(o['authors'])}  candidates {len(o['candidates'])} "
              f"(tied to the paper or linked in it {len(strong)})", flush=True)
        for c in strong:
            print(f"        {c['repo']}  {c['found_by']}  {c['signs']}  licence {c.get('licence_detected')}  "
                  f"{c.get('status', '')} SWH {c.get('software_heritage')} WB {c.get('wayback')}", flush=True)


if __name__ == '__main__':
    main()
