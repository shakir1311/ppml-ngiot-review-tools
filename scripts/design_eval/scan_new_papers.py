#!/usr/bin/env python3
"""Says, for each new design's paper, whether the paper declares its own code on GitHub (or another host) and whether that is the repository we cloned, without showing any of the paper's text.

Reads the extracted, OCR-verified pages of paper/<Znn>/ and the PDF's link annotations (the link finder of scan_paper.py). For
each link to a code host it records the pages, whether it sits in the reference list, and a category for the sentence around it,
judged by local patterns: OWN (the paper declares it as its code: our code, implementation or artefact is available at …), OTHER
(a tool, library, baseline or dataset the paper uses or cites), or UNCLEAR. It compares each link with the repository we cloned
(same repository, same owner, or different). Availability statements and mentions of supplementary material are recorded as
categories with pages. Per design: evidence/paper-links.json and a verdict: the paper declares the cloned repository; declares
another repository; links code only as others' tools; links no code; or unclear. Only links, pages and categories are printed.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/scan_new_papers.py
"""
import json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, save_json, now   # noqa: E402
from scan_paper import urls_in, kind, clean, REF_HEAD, STATEMENTS, PAPER_WIDE   # noqa: E402

BASE = EVAL / 'new-designs'
HOSTS = r'github\.com|gitlab\.com|bitbucket\.org|gitee\.com|codeocean\.com|zenodo\.org|figshare\.com|anonymous\.4open\.science|huggingface\.co|osf\.io'
OWN = [r'\b(our|we|the proposed|this (paper|work|study|article)|the authors?)\b[^.]{0,140}\b(code|implementation|source|artifacts?|prototype|repository|scripts|experiments?)\b',
       r'\b(code|implementation|source code|artifacts?|prototype|repository)\b[^.]{0,80}\b(is|are|will be|has been|have been|can be)\b[^.]{0,50}\b(available|released|found|accessed|open[- ]?sourced|published|hosted)',
       r'(?:^|\n)\s*(code|source code|artifacts?|implementation|repository)\s*(availability)?\s*[:：]',
       r'\b(available|released|open[- ]?sourced)\s+(at|on|in)\b']
OTHER = [r'\b(we use|we used|using|based on|built (on|upon|with)|we adopt|adopted|borrowed|we follow|following|provided by|taken from|from the)\b',
         r'\b(library|framework|toolkit|toolchain|baseline|dataset|benchmark|compiler|official implementation of)\b']
SUPP = r'\bsupplement(ary|al)\s+(material|materials|data|file|files|information|items?)\b|\bonline appendix\b|\bappendix\b[^.]{0,40}\bonline\b'


def repo_of(url):
    m = re.search(r'(github\.com|gitlab\.com|gitee\.com|bitbucket\.org)/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)', url, re.I)
    return (m.group(2).lower(), re.sub(r'\.git$', '', m.group(3)).lower()) if m else None


def context_category(window):
    w = re.sub(r'\s+', ' ', window)
    own = any(re.search(p, w, re.I) for p in OWN)
    other = any(re.search(p, w, re.I) for p in OTHER)
    if own and not other:
        return 'OWN'
    if own and other:
        return 'OWN' if re.search(r'\b(our|we)\b[^.]{0,80}\b(code|implementation|source|artifacts?)\b[^.]{0,60}\b(available|released|at)\b', w, re.I) else 'UNCLEAR'
    return 'OTHER' if other else 'UNCLEAR'


