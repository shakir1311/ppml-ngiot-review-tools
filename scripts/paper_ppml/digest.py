#!/usr/bin/env python3
"""Print a compact digest of evidence sheets (answers and values, no quotations) for writing the synthesis.

Usage: python3 scripts/paper_ppml/digest.py [--kind primary|secondary] [--keys P2,P4] [id ...]
"""
import csv, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
SH = ROOT / 'search-ppml' / 'evidence' / 'sheets'
args = sys.argv[1:]
kind = args[args.index('--kind') + 1] if '--kind' in args else None
keys = args[args.index('--keys') + 1].split(',') if '--keys' in args else None
ids = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] not in ('--kind', '--keys'))]
for f in sorted(SH.glob('*.json')):
    s = json.loads(f.read_text(encoding='utf-8'))
    if (ids and f.stem not in ids) or (kind and s.get('kind') != kind):
        continue
    print(f'### {f.stem} ({s.get("kind")}) {s.get("title", "")[:90]}')
    for k, a in s.get('answers', {}).items():
        if keys and k not in keys:
            continue
        v = a.get('values') or {}
        pages = sorted({e.get('page') for e in a.get('evidence', [])}, key=lambda x: (str(type(x)), x))
        print(f'{k} [{a.get("located_via", "")}; pp {pages}]: {a.get("answer", "")}' + (f' || {json.dumps(v, ensure_ascii=False)}' if v else ''))
    print()
