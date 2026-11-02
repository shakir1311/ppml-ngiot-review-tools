#!/usr/bin/env python3
"""Find the research or survey questions that the surveys in the corpus state for themselves (7 October 2026: the author
asked to "deduce from our corpus the various survey questions people have devised for similar studies", to judge the
review's own survey questions SQ1-SQ5).

Surveys: the 30 secondary studies included in the review (search-ppml/FINAL-STUDIES-2026-10-05.csv) and every paper of the
corpus index (search-ppml/CORPUS-INDEX-2026-10-04.csv) whose kind is a survey, including the supervisors' surveys. For each
full text (text/pages/page_NNNN.txt), the pages that state questions are found by fixed patterns (RQ1, "research
question", "survey question", Q1:, "we answer the following questions" …) and written with their lines, so that a reader
can copy each question verbatim with its page.

Output: search-ppml/evidence/sq-review/CORPUS-RQ-CANDIDATES.json
Then a reader copies the questions into search-ppml/evidence/sq-review/CORPUS-RQS.json (see RQ-COMPILE-GUIDE.md there);
'check' finds every copied question word for word on the page it names.

Usage: python3 scripts/paper_ppml/survey_rqs.py            (candidates)
       python3 scripts/paper_ppml/survey_rqs.py check      (the compiled questions)
"""
import csv, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import check_sheets as CS                                          # noqa: E402  (folder_of: the copy the review rests on)

PAT = re.compile(r'\bRQ\s?-?\s?\d|\bSQ\s?-?\s?\d|research questions?|survey questions?|review questions?|guiding questions?|'
                 r'\bQ\s?\d\s?[:.)]|following questions|questions? (?:we|this (?:survey|review|paper)) (?:aim|seek|address|answer)', re.I)


def surveys():
    out = {}
    for r in csv.DictReader(open(ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')):
        if r['kind'] == 'secondary':
            out[r['corpus_id']] = {'source': 'included in the review', 'title': r.get('title', ''), 'year': r.get('year', ''),
                                   'folder': CS.folder_of(r['corpus_id'])}
    for r in csv.DictReader(open(ROOT / 'search-ppml' / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8')):
        if 'survey' in r['kind'] and r['id'] not in out:
            out[r['id']] = {'source': r['collection'] + (' (supervisor)' if 'supervisor' in r['kind'] else ''), 'title': r['title'],
                            'year': r['year'], 'folder': (ROOT / r['pdf']).parent}
    return out


def main():
    res, n_with = {}, 0
    for k, s in sorted(surveys().items()):
        pages = sorted((pathlib.Path(s['folder']) / 'text' / 'pages').glob('page_*.txt'))
        hits = []
        for p in pages:
            lines = p.read_text(encoding='utf-8', errors='ignore').splitlines()
            idx = [i for i, l in enumerate(lines) if PAT.search(l)]
            if idx:
                keep = sorted({j for i in idx for j in range(max(0, i - 2), min(len(lines), i + 8))})
                hits.append({'page': int(p.stem.split('_')[1]), 'lines': [lines[j] for j in keep]})
        res[k] = {k2: (str(v) if k2 == 'folder' else v) for k2, v in s.items()} | {'pages_searched': len(pages), 'hits': hits}
        n_with += bool(hits)
    out = ROOT / 'search-ppml' / 'evidence' / 'sq-review' / 'CORPUS-RQ-CANDIDATES.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    no_text = [k for k, v in res.items() if not v['pages_searched']]
    print(f'{len(res)} surveys; {n_with} with candidate passages; {len(no_text)} without extracted text: {no_text[:12]}')


def check():
    cand = json.loads((ROOT / 'search-ppml' / 'evidence' / 'sq-review' / 'CORPUS-RQ-CANDIDATES.json').read_text(encoding='utf-8'))
    comp = json.loads((ROOT / 'search-ppml' / 'evidence' / 'sq-review' / 'CORPUS-RQS.json').read_text(encoding='utf-8'))
    bad = n = 0
    for s in comp['surveys']:
        folder = pathlib.Path(cand.get(s['id'], {}).get('folder', ''))
        for q in s.get('questions', []):
            n += 1
            pf = folder / 'text' / 'pages' / f"page_{int(q['page']):04d}.txt"
            if not pf.exists() or not CS.found(q['text'], pf.read_text(encoding='utf-8', errors='ignore')):
                bad += 1
                print(f"{s['id']} {q.get('label', '')}: not on p{q['page']}: {q['text'][:80]!r}")
    print(f"{len(comp['surveys'])} surveys, {n} questions; {bad} not found on their page")
    return bad


if __name__ == '__main__':
    sys.exit(1 if check() else 0) if sys.argv[1:] == ['check'] else main()
