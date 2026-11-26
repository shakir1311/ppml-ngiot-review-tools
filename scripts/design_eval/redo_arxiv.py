#!/usr/bin/env python3
"""Finds, through Semantic Scholar, the arXiv preprint of each design whose arXiv look-up arXiv refused (status 429) during the code search, and checks that preprint for code.

arXiv refused the title queries of 19 designs during the search of 10 November 2026 and kept refusing on retry, so the
preprint is found instead from Semantic Scholar's record of the DOI (its external identifiers only; no abstract is asked
for). For a preprint found, Hugging Face Papers and the Papers with Code archive are asked for its code. What is found is
merged into evidence/10-candidates.json (arXiv versions, a line in `sources`, new candidates); every request is recorded as
in search_code.py.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/redo_arxiv.py [<id> ...]   (all designs with a refused look-up)
"""
import json, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import load_designs, save_json, now   # noqa: E402
from search_code import Search   # noqa: E402


def refused(d):
    log = d['folder'] / 'evidence' / 'log.jsonl'
    rows = [json.loads(l) for l in open(log)] if log.exists() else []
    tried = [r for r in rows if r['label'] == 'arxiv-title']
    return bool(tried) and all(r['status'] != 200 for r in tried)


def redo(d):
    path = d['folder'] / 'evidence' / '10-candidates.json'
    o = json.load(open(path))
    s = Search(d)
    s.authors, s.names = o['authors'], o['names_searched']
    for c in o['candidates']:
        s.cands[c['repo']] = c
    st, j = s.rec.fetch('semanticscholar-doi', f"https://api.semanticscholar.org/graph/v1/paper/DOI:{d['doi']}",
                        params={'fields': 'externalIds,title'})
    arx = sorted(set(o.get('arxiv_versions', [])) | ({(j.get('externalIds') or {}).get('ArXiv')} - {None} if isinstance(j, dict) else set()))
    s.notes.append(f"Semantic Scholar (in place of the refused arXiv look-up): {st}; arXiv preprint: {arx or 'none'}")
    if arx:
        s.huggingface(arx)
        s.pwc(arx)
    o['arxiv_versions'] = arx
    o['sources'] = [x for x in o['sources'] if not x.startswith('arXiv: 429')] + s.notes
    o['candidates'] = sorted(s.cands.values(), key=lambda c: (not c.get('tied_to_paper'), c.get('weak_only', True), c['repo']))
    o['arxiv_redone'] = now()
    save_json(path, o)
    return s.notes


def main():
    ids = set(sys.argv[1:])
    for d in load_designs():
        if (ids and d['id'] not in ids) or (not ids and not refused(d)):
            continue
        print(f"{d['id']:6} " + ' | '.join(redo(d)), flush=True)
        time.sleep(3)


if __name__ == '__main__':
    main()
