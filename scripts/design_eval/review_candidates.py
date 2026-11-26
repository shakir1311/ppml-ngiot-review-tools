#!/usr/bin/env python3
"""Shows the reviewer, for one design, the candidate repositories that the search tied to the paper, with what is needed to judge each.

For each candidate that the paper links or that a sign ties to the paper (evidence/10-candidates.json) it prints the sources
that found it, the signs, the repository's own description, creation date, licence, and a reading-list flag (the name or
description says awesome, papers, survey, list, resources, or the README is mostly links), then one line naming the other,
name-only candidates. It reads only the search's saved responses; nothing of the paper.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/review_candidates.py <id> [<id> ...]
"""
import base64, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import design   # noqa: E402
from search_code import title_words   # noqa: E402

LIST_WORDS = re.compile(r'(?i)awesome|papers?\b|paper-?list|survey|reading|resources|references|curated|collection|arxiv|daily|digest|bib|zotero|literature|list\b|notes')


def raw_json(folder, prefix):
    for f in sorted((folder / 'evidence' / 'raw').glob(f'*-{prefix}*.json')):
        try:
            return json.load(open(f))
        except Exception:
            pass
    return None


def show(design_id):
    d = design(design_id)
    o = json.load(open(d['folder'] / 'evidence' / '10-candidates.json'))
    print(f"== {d['id']} ({d['first_author']} {d['year']}) names {o['names_searched']}  arXiv {o['arxiv_versions']}")
    for s in o['sources']:
        print('   ', s)
    if o['links_in_metadata']:
        print('    metadata links:', o['links_in_metadata'][:8])
    always = {'paper_link', 'github_author_account', 'scholexplorer', 'datacite', 'zenodo', 'orcid_work', 'orcid_researcher_url',
              'github_account_listed_in_orcid', 'huggingface_papers', 'papers_with_code_archive', 'arxiv_comment'}
    tied = [c for c in o['candidates'] if c.get('tied_to_paper') or set(c['found_by']) & always]
    for c in tied:
        owner, name = c['repo'].split('/')[3:5]
        meta = raw_json(d['folder'], f'gh-repo-{owner}-{name}'[:52]) or {}
        rd = raw_json(d['folder'], f'gh-readme-{owner}-{name}'[:52]) or {}
        text = base64.b64decode(rd['content']).decode('utf-8', 'replace') if isinstance(rd, dict) and rd.get('content') else ''
        lines = [l for l in text.splitlines() if l.strip()]
        link_share = sum(1 for l in lines if 'http' in l or '](' in l) / max(1, len(lines))
        is_list = bool(LIST_WORDS.search(name + ' ' + (meta.get('description') or ''))) or (len(lines) > 40 and link_share > 0.4)
        print(f"  * {c['repo']}  created {str(c.get('created'))[:10]}  licence {c.get('licence_detected')}  "
              f"{'READING-LIST? ' if is_list else ''}{c.get('status', '')}")
        print(f"      found by {c['found_by']}; signs {c['signs']}")
        print(f"      description: {(meta.get('description') or '')[:160]!r}; README lines {len(lines)}, link share {link_share:.2f}")
    tw = set(title_words(d['title']))
    for c in o['candidates']:
        if c in tied:
            continue
        name = c['repo'].split('/')[-1]
        words = set(re.findall(r'[a-z][a-z0-9]+', name.lower().replace('-', ' ').replace('_', ' ')))
        share = len(words & tw) / max(1, len(tw))
        if share >= 0.5 or any(n.split()[0].lower() in name.lower() for n in o['names_searched']):
            print(f"  ? {c['repo']}  NAME REPEATS TITLE/NAME (share {share:.2f})  found by {c['found_by']}; signs {c['signs']}  "
                  f"licence {c.get('licence_detected')} created {str(c.get('created'))[:10]}")
    others = [c['repo'].split('github.com/')[-1] for c in o['candidates'] if c not in tied]
    print(f"  name-only or untied ({len(others)}): {', '.join(others[:40])}")


if __name__ == '__main__':
    for i in sys.argv[1:]:
        show(i)
