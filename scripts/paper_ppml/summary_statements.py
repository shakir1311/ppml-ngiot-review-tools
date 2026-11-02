#!/usr/bin/env python3
"""Turn the installed short notes of the included studies into statements for the local fact checker
(local-checker/run.sh): one line per sentence, {"id", "key", "claim", "pages"}, the pages from the sentence's [pN] cites.
Writes search-ppml/evidence/summaries-recut/statements.jsonl. The claims are our own words (the notes'), not the papers'.
Usage: python3 scripts/paper_ppml/summary_statements.py
"""
import csv, json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'search-ppml' / 'evidence' / 'summaries-recut' / 'statements.jsonl'
PAGE = re.compile(r'\[p(\d+)(?:\s*[–-]\s*p?(\d+))?')
inc = {r['corpus_id']: ROOT / r['folder'] for r in csv.DictReader((ROOT / 'corpus/ppmlcorpus/included/INDEX.csv').open(encoding='utf-8'))}
n = 0
with open(OUT, 'w', encoding='utf-8') as fh:
    for cid, folder in sorted(inc.items()):
        f = folder / 'notes' / 'SUMMARY.md'
        if not f.exists():
            continue
        text = f.read_text(encoding='utf-8', errors='replace')
        if 'Fabric and cost' not in text and 'What it treats' not in text:
            continue                                            # only the re-cut notes
        body = re.sub(r'^#.*$|^\*.*\*$', '', text, flags=re.M)
        body = re.sub(r'\*\*[^*]+\.\*\*', '', body)
        for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9(])', re.sub(r'\s+', ' ', body)):
            pages = sorted({int(a) for a, b in PAGE.findall(s)} | {p for a, b in PAGE.findall(s) if b for p in range(int(a), int(b) + 1)})
            claim = re.sub(r'\s*\[p[^\]]*\]', '', s).strip()
            if len(claim.split()) < 5:
                continue
            n += 1
            fh.write(json.dumps({'id': f'{cid}-{n}', 'key': cid, 'claim': claim, 'pages': pages}, ensure_ascii=False) + '\n')
print(f'{n} statements -> {OUT.relative_to(ROOT)}')
