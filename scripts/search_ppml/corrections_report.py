#!/usr/bin/env python3
"""The author's review page for the corrections applied on 5 October 2026 (apply_corrections.py).

Lists every correction (study, answer, old -> new, why) with the evidence the decision check found for it
(search-ppml/DECISION-CHECK-2026-10-05.csv), and the check after the corrections (DECISION-CHECK-V2-2026-10-05.csv).

Output: Docs/PPML-REVIEW-CORRECTIONS-2026-10-05.html (printable)

Usage: python3 scripts/search_ppml/corrections_report.py
"""
import csv, html, pathlib, sys
from collections import Counter, defaultdict

csv.field_size_limit(10 ** 9)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402

P, ROOT = M.P, M.ROOT
OUT = ROOT / 'Docs' / 'PPML-REVIEW-CORRECTIONS-V2-2026-10-05.html'   # version 1 (first corrections) is kept
e = html.escape
FIELD = {'privacy': 'Privacy (question 2)', 'ngiot': 'NG-IoT setting (question 4)', 'focus_parts': 'PhD angles (question 3)',
         'focus': 'PhD focus (follows the angles)', 'zk_proves': 'What the ZK proof shows'}
CHECK_OF = {'privacy': 'privacy (own mechanism / treated)', 'ngiot': 'NG-IoT setting'}


def main():
    corr = list(csv.DictReader(open(P / 'CORRECTIONS-2026-10-05.csv', encoding='utf-8')))
    v1 = defaultdict(list)
    for c in csv.DictReader(open(P / 'DECISION-CHECK-2026-10-05.csv', encoding='utf-8')):
        v1[c['n']].append(c)
    v2 = list(csv.DictReader(open(P / 'VERIFY-DECISIONS-2026-10-05.csv', encoding='utf-8')))
    st2 = Counter(c['status'] for c in v2)
    ver = defaultdict(list)
    for c in v2:
        ver[c['n']].append(c)

    def evidence(c):
        rows = ver.get(c['n'], [])
        if c['field'] in CHECK_OF:
            hits = [r for r in rows if r['check'].startswith(CHECK_OF[c['field']].split(' (')[0])]
        elif c['field'] == 'zk_proves':
            hits = [r for r in rows if r['check'].startswith('ZK proof shows')]
        else:
            hits = [r for r in rows if r['check'].startswith('angle') or r['check'].startswith('at least one')]
        return ' · '.join(f"{r['check']} [{r['status']}, {r['level']}]: {r['evidence'][:220]}" for r in hits if r['evidence'])[:700]

    body = ''.join(
        f"<tr><td>{e(c['id'])}</td><td class='t'>{e(c['title'][:80])}</td><td>{e(FIELD.get(c['field'], c['field']))}</td>"
        f"<td>{e(c['old'] or '—')}</td><td><b>{e(c['new'])}</b></td><td>{e(c['why'])}</td><td class='ev'>{e(evidence(c))}</td></tr>"
        for c in corr)
    remaining = ''.join(f"<li>{e(c['id'])} — {e(c['check'])} ({c['status']}): {e(c['evidence'][:220])}</li>"
                        for c in v2 if c['status'] != 'VERIFIED')
    by_field = Counter(FIELD.get(c['field'], c['field']) for c in corr)
    doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPML review: corrections</title><style>
:root{{--ink:#1b1b1b;--muted:#555;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7}}
html,body{{background:#fff;color:var(--ink)}} body{{font:14px/1.45 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:74rem;padding:24px 16px 48px}}
h1{{font-size:1.4rem;color:var(--head);margin:0 0 4px}} h2{{font-size:1.12rem;color:var(--head);margin:24px 0 8px;border-bottom:1px solid var(--line)}}
.muted{{color:var(--muted)}} .note{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band)}}
table{{border-collapse:collapse;width:100%;font-size:.82rem}} th,td{{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}}
th{{background:var(--band)}} td.t{{min-width:10rem}} td.ev{{font-size:.76rem;color:#333}}
@page{{size:auto;margin:12mm}} @media print{{body{{max-width:none;padding:0;font-size:9pt}} table{{font-size:7.5pt}} tr,.note{{break-inside:avoid}} th,.note{{background:#fff}}}}
</style></head><body>
<h1>PPML review: corrections to your full-text answers, verified (version 2)</h1>
<p class="muted">5 October 2026 · applied by Claude Code at your request (scripts/search_ppml/apply_corrections.py) · every change is logged with
its old value (search-ppml/AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl) · no Include/Exclude decision was changed</p>
<div class="note"><b>{len(corr)} corrections</b> — {'; '.join(f'{k}: {v}' for k, v in by_field.items())}. After them, the decision check
after them, every answer of the 54 studies is verified: {st2['VERIFIED']} of {sum(st2.values())} (evidence in the summary, the notes, the
title, the abstract or the full text, or read by Claude Code at the page given; Docs/PPML-REVIEW-VERIFIED-DECISIONS-2026-10-05.html). To undo one: open the full-text app
(<code>run-screening-app.sh --fulltext</code>), find the study by its number, and change the answer back; your change is saved at once.</div>
<h2>1. The corrections</h2>
<table><tr><th>Id</th><th>Study</th><th>Answer</th><th>Was</th><th>Now</th><th>Why</th><th>Conclusive evidence (status, where: S summary, N notes, T title, A abstract, F full text, R read)</th></tr>{body}</table>
<h2>2. Not verified after the corrections</h2>
<ul>{remaining or '<li>none</li>'}</ul>
<p class="muted">NG-IoT is read as you set it on 5 October: IoT with 5G, edge or another next-generation enabler is NG-IoT; a strict
"stated focus" is not required.</p>
</body></html>"""
    OUT.write_text(doc, encoding='utf-8')
    print(OUT.relative_to(ROOT), '|', len(corr), 'corrections |', dict(st2))


if __name__ == '__main__':
    main()
