#!/usr/bin/env python3
"""Evidence pages of the PPML review (V29 onwards) for the Review Viewer: for every sentence that carries an evidence
marker, the PDF page of the cited evidence, so that clicking its reference [n] opens the cited paper at the page where
the sentence's fact is quoted.

A marker ⟦id:P3⟧ names an answer of the study's extraction record (search-ppml/evidence/sheets/<id>.json); of that
answer's quotations, the one sharing most words with the sentence gives the page (every quotation was found on its page
by scripts/paper_ppml/check_sheets.py; pages are PDF pages). A marker ⟦F:<refkey>:<page>⟧ gives the page of a foundation
(EDPB guidelines, GDPR, PRISMA 2020) directly. Each sentence is checked against the version's assembled text
(build/paper-V<n>.md); a sentence not found there is dropped, so the map never belongs to another version.
Same output format as scripts/paper/links.py, so the viewer reads both.

Writes myliteraturereviewpaper/ppml2026/build/LINKS-V<n>.json.
Usage: python3 scripts/paper_ppml/links.py <version-number>
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
B = P / 'build'
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build                                      # noqa: E402  (studies(): the study paragraphs as the build uses them)

W = re.compile(r'[a-z0-9]+')
words = lambda s: [w for w in W.findall(s.lower()) if len(w) > 2]


def evidence(sid, key):
    f = SHEETS / f'{sid}.json'
    if not f.exists():
        return []
    return (json.loads(f.read_text(encoding='utf-8')).get('answers', {}).get(key) or {}).get('evidence', [])


def main(version):
    refs = json.loads((P / 'refs.json').read_text(encoding='utf-8'))
    S = build.studies()
    import os
    parts = pathlib.Path(os.environ.get('PPML_PARTS') or P / 'parts')
    src = '\n\n'.join(f.read_text(encoding='utf-8') for f in sorted(parts.glob('*.md')))
    src = re.sub(r'\{\{STUDY:(\w+)\}\}', lambda m: S.get(m.group(1), ''), src)
    src = build.define_once(src)                                  # as the paper: abbreviations defined once
    _h, _f, _b = build.split_front(src)                           # and used consistently after their definition
    src = _h + _f + build.consistent_forms(_b)
    plain = re.sub(r'\{\{[^}]*\}\}|\[@[^\]]*\]', '', src)
    paper = (B / f'paper-V{version}.md').read_text(encoding='utf-8')
    paras = [set(words(re.sub(r'\[\d{1,3}\]', ' ', p))) for p in paper.split('\n\n')]
    entries, dropped = [], 0
    for m in re.finditer(r'([^⟦⟧]*?)((?:\s*⟦[^⟧]+⟧)+)', plain):
        chunk = m.group(1).rstrip().rstrip('.')
        sentence = re.split(r'(?<=[.!?])\s+|\n', chunk)[-1].strip()
        ws = set(words(sentence))
        if not ws:
            continue
        if not any(len(ws & p) / len(ws) >= 0.9 for p in paras):
            dropped += 1
            continue
        for mk in re.findall(r'⟦([^⟧]+)⟧', m.group(2)):
            if mk.startswith('F:'):
                _, ref, pages = mk.split(':')
                if ref in refs:
                    for pg in pages.split(','):
                        entries.append({'key': ref, 'sheet': ref, 'q': 'page', 'page': int(pg), 'sentence': sentence, 'quote': ''})
                continue
            sid, _, ks = mk.partition(':')
            sid = sid.strip()
            if sid not in refs:
                continue
            for k in (x.strip() for x in ks.split(',')):
                ev = [e for e in evidence(sid, k) if str(e.get('page', '0')).isdigit() and int(e['page']) > 0]
                if not ev:
                    continue
                best = max(ev, key=lambda e: len(ws & set(words(e['quote']))))
                entries.append({'key': sid, 'sheet': sid, 'q': k, 'page': int(best['page']), 'sentence': sentence,
                                'quote': best['quote'][:160]})
    out = B / f'LINKS-V{version}.json'
    out.write_text(json.dumps({'version': int(version), 'entries': entries, 'dropped_not_in_version': dropped},
                              indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{out.name}: {len(entries)} evidence links from {len({e["sentence"] for e in entries})} sentences; '
          f'{dropped} sentence(s) not in V{version}, dropped')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__))
