#!/usr/bin/env python3
"""Propose the exclusion reasons that the author left unrecorded for two studies identified via other methods (O059,
n2438), at the author's request ("add reasons and let me review them", 5 October 2026).

Each reason is decided against the criteria (search-ppml/CRITERIA-V8-2026-10-05.md) from the study's summary, then its
page-cited notes (the author's rule: summary -> notes -> full text). The reason is written to the author's decision file
(search-ppml/AUTHOR-DECISIONS-2026-10-04.csv: code and comment) and logged with the old values in
AUTHOR-DECISIONS-LOG-2026-10-04.jsonl ("changed": proposed by Claude Code for the author's review). Where no criterion
supports the exclusion, no code is written; the comment says so. The decisions themselves are not changed.
Writes the author's review page Docs/PPML-OTHER-METHODS-REASONS-2026-10-05.html. The screening app must be closed.

Usage: python3 scripts/paper_ppml/propose_reasons.py
"""
import csv, datetime, html, json, pathlib

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
DEC, LOG = P / 'AUTHOR-DECISIONS-2026-10-04.csv', P / 'AUTHOR-DECISIONS-LOG-2026-10-04.jsonl'
OUT = ROOT / 'Docs' / 'PPML-OTHER-METHODS-REASONS-2026-10-05.html'
PROPOSALS = [
    ('100005', 'O059', 'NO-LEARNING',
     'Proposed by Claude Code for your review: EC5, the learning is incidental. A survey of security schemes for next-generation networks; '
     'machine learning appears as a tool for intrusion detection (p8), privacy as DP, HE and data minimisation for network data (p9-p10), and '
     'federated learning only as a future direction (p15); the privacy of machine learning is not its subject (IC1).',
     [('summary', 'Use in this review: ... not distributed learning, verification of updates, evaluation or any named law.'),
      ('notes p15', '"Develop efficient privacy-preserving techniques tailored for NGN applications, such as federated learning for decentralized data analysis"'),
      ('notes p8', '"Leverage machine learning algorithms to identify patterns of known and unknown attacks"')]),
    ('100006', 'n2438', '',
     'Proposed by Claude Code for your review: no criterion supports this exclusion. The study meets IC1-IC6: CKKS-encrypted updates (privacy, p6, p9), '
     'Hyperledger Fabric smart contracts that keep trust scores and quarantine low-trust devices (IC3f blockchain, IC3b malicious participants, p6, p9), '
     'IoT edge devices, evaluated. Its "Zero-Knowledge Secure Communication Layer" contains no zero-knowledge proof (so IC3e and IC3g do not apply). '
     'Either include it (with the ZK angles removed), or record your own reason.',
     [('summary', 'Despite its name, the paper has no zero-knowledge proof about an update; it shows encrypted aggregation with ledger-held trust scores only.'),
      ('notes p9', '"Hyperledger Fabric; Raft consensus" and "Trust score update, client attestation, quarantine event"'),
      ('notes p6', '"are quarantined or subjected to reduced aggregation weights. Smart-contract logic enforces tamper-resistant admission and"'),
      ('notes', 'Zero-knowledge proof about an update: not stated by the authors. Searched for: proof, prove, zk, SNARK, STARK, verifier, commitment.')]),
]


def main():
    rows = list(csv.DictReader(open(DEC, encoding='utf-8')))
    fields = list(rows[0])
    by = {r['n']: r for r in rows}
    now = datetime.datetime.now().isoformat(timespec='seconds')
    with open(LOG, 'a', encoding='utf-8') as log:
        for n, cid, code, comment, _ in PROPOSALS:
            r = by[n]
            old = {'code': r['code'], 'comment': r['comment']}
            r['code'], r['comment'] = code, comment
            log.write(json.dumps({'time': now, 'n': int(n), 'changed': "reason proposed by Claude Code for the author's review",
                                  'note': f"old {old}", **{k: r[k] for k in ('decision', 'code', 'type', 'privacy', 'focus', 'focus_parts', 'ngiot', 'comment')}},
                                 ensure_ascii=False) + '\n')
    tmp = DEC.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(DEC)
    e = html.escape
    body = ''.join(f"<h2>{e(cid)} (record {n})</h2><p><b>Proposed code:</b> {e(code or 'none — no criterion supports the exclusion')}</p><p>{e(comment)}</p><ul>"
                   + ''.join(f'<li><b>{e(w)}:</b> {e(q)}</li>' for w, q in ev) + '</ul>' for n, cid, code, comment, ev in PROPOSALS)
    if not OUT.exists():
        OUT.write_text(f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Other-methods exclusion reasons</title><style>:root{{--ink:#1b1b1b;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7}}
html,body{{background:#fff;color:var(--ink)}} body{{font:15px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:52rem;padding:24px 16px 48px}}
h1{{font-size:1.35rem;color:var(--head)}} h2{{font-size:1.1rem;color:var(--head);border-bottom:1px solid var(--line);margin-top:24px}}
.note{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band)}}
@page{{size:auto;margin:14mm}} @media print{{body{{max-width:none;padding:0}} .note,h2,ul{{break-inside:avoid}} .note{{background:#fff}}}}</style></head><body>
<h1>Two exclusions identified via other methods: proposed reasons for your review</h1>
<div class="note">Written into your decision file (code and comment), logged with the old values; your Exclude decisions are unchanged.
To change either: open the app (<code>run-screening-app.sh --filter known</code>) and edit the record. Evidence read in the order summary → notes.</div>
{body}</body></html>""", encoding='utf-8')
    print('written', OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
