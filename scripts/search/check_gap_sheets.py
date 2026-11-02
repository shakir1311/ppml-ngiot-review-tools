#!/usr/bin/env python3
"""Check the gap-check sheets (search/gapcheck/sheets/<id>.json) against the papers.

For each sheet: every condition C1-C6 has an answer "yes" or "no"; every "yes" has evidence; every quotation is on its
cited page of the paper (the corpus checker's matching, scripts/check_notes.py: the words run on, in order, in the
text of that page as any extraction engine read it); closes_gap is true exactly when C1-C5 are all "yes". The paper
folder is found in the search-corpus manifest (corpus/searchcorpus/MANIFEST-2026-10-02.csv) by id, or by corpus id
through the corpus manifest. Writes search/gapcheck/CHECK.json.

Usage: python3 scripts/search/check_gap_sheets.py [<id> ...]
"""
import csv, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts' / 'review'))
import check_notes as CN                 # noqa: E402
import notes_format as N                 # noqa: E402
import ref_links as RL                   # noqa: E402

SHEETS = ROOT / 'search' / 'gapcheck' / 'sheets'
CONDS = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6']


def folder_of(pid):
    for r in csv.DictReader(open(ROOT / 'corpus' / 'searchcorpus' / 'MANIFEST-2026-10-02.csv', encoding='utf-8')):
        if r['id'] == pid or (r['corpus_id'] and r['corpus_id'] == pid):
            return ROOT / r['folder']
    by = RL.manifest()
    return ROOT / 'corpus' / by[pid]['folder'] if pid in by else None


def check(path):
    s = json.loads(path.read_text(encoding='utf-8'))
    err = []
    folder = folder_of(s.get('id', path.stem))
    if not folder or not (folder / 'text' / 'pages').exists():
        return {'id': path.stem, 'passed': False, 'errors': [f'no paper folder with page text for {path.stem}']}
    pages = CN.Pages(folder)
    tested = 0
    for c in CONDS:
        a = s.get(c)
        if not isinstance(a, dict) or a.get('answer') not in ('yes', 'no'):
            err.append(f'{c}: answer must be "yes" or "no"')
            continue
        if a['answer'] == 'yes' and not a.get('evidence'):
            err.append(f'{c}: "yes" without evidence')
        for e in a.get('evidence', []):
            p, q = e.get('page'), e.get('quote', '')
            if not isinstance(p, int) or not 1 <= p <= len(pages):
                err.append(f'{c}: page {p} is not a page of the paper ({len(pages)} pages)')
                continue
            for fragment in N.fragments(q):
                ok, remark = CN.find_fragment(fragment, pages, [p])
                if remark == 'too short to test':
                    continue
                tested += 1
                if not ok:
                    err.append(f'{c}: quotation not on p{p} — "{fragment[:80]}" — {remark}')
    want = all(isinstance(s.get(c), dict) and s[c].get('answer') == 'yes' for c in CONDS[:5])
    if s.get('closes_gap') is not want:
        err.append(f'closes_gap is {s.get("closes_gap")!r} but C1-C5 give {want}')
    return {'id': s.get('id', path.stem), 'passed': not err, 'quotations_tested': tested, 'closes_gap': want,
            'meets': [c for c in CONDS if isinstance(s.get(c), dict) and s[c].get('answer') == 'yes'], 'errors': err}


def main(ids):
    files = [SHEETS / f'{i}.json' for i in ids] if ids else sorted(SHEETS.glob('*.json'))
    results = [check(f) for f in files]
    if not ids:
        (ROOT / 'search' / 'gapcheck' / 'CHECK.json').write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding='utf-8')
    for r in results:
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['id']}: meets {', '.join(r.get('meets', [])) or 'none'}; "
              f"closes the gap: {r.get('closes_gap')}; {r.get('quotations_tested', 0)} quotations tested")
        for e in r['errors'][:20]:
            print('   -', e)
    sys.exit(0 if all(r['passed'] for r in results) else 1)


if __name__ == '__main__':
    main(sys.argv[1:])
