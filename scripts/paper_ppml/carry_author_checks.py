#!/usr/bin/env python3
"""Carry the author checks of one version into the next: keep every check of AUTHOR-CHECKS-V<prev>.json whose anchor
("find") is still in the text of build/paper-V<next>.md, add the checks listed in NEW-AUTHOR-CHECKS-V<next>.json, and
report the anchors that are gone (to be re-anchored or dropped by hand). Writes AUTHOR-CHECKS-V<next>.json (never over an
existing file).

Usage: python3 scripts/paper_ppml/carry_author_checks.py <prev> <next>
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'


def plain(text):
    text = re.sub(r'⟦[^⟧]*⟧', '', text)
    text = text.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    return re.sub(r'\s+', ' ', text)


def main():
    prev, nxt = sys.argv[1], sys.argv[2]
    out = P / f'AUTHOR-CHECKS-V{nxt}.json'
    if out.exists():
        sys.exit(f'{out.name} exists')
    old = json.loads((P / f'AUTHOR-CHECKS-V{prev}.json').read_text(encoding='utf-8'))
    text = plain((P / 'build' / f'paper-V{nxt}.md').read_text(encoding='utf-8'))
    kept, gone = [], []
    for c in old['checks']:
        (kept if plain(c['find']) in text else gone).append(c)
    new_f = P / f'NEW-AUTHOR-CHECKS-V{nxt}.json'
    added = json.loads(new_f.read_text(encoding='utf-8')) if new_f.exists() else []
    missing_new = [c for c in added if plain(c['find']) not in text]
    out.write_text(json.dumps({**{k: v for k, v in old.items() if k != 'checks'}, 'checks': kept + [c for c in added if c not in missing_new]},
                              indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'kept {len(kept)} of {len(old["checks"])}; added {len(added) - len(missing_new)}; anchors gone: {len(gone)}; '
          f'new anchors not found: {len(missing_new)}')
    for c in gone + missing_new:
        print(f"  [{c['kind']}] {c['find'][:90]}")


if __name__ == '__main__':
    main()
