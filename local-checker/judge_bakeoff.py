#!/usr/bin/env python3
"""Score a local model as context judge on data/context-set.jsonl: does it tell the authors' own work from other work,
and does it refuse to let other work support a statement about the authors' own work?

    local-checker/.venv/bin/python local-checker/judge_bakeoff.py MODEL [--think]

Each test quotation is found in its paper (the passage on its page that contains it) and given to the judge with the
quotation itself as the statement. Expected: own -> about 'own' and verdict 'supports'; other or mixed -> not both.
Prints counts and timings only; writes data/bakeoff-<model>.jsonl (ids, answers, seconds — no text).
"""
import argparse
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_claims as cc
from context_judge import Judge


def squash(s):
    return re.sub(r'[^a-z0-9]', '', cc.clean(s).lower())


def locate(paper, page, quote):
    """The shortest passage on the page that contains the quotation (or its first ten words)."""
    q = squash(quote)
    head = squash(' '.join(quote.split()[:10]))
    hits = [i for i, (p, t) in enumerate(paper.passages) if p == page and (q in squash(t) or head in squash(t))]
    return min(hits, key=lambda i: len(paper.passages[i][1])) if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model')
    ap.add_argument('--think', action='store_true')
    a = ap.parse_args()
    folders = {p['key']: cc.ROOT / p['folder'] for p in json.loads(cc.PAPERS.read_text())['papers']}
    items = [json.loads(l) for l in (HERE / 'data' / 'context-set.jsonl').read_text().splitlines() if l.strip()]
    judge, papers, out = Judge(a.model, think=a.think), {}, []
    for it in items:
        paper = papers.get(it['key']) or papers.setdefault(it['key'], cc.Paper(folders[it['key']]))
        i = locate(paper, it['page'], it['quote'])
        if i is None:
            out.append({'id': it['id'], 'label': it['label'], 'located': False})
            continue
        ans = judge.ask(paper, i, it['quote'])
        out.append({'id': it['id'], 'label': it['label'], 'located': True, **ans})
    tag = a.model.replace(':', '-').replace('/', '-') + ('-think' if a.think else '')
    (HERE / 'data' / f'bakeoff-{tag}.jsonl').write_text('\n'.join(json.dumps(r) for r in out) + '\n')
    done = [r for r in out if r['located']]
    own = [r for r in done if r['label'] == 'own']
    not_own = [r for r in done if r['label'] != 'own']
    ok_own = sum(r['about'] == 'own' and r['verdict'] == 'supports' for r in own)
    danger = [r['id'] for r in not_own if r['about'] == 'own' and r['verdict'] == 'supports']
    about_ok = sum((r['about'] == 'own') == (r['label'] == 'own') for r in done)
    invalid = sum(r['about'] == 'invalid' for r in done)
    secs = [r['seconds'] for r in done]
    print(f"{tag}: located {len(done)}/{len(out)} | own judged own+supports {ok_own}/{len(own)} | other/mixed wrongly "
          f"accepted {len(danger)}/{len(not_own)} {danger} | own-vs-other right {about_ok}/{len(done)} | invalid {invalid} | "
          f"{statistics.median(secs):.1f} s median, {sum(secs) / 60:.1f} min total")


if __name__ == '__main__':
    main()
