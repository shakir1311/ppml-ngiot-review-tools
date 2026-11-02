#!/usr/bin/env python3
"""Check the links a paper's notes record to earlier work (notes/LINKS.json), against LINKS-PROTOCOL.md.

Every link must carry evidence: a quotation of the paper's own words, found on the page given (checked as
check_notes.py checks quotations). Values read from tables or figures are not accepted. Every corpus paper in the paper's
reference list (found by review/ref_links.py) must be accounted for, in links or in cited_only.

Usage: scripts/.venv/bin/python scripts/check_links.py ID [ID ...] | --all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'review'))
import corpus as C                      # noqa: E402
import check_notes as CN                # noqa: E402
import ref_links as RL                  # noqa: E402

TYPES = {'builds_on', 'measured_against', 'compared_not_measured', 'critique', 'positions_against'}
MAX_SAYS = 45


def primary_ids() -> list[str]:
    """the primary studies of the review (included, kind = primary)"""
    root = Path(__file__).resolve().parents[1] / 'myliteraturereviewpaper' / '_src'
    inc = json.loads((root / 'V17' / 'focus.json').read_text()).keys()
    return sorted(i for i in inc if json.loads((root / 'V14' / 'coding' / f'{i}.json').read_text())['kind'] == 'primary')


def check(pid: str, titles: dict, by: dict) -> tuple[list[str], list[str], dict]:
    err, warn = [], []
    entry = by[pid]
    folder = C.folder_of(entry)
    path = folder / 'notes' / 'LINKS.json'
    if not path.exists():
        return [f'no {path.relative_to(folder)}'], warn, {}
    try:
        d = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        return [f'LINKS.json is not valid JSON: {e}'], warn, {}
    if d.get('id') != pid:
        err.append(f"id is {d.get('id')!r}, not {pid}")
    links = d.get('links')
    if not isinstance(links, list):
        return err + ['"links" must be a list'], warn, {}
    cited_only = d.get('cited_only', [])
    if not isinstance(cited_only, list):
        err.append('"cited_only" must be a list of corpus IDs')
        cited_only = []
    pages = CN.Pages(folder)
    total = len(pages)
    for k, l in enumerate(links, 1):
        at = f"link {k} ({l.get('type', '?')} → {l.get('to') or l.get('to_name', '?')})"
        t = l.get('type')
        if t not in TYPES:
            err.append(f'{at}: type must be one of {sorted(TYPES)}')
        to = l.get('to')
        if to is not None and to not in by:
            err.append(f'{at}: "to" {to!r} is not a corpus ID')
        if to == pid:
            err.append(f'{at}: a paper cannot link to itself')
        if to is None and t != 'measured_against':
            err.append(f'{at}: works outside the corpus are recorded only as measured_against')
        if not str(l.get('to_name', '')).strip():
            err.append(f'{at}: "to_name" is empty')
        ref = l.get('ref')
        if ref is not None and not re.fullmatch(r'\d{1,3}', str(ref)):
            err.append(f'{at}: "ref" must be the reference number as a string, or null')
        says = str(l.get('says', '')).strip()
        if not says:
            err.append(f'{at}: "says" is empty')
        elif len(says.split()) > MAX_SAYS:
            err.append(f'{at}: "says" has {len(says.split())} words (at most {MAX_SAYS})')
        if t == 'measured_against':
            for f in ('metric', 'result', 'setting'):
                if not str(l.get(f, '')).strip():
                    err.append(f'{at}: measured_against needs "{f}"')
            if l.get('same_setting') is not True:
                err.append(f'{at}: measured_against needs "same_setting": true')
        elif t == 'compared_not_measured':
            for f in ('result', 'setting'):
                if not str(l.get(f, '')).strip():
                    err.append(f'{at}: compared_not_measured needs "{f}" (setting = the basis of the comparison)')
            if l.get('same_setting') is not False:
                err.append(f'{at}: compared_not_measured needs "same_setting": false')
        ev = l.get('evidence')
        if not isinstance(ev, list) or not ev:
            err.append(f'{at}: "evidence" with at least one page is required')
            continue
        for j, e in enumerate(ev, 1):
            m = re.fullmatch(r'p(\d+)', str(e.get('page', '')).strip())
            if not m:
                err.append(f'{at}, evidence {j}: "page" must look like "p4"')
                continue
            p = int(m.group(1))
            if not 1 <= p <= total:
                err.append(f'{at}, evidence {j}: p{p} is outside the paper (p1–p{total})')
                continue
            if e.get('image') or e.get('what'):
                err.append(f'{at}, evidence {j}: record the paper\'s words — a quotation from its text, not a value '
                           'read from a table or figure')
                continue
            q = str(e.get('quote', '')).strip()
            if not q:
                err.append(f'{at}, evidence {j}: a verbatim quotation from the text is required')
                continue
            ok, remark = CN.find_fragment(q, pages, [p])
            if not ok:
                err.append(f'{at}, evidence {j} [p{p}]: {remark}')
    # every corpus paper in the reference list is accounted for
    mapped = RL.links(pid, titles, by)
    found = {f['corpus_id'] for f in mapped['in_corpus']}
    linked = {l.get('to') for l in links if l.get('to')}
    missing = sorted(found - linked - set(cited_only))
    if missing:
        err.append(f'corpus papers in the reference list not accounted for (links or cited_only): {", ".join(missing)}')
    for c in cited_only:
        if c not in by:
            err.append(f'cited_only: {c!r} is not a corpus ID')
    if mapped.get('style') == 'author-year':
        warn.append('author-year reference list: corpus papers were found by their titles in the reference section')
    stats = {'links': len(links), 'cited_only': len(cited_only), 'in_corpus_refs': len(found),
             'measured': sum(l.get('type') == 'measured_against' for l in links)}
    return err, warn, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--all', action='store_true', help='every primary study of the review')
    a = ap.parse_args()
    ids = primary_ids() if a.all else a.ids
    if not ids:
        ap.error('give paper IDs, or --all')
    by = RL.manifest()
    titles = RL.corpus_titles()
    bad = 0
    for pid in ids:
        err, warn, s = check(pid, titles, by)
        status = 'FAIL' if err else 'PASS'
        bad += bool(err)
        extra = (f"  {s['links']} links ({s['measured']} measured), {s['cited_only']} cited only, "
                 f"{s['in_corpus_refs']} corpus references") if s else ''
        print(f'{pid}  {status}{extra}')
        for e in err:
            print(f'   ERROR  {e}')
        for w in warn:
            print(f'   warn   {w}')
    print(f'\n{len(ids) - bad} pass, {bad} fail')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