def scan(folder, meta):
    zid = meta['id']
    pdir = folder / 'paper' / zid
    pages = sorted((pdir / 'text' / 'pages').glob('page_*.txt'))
    clone = repo_of(meta['repo'])
    links, stmts, supp = {}, {}, set()
    in_refs = False
    for p in pages:
        n = int(p.stem.split('_')[1])
        text = p.read_text(errors='replace')
        head = REF_HEAD.search(text)
        body, refs = (text, '') if in_refs is False and not head else ((text[:head.start()], text[head.start():]) if not in_refs else ('', text))
        flat = re.sub(r'-\n(?=[a-z])', '', text)
        if re.search(SUPP, re.sub(r'\s+', ' ', flat), re.I):
            supp.add(n)
        for cat in PAPER_WIDE:
            if re.search(STATEMENTS[cat], re.sub(r'\s*\n\s*', ' ', flat), re.I):
                stmts.setdefault(cat, set()).add(n)
        for part, is_ref in ((body, False), (refs, True)):
            for u in urls_in(part):
                if not re.search(HOSTS, u, re.I):
                    continue
                key = repo_of(u) or clean(u).lower()
                i = part.find(u.replace('https://', '').split('/')[0]) if u else -1
                anchor = re.escape('/'.join(key)) if isinstance(key, tuple) else re.escape(u.split('//')[-1][:30])
                m = re.search(anchor, re.sub(r'\s+', '', part), re.I)
                # the window: the sentence(s) around the link in the page's own text
                pos = part.lower().find((key[1] if isinstance(key, tuple) else u.split('/')[-1]).lower()[:20])
                window = part[max(0, pos - 350): pos + 120] if pos >= 0 else ''
                e = links.setdefault(str(key), {'url': clean(u), 'pages': set(), 'in_references': True, 'categories': set()})
                e['pages'].add(n)
                e['in_references'] &= is_ref
                e['categories'].add('REFERENCE' if is_ref else context_category(window))
        if head:
            in_refs = True
    import pymupdf
    doc = pymupdf.open(pdir / f'{zid}.pdf')
    for i, page in enumerate(doc, start=1):
        for ln in page.get_links():
            u = ln.get('uri') or ''
            if re.search(HOSTS, u, re.I):
                key = repo_of(u) or clean(u).lower()
                e = links.setdefault(str(key), {'url': clean(u), 'pages': set(), 'in_references': False, 'categories': {'UNCLEAR'}})
                e['pages'].add(i)
    rows = []
    for k, e in links.items():
        r = repo_of(e['url'])
        match = 'same repository' if r and clone and r == clone else ('same owner' if r and clone and r[0] == clone[0] else 'different')
        cat = 'OWN' if 'OWN' in e['categories'] else ('REFERENCE' if e['in_references'] else ('OTHER' if 'OTHER' in e['categories'] else 'UNCLEAR'))
        rows.append({'url': e['url'], 'host_kind': kind(e['url']), 'pages': sorted(e['pages']), 'in_references': e['in_references'],
                     'category': cat, 'vs_clone': match})
    own_same = [r for r in rows if r['category'] == 'OWN' and r['vs_clone'] != 'different']
    own_other = [r for r in rows if r['category'] == 'OWN' and r['vs_clone'] == 'different']
    any_same = [r for r in rows if r['vs_clone'] != 'different' and not r['in_references']]
    if own_same:
        verdict = 'the paper declares the cloned repository as its code'
    elif own_other:
        verdict = 'the paper declares a different repository as its code'
    elif any_same:
        verdict = 'the paper links the cloned repository, but the sentence does not say it is the paper\'s code (unclear)'
    elif rows:
        verdict = 'the paper links code only as others\' tools or references'
    else:
        verdict = 'the paper links no code'
    out = {'about': 'Code links in the paper (local scan of the OCR-verified pages and the PDF\'s link annotations); categories only, no text.',
           'made': now(), 'pages_scanned': len(pages), 'cloned_repository': meta['repo'], 'links': sorted(rows, key=lambda r: r['pages']),
           'statements': {k: sorted(v) for k, v in stmts.items()}, 'supplementary_mentioned_on_pages': sorted(supp), 'verdict': verdict}
    save_json(folder / 'evidence' / 'paper-links.json', out)
    return out


def main():
    for folder in sorted((BASE / 'designs').iterdir()):
        meta = json.load(open(folder / 'design.json'))
        if not (folder / 'paper' / meta['id'] / 'text' / 'pages').exists():
            print(f"{meta['id']}: not extracted yet")
            continue
        o = scan(folder, meta)
        print(f"\n{meta['id']} ({o['pages_scanned']} pages): {o['verdict']}")
        for r in o['links']:
            print(f"   {r['category']:9} {r['vs_clone']:15} p{r['pages']}  {r['url'][:90]}")
        if o['statements'] or o['supplementary_mentioned_on_pages']:
            print(f"   statements {o['statements']}; supplementary mentioned on pages {o['supplementary_mentioned_on_pages']}")


if __name__ == '__main__':
    main()
