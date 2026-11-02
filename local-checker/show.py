#!/usr/bin/env python3
"""Show the person checking a verdict the passages it rests on — in their browser, never in the terminal.

    local-checker/.venv/bin/python local-checker/show.py RESULTS.jsonl ID [ID ...]

Writes local-checker/show/passages.html (the statement, the verdict, and the passage that supports it and the one that
contradicts it, each with its page) and opens it. Prints only "opened". The page is for the person; Claude does not
read it (workspace rule: no paper text to Claude).
"""
import html
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_claims as cc


def main(results, ids):
    rows = {r['id']: r for r in map(json.loads, Path(results).read_text().splitlines())}
    claims = {}
    for f in (HERE / 'data').glob('*.jsonl'):
        if not f.name.endswith('-results.jsonl'):
            for line in f.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    c = json.loads(line)
                    claims[c['id']] = c
    folders = {p['key']: cc.ROOT / p['folder'] for p in json.loads(cc.PAPERS.read_text())['papers']}
    parts = ['<!doctype html><meta charset="utf-8"><title>Checker passages</title>',
             '<style>body{font:15px/1.5 -apple-system,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#222}'
             'h2{font-size:17px;margin-top:32px}.s{background:#eef6ee;border-left:4px solid #2e7d32;padding:8px 12px}'
             '.c{background:#fbeeee;border-left:4px solid #b71c1c;padding:8px 12px}.m{color:#555}</style>']
    for i in ids:
        r, c = rows[i], claims.get(i, {})
        paper = cc.Paper(folders[r['key']])
        parts.append(f"<h2>{html.escape(i)} — verdict: {html.escape(r['verdict'])}</h2>")
        parts.append(f"<p><b>Statement:</b> {html.escape(c.get('claim', '?'))}</p>")
        for label, key, cls, score in (('Supporting passage', 'entails_passage', 's', r['entails']),
                                       ('Contradicting passage', 'contradicts_passage', 'c', r['contradicts'])):
            at = r.get(key)
            if at is None:
                parts.append(f'<p class="m">{label}: none</p>')
                continue
            page, text = paper.passages[at]
            parts.append(f'<p class="m">{label} — page {page}, score {score:.2f}</p><div class="{cls}">{html.escape(text)}</div>')
    out = HERE / 'show' / 'passages.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text('\n'.join(parts), encoding='utf-8')
    subprocess.run(['open', str(out)])
    print('opened')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
