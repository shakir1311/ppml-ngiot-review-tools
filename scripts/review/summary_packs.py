#!/usr/bin/env python3
"""Assemble one input pack per paper, from which its short note (notes/SUMMARY.md) is written.

A pack gathers, without rewording: the bibliographic record, the eligibility decision, the classification record
(_src/V14/coding), the digest of the page-cited notes (_src/V14/digests), and the sentences of the current review
draft that cite the paper. An index of all papers is written beside the packs, so that related papers can be named
by their IDs.

Usage: scripts/.venv/bin/python scripts/review/summary_packs.py <out_dir> [ID ...]
       REVIEW_VERSION=V17 ... uses the V17 draft and data (default V16)
"""
import importlib, json, os, pathlib, re, sys
VERSION = os.environ.get('REVIEW_VERSION', 'V16')
T = importlib.import_module('tables_' + VERSION.lower())
from tables_v14 import THEMES, ROOT

DRAFT = ROOT / 'myliteraturereviewpaper' / '_src' / VERSION
DIGESTS = ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'digests'
SENT = re.compile(r'(?<=[.!?])\s+(?=[A-Z(\[{@])')


def first_author(d, i):
    r = d['refs'].get(i)
    if r and r.get('authors'):
        return r['authors'][0][0] + (' et al.' if len(r['authors']) > 1 else ''), r['year']
    names = [x.strip() for x in re.split(r'[,;]', d['papers'][i]['authors']) if x.strip()]
    return names[0].split()[-1] + (' et al.' if len(names) > 1 else ''), d['papers'][i]['year']


def citation(d, i):
    r, p = d['refs'].get(i), d['papers'][i]
    if not r:
        return p['venue']
    bits = [r.get('container') or '', r.get('volume') and f"vol. {r['volume']}", r.get('issue') and f"no. {r['issue']}",
            r.get('pages') and f"pp. {r['pages']}", r.get('article_number') and f"art. {r['article_number']}"]
    return ', '.join(b for b in bits if b) or p['venue']


def draft_sentences():
    """Sentences of the review draft, each with the heading it sits under."""
    out, head = [], ''
    for f in sorted(DRAFT.glob(f'{VERSION}-part*.md')):
        for line in f.read_text(encoding='utf-8').splitlines():
            if line.startswith('#'):
                head = line.lstrip('# ').strip()
                continue
            line = re.sub(r'^\s*(?:[-*]|\d+\.)\s+', '', line.strip())
            if not line or line.startswith('<!--') or line.startswith('{{'):
                continue
            out += [(head, s) for s in SENT.split(line)]
    return out


def pack(d, i, sentences):
    p, c = d['papers'][i], d['coding'].get(i, {})
    fa, yr = first_author(d, i)
    ex = d['excluded'].get(i)
    status = f"excluded ({ex['criterion']}): {ex['reason']}" if ex else 'included'
    theme = c.get('theme', '')
    L = [f'# Pack for {i}', '',
         f"- write to: corpus/{p['folder']}/notes/SUMMARY.md",
         f"- full text, for checking a number: corpus/{p['folder']}/text/full.txt", '',
         '## Record', '',
         f"- short citation: {fa} {yr}",
         f"- title: {p['title']}",
         f"- authors: {p['authors']}",
         f"- published in: {citation(d, i)}",
         f"- DOI: {(d['refs'].get(i) or {}).get('doi') or p['doi'] or 'none'}",
         f"- study: {T.kind(d, i)}; {p['document_type']}; {p['research_type']}",
         f"- evidence: {p['evaluation_type']}",
         f"- status in the review: {status}",
         f"- theme: {THEMES.get(theme, theme)}" + (f" — {c['theme_reason']}" if c.get('theme_reason') else ''), '']
    if c:
        L += ['## Classification record', '', f"- description: {c.get('description', '')}",
              f"- key result: {c.get('key_result', '')}"]
        for k in ('setting', 'learning', 'privacy_mechanisms', 'threats', 'defences'):
            if c.get(k):
                L.append(f"- {k.replace('_', ' ')}: {', '.join(c[k])}")
        lg = c.get('ledger') or {}
        if lg.get('used'):
            L.append('- ledger: ' + '; '.join(f'{k} {v}' for k, v in lg.items() if k != 'used' and v))
        ev = c.get('evaluation') or {}
        if any(ev.values()):
            L.append('- evaluation: ' + '; '.join(f"{k} {', '.join(v) if isinstance(v, list) else v}"
                                                   for k, v in ev.items() if v not in ('', [], None)))
        sv = c.get('survey')
        if sv:
            cov = ', '.join(k for k, v in sv.get('covers', {}).items() if v)
            L.append(f"- survey: years {sv.get('years_covered')}; studies {sv.get('studies_reviewed')}; "
                     f"protocol {sv.get('protocol')}; covers {cov or 'none of the review topics'}")
        for k in ('assumptions', 'open_issues', 'future_directions'):
            for x in c.get(k) or []:
                L.append(f"- {k.replace('_', ' ')}: {x.get('text') or x.get('code')} [{x.get('pages', '')}]")
        L.append('')
    if i in T.APPROACH:
        a = T.APPROACH[i]
        L += ['## Row in the table of blockchain-based approaches', '',
              f'- ledger {a[0]}; ledger roles {a[1]} (A aggregates, R records, V verifies, I incentives); '
              f'check {a[2]}; relies on {a[3]}', '']
    if i in [x if isinstance(x, str) else x[0] for x in T.CLOSEST]:
        L += ['## Listed among the closest surveys (comparison table)', '']
    dg = DIGESTS / f'{i}.md'
    if dg.exists():
        body = dg.read_text(encoding='utf-8').split('\n## ', 1)
        L += ['## Digest of the page-cited notes', '', '## ' + body[1] if len(body) > 1 else body[0], '']
    cites = [(h, s) for h, s in sentences if re.search(rf'@{i}(?![0-9A-Za-z])', s)]
    L += ['## Sentences of the review draft that cite this paper', '']
    L += [f'- [{h}] {s}' for h, s in cites] or ['- none']
    return '\n'.join(L) + '\n'


def main(out_dir, ids):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    d = T.load()
    sentences = draft_sentences()
    for i in ids or d['papers']:
        (out / f'{i}.md').write_text(pack(d, i, sentences), encoding='utf-8')
    idx = ['# Index of the corpus', '', 'ID | first author, year | title | study | status', '--- | --- | --- | --- | ---']
    for i, p in d['papers'].items():
        fa, yr = first_author(d, i)
        idx.append(f"{i} | {fa} {yr} | {p['title']} | {T.kind(d, i)} | {'excluded' if i in d['excluded'] else 'included'}")
    (out / 'index.md').write_text('\n'.join(idx) + '\n', encoding='utf-8')
    print(f'{len(ids or d["papers"])} packs and the index written to {out}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
