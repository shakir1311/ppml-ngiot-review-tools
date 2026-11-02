#!/usr/bin/env python3
"""Settle the conflicts between the author's screening answers and the full-text extraction records (5 October 2026).

The author asked whether the 42 conflicts listed in Docs/PPML-V29-AUTHOR-NOTES-2026-10-05.html were "taken care of and
corrected". Each conflict is decided here against the criteria as written (search-ppml/CRITERIA-V8-2026-10-05.md) and the
page evidence: the page-checked quotations of the extraction record (summary → notes → full text, as the author set it)
and, where the record did not settle it, a reading of the page (quoted below with its page; checked by script).

  IC3a poisoning: the study defends against, detects or mounts poisoning. Changed to yes only where the extraction shows
       a poisoning or backdoor attack tested; a threat only claimed is left as the author answered it.
  IC3b malicious or fake participants: Byzantine or malicious clients, Sybil or fake nodes, dishonest aggregators — the
       study detects, excludes, authenticates or tolerates them. Yes where tested; the author's yes stands where the study
       counters malicious clients, a dishonest aggregator or impersonation, or authenticates participants.
  IC3c free riding: yes where tested.
  IC3e zero-knowledge proofs: the study uses ZKPs to prove something about the learning (training, updates, aggregation,
       identity or inference).
  IC3f blockchain: the design builds on a ledger (smart contracts, consensus, on-chain records).
  IC3g ZK on blockchain: the proofs are verified on the ledger by a smart contract or the validators, not off-chain.
  Secondary studies: an angle the survey treats as a subject of its own is covered.

Outputs: search-ppml/evidence/RESOLVE-CONFLICTS-2026-10-05.csv (every decision with its basis);
         Docs/PPML-CONFLICTS-RESOLVED-2026-10-05.html (the author's review page; printable).
With --apply: the author's answers are changed in search-ppml/AUTHOR-FULLTEXT-2026-10-05.csv (each change logged with its
old value in AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl; the answers before are kept in
AUTHOR-FULLTEXT-BEFORE-CORRECTIONS-V2-2026-10-05.csv; net changes in CORRECTIONS-V2-2026-10-05.csv), and two extraction
records are corrected (search-ppml/evidence/SHEET-CORRECTIONS-2026-10-05.json keeps the old values). No Include/Exclude
decision changes. The screening app must be closed.

Usage: python3 scripts/paper_ppml/resolve_conflicts.py [--apply]
"""
import csv, datetime, html, json, pathlib, shutil, sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import check_sheets as CS                              # noqa: E402  (page matching, the same as the quotation check)

FT, LOG = P / 'AUTHOR-FULLTEXT-2026-10-05.csv', P / 'AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl'
BEFORE, NET = P / 'AUTHOR-FULLTEXT-BEFORE-CORRECTIONS-V2-2026-10-05.csv', P / 'CORRECTIONS-V2-2026-10-05.csv'
OUT_CSV, OUT_HTML = P / 'evidence' / 'RESOLVE-CONFLICTS-2026-10-05.csv', ROOT / 'Docs' / 'PPML-CONFLICTS-RESOLVED-2026-10-05.html'
SHEET_LOG = P / 'evidence' / 'SHEET-CORRECTIONS-2026-10-05.json'
ORDER = ['poisoning', 'malicious or fake participants', 'free riding', 'verification', 'zero-knowledge proofs', 'blockchain', 'ZK on blockchain']

# (id, item, author, extraction, verdict, change: (field, op, value) or None, record key for evidence, basis, [(page, quote) read])
D = [
    # ---- ZK checked on the blockchain, and what the proof shows
    ('n2912', 'ZK on blockchain', 'yes', 'not stated', 'extraction stands', ('focus_parts', 'remove', 'ZK on blockchain'), 'P4',
     'The Schnorr proof authenticates satellite nodes; "the verifier" reads the public key from the on-chain registration and checks the proof. No smart contract or validator verifies it (IC3g not met).',
     [(14, 'obtains 𝑣𝑆𝑁 from the on-chain registration relationship')]),
    ('n3910', 'ZK on blockchain', 'yes', 'no', 'extraction stands', ('focus_parts', 'remove', 'ZK on blockchain'), 'P4',
     'The federated server verifies the zk-SNARK off-chain with a public verification key; the ledger authenticates devices (IC3g not met).', []),
    ('n3910', 'what the ZK proof shows', 'bounded, identity', 'training, other', 'extraction stands', ('zk_proves', 'set', 'training; other'), 'P4',
     'The circuit enforces data origin and the training steps; no bound on the update and no identity statement is proved.', []),
    ('n2405', 'ZK on blockchain', 'yes', 'no', 'extraction stands', ('focus_parts', 'remove', 'ZK on blockchain'), 'P3',
     'Peers verify the Binius proofs; the ledger stores the Merkle root of each proof\'s commitments and "does not verify proofs or aggregate" (record P3, pp. 6, 9, 11).', []),
    ('n3378', 'zero-knowledge proofs', 'no', 'yes', 'extraction stands', ('focus_parts', 'add', 'zero-knowledge proofs'), 'P4',
     'Groth16 proofs of the masked anchor-aggregation consistency (p16) are a ZKP about the aggregation (IC3e).', []),
    ('n3378', 'ZK on blockchain', 'no', 'yes', 'extraction stands', ('focus_parts', 'add', 'ZK on blockchain'), 'P4',
     'A smart contract verifies the proofs on-chain (IC3g).', []),
    ('n3378', 'what the ZK proof shows', '—', 'aggregation', 'extraction stands', ('zk_proves', 'set', 'aggregation'), 'P4',
     'Follows from the two rows above.', []),
    ('N012', 'zero-knowledge proofs', 'no', 'yes', 'extraction stands', ('focus_parts', 'add', 'zero-knowledge proofs'), 'P4',
     'A non-interactive ZKP of the private key behind each client\'s public key at registration (identity, IC3e).', []),
    ('N012', 'ZK on blockchain', 'no', 'yes', 'extraction stands', ('focus_parts', 'add', 'ZK on blockchain'), 'P4',
     'The deployed smart contract verifies the proof (p5; registration with the proof check costs 157 970 gas, p9).', []),
    ('N012', 'what the ZK proof shows', '—', 'identity', 'extraction stands', ('zk_proves', 'set', 'identity'), 'P4', 'Follows from the rows above.', []),
    ('n3855', 'ZK on blockchain', 'no', 'yes', 'extraction stands', ('focus_parts', 'add', 'ZK on blockchain'), 'P4',
     'The smart contract validates each device\'s zkSNARK proof before Ethereum forwards it (p6).', []),
    ('n3855', 'blockchain', 'no', 'yes', 'extraction stands', ('focus_parts', 'add', 'blockchain'), 'P3',
     'Ethereum smart contracts verify proofs, sign and score local models (IC3f).', []),
    ('n3299', 'blockchain', 'no', 'yes', 'extraction stands', ('focus_parts', 'add', 'blockchain'), 'P3',
     'A Hyperledger Fabric ledger holds the identity records used to authenticate vehicles (IC3f: on-chain records are part of the design).', []),
    ('n0414', 'what the ZK proof shows', 'bounded', 'inference, other', 'neither: training', ('zk_proves', 'set', 'training'), 'P4',
     'Section 5.3 is titled "zkSNARKs-based model update verification" and the proofs show "the correctness of the local model updates" (p9). No bound is proved. The record\'s "inference" rests on a sentence relating the work to ZK proofs of inference (p12); the record is corrected to training.',
     [(9, 'zkSNARKS-based model update veriﬁcation'), (9, 'construct proofs of the correctness of the local model updates')]),
    ('n1749', 'what the ZK proof shows', 'other', 'training', 'extraction stands', ('zk_proves', 'set', 'training'), 'P4',
     'Validators use the SNARKs to "ensure that the submitted model modifications are accurate" (p3), i.e. the update came from valid training.', []),
    ('n3813', 'what the ZK proof shows', 'identity', 'bounded, other', 'neither: other', ('zk_proves', 'set', 'other'), 'P4',
     'The ZKPs concern supply-chain records: authenticity of transaction hashes (p8), sensor readings within thresholds (p9), approved checkpoints, oracle data (p11). None proves an identity or a bound on a model update; the record\'s "bounded" (sensor ranges) is corrected to other.', []),
    # ---- poisoning, malicious or fake participants, free riding (primary)
    *[(cid, 'poisoning', 'no', 'tested', 'extraction stands', ('focus_parts', 'add', 'poisoning'), 'P5', why, [])
      for cid, why in (('n2912', 'Poisoning claimed and tested (malicious-node tests; default share 20%, Table 3).'),
                       ('n3102', 'Data poisoning claimed and a success rate reported (Table 7, set-up not described).'),
                       ('N021', 'Backdoor poisoning tested on MNIST.'),
                       ('n3855', 'Poisoning claimed and tested (accuracy under the defence in figures).'),
                       ('N013', 'Poisoning tested ("approximately 71%" in the text).'),
                       ('N011', 'Bad workers adding Gaussian noise to their updates, recorded as (untargeted) poisoning, tested.'))],
    ('n3348', 'malicious or fake participants', 'no', 'tested', 'extraction stands', ('focus_parts', 'add', 'malicious or fake participants'), 'P5',
     'Byzantine (sign-flip) and Sybil participants tested (Table 5; the Sybil rows reuse the Byzantine simulations, p21).', []),
    ('n3348', 'free riding', 'no', 'tested', 'extraction stands', ('focus_parts', 'add', 'free riding'), 'P5', 'Free riding tested (Table 5).', []),
    *[(cid, 'malicious or fake participants', 'yes', 'not claimed as such', 'author stands', None, 'P5', why, [])
      for cid, why in (('N004', 'Malicious internal participants (label flipping) are detected and their models excluded: IC3b "malicious clients … detects, excludes".'),
                       ('N016', 'Semi-honest edge aggregators and a fake model in the isolating attack: IC3b "dishonest aggregators".'),
                       ('n0207', 'A malicious server and illegal users: IC3b "dishonest aggregators", authentication.'),
                       ('N008', 'Participants are authenticated by a trusted authority and miners: IC3b "authenticates".'),
                       ('n0763', 'A malicious server and impersonation of selected participants: IC3b.'),
                       ('n1640', 'Malicious clients uploading abnormal updates are rejected by range proofs and client credibility: IC3b "malicious clients … excludes".'))],
    # ---- secondary studies: an angle treated as a subject is covered
    *[(cid, item, 'no', 'subject', 'extraction stands', ('focus_parts', 'add', item), 'S4', why, [])
      for cid, item, why in (
          ('p0156', 'zero-knowledge proofs', 'A section of its own on ZKPs.'),
          ('n3837', 'poisoning', 'Three blockchain-backed poisoning defences compared; poisoning among the test scenarios.'),
          ('S026', 'poisoning', 'Sect. V-C-1: model-integrity checks against model poisoning.'),
          ('S026', 'malicious or fake participants', 'Malicious provers and verifiers; Byzantine attackers in NoV and zPROBE.'),
          ('S026', 'zero-knowledge proofs', 'The subject of the survey (ZKP-based verifiable ML).'),
          ('S021', 'poisoning', 'Subsections on data and model poisoning.'),
          ('S021', 'malicious or fake participants', 'A subsection on Byzantine attacks.'),
          ('p0013', 'verification', 'The ZKP section is on proving that gradients were computed correctly.'),
          ('p0013', 'zero-knowledge proofs', 'A section on zero-knowledge proofs of knowledge.'),
          ('S017', 'poisoning', 'Data and model poisoning among six attack types, with defences.'),
          ('S017', 'blockchain', 'A blockchain subsection of its own (mostly ledger databases).'),
          ('S007', 'poisoning', 'Data and model poisoning subsections.'),
          ('S007', 'malicious or fake participants', 'A Byzantine attacks subsection; Sybil attacks named.'),
          ('S007', 'free riding', 'A free-riding attacks subsection.'),
          ('S010', 'blockchain', 'A short subsection of its own on blockchain and smart-contract solutions (V-G); a judgement call.'),
          ('S005', 'free riding', 'Subsection VI-D on lazy nodes that copy other clients\' models (the paper says plagiarism); a judgement call.'))],
]
SHEET_FIX = [('n0414', 'P4', 'zk_shows', ['training'],
              'Corrected 5 Oct 2026 (resolve_conflicts.py): Sect. 5.3 "zkSNARKs-based model update verification"; the proofs show the correctness of the local model updates (p9). The earlier value "inference" rested on p12.'),
             ('n3813', 'P4', 'zk_shows', ['other: transaction-hash authenticity', 'other: sensor readings within thresholds',
                                           'other: set membership of locations', 'other: oracle data authenticity'],
              'Corrected 5 Oct 2026 (resolve_conflicts.py): the range proofs bound sensor readings, not model updates, so "bounded" is replaced by other.')]


def quotes(cid, key, n=2):
    s = json.loads((P / 'evidence' / 'sheets' / f'{cid}.json').read_text(encoding='utf-8'))
    return [(e['page'], e['quote']) for e in s['answers'][key].get('evidence', [])[:n]]


def check_reading(cid, page, quote):
    f = CS.folder_of(cid) / 'text' / 'pages' / f'page_{page:04d}.txt'
    return CS.found(quote, f.read_text(encoding='utf-8', errors='ignore'))


def apply():
    rows = list(csv.DictReader(open(FT, encoding='utf-8')))
    fields = list(rows[0])
    if not BEFORE.exists():
        shutil.copy(FT, BEFORE)
    before = {r['n']: r for r in csv.DictReader(open(BEFORE, encoding='utf-8'))}
    fin = {r['corpus_id']: r['n'] for r in csv.DictReader(open(P / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8'))}
    by_n = {r['n']: r for r in rows}
    now = datetime.datetime.now().isoformat(timespec='seconds')
    with open(LOG, 'a', encoding='utf-8') as log:
        for cid, item, a, x, verdict, ch, key, why, read in D:
            if not ch:
                continue
            r = by_n[fin[cid]]
            field, op, val = ch
            old = r[field]
            if field == 'focus_parts':
                parts = [p for p in old.split('; ') if p]
                parts = [p for p in parts if p != val] if op == 'remove' else parts + ([val] if val not in parts else [])
                new = '; '.join(p for p in ORDER if p in parts)
                r['focus'] = 'yes' if new else r['focus']
            else:
                new = val
            if new == old:
                continue
            r[field] = new
            log.write(json.dumps({'time': now, 'n': int(r['n']), 'changed': "conflict settled by Claude Code at the author's request",
                                  'note': f'{field}: {old!r} -> {new!r}; {why}',
                                  **{k: r[k] for k in ('decision', 'code', 'type', 'privacy', 'focus', 'focus_parts', 'zk_proves', 'ngiot', 'comment')}},
                                 ensure_ascii=False) + '\n')
    tmp = FT.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(FT)
    ids = {n: cid for cid, n in fin.items()}
    net = [{'id': ids[n], 'n': n, 'field': f, 'old': before[n][f], 'new': by_n[n][f]}
           for n in by_n if n in ids for f in ('focus_parts', 'zk_proves') if before[n][f] != by_n[n][f]]
    with open(NET, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['id', 'n', 'field', 'old', 'new'])
        w.writeheader()
        w.writerows(net)
    done = json.loads(SHEET_LOG.read_text(encoding='utf-8')) if SHEET_LOG.exists() else []
    for cid, key, field, new, note in SHEET_FIX:
        f = P / 'evidence' / 'sheets' / f'{cid}.json'
        s = json.loads(f.read_text(encoding='utf-8'))
        old = s['answers'][key]['values'].get(field)
        if old == new:
            continue
        s['answers'][key]['values'][field] = new
        if cid == 'n0414':
            ev = s['answers'][key]['evidence']
            if not any('model update veri' in e['quote'] for e in ev):
                ev.insert(0, {'page': 9, 'quote': 'zkSNARKS-based model update veriﬁcation'})
        s['remarks'] = (s.get('remarks', '') + ' ' + note).strip()
        f.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding='utf-8')
        done.append({'time': now, 'id': cid, 'key': key, 'field': field, 'old': old, 'new': new, 'why': note})
    SHEET_LOG.write_text(json.dumps(done, indent=1, ensure_ascii=False), encoding='utf-8')
    print(len(net), 'net answer changes ->', NET.name, '|', len(SHEET_FIX), 'extraction records corrected')


def main():
    out, problems = [], []
    for cid, item, a, x, verdict, ch, key, why, read in D:
        for pg, q in read:
            if not check_reading(cid, pg, q):
                problems.append(f'{cid} p{pg}: reading quote not found')
        ev = ' · '.join(f'p{p}: "{q}"' for p, q in (read or quotes(cid, key)))
        out.append({'id': cid, 'item': item, 'author': a, 'extraction': x, 'verdict': verdict,
                    'change': (f'{ch[1]} {ch[2]!r} ({ch[0]})' if ch else 'none'), 'basis': why, 'evidence': ev,
                    'level': 'page read' if read else f'extraction record {key} (page-checked)'})
    if problems:
        sys.exit('\n'.join(problems))
    with open(OUT_CSV, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    e = html.escape
    changes = sum(1 for r in out if r['change'] != 'none')
    body = ''.join(f"<tr><td>{e(r['id'])}</td><td>{e(r['item'])}</td><td>{e(r['author'])}</td><td>{e(r['extraction'])}</td>"
                   f"<td><b>{e(r['verdict'])}</b></td><td>{e(r['change'])}</td><td>{e(r['basis'])}</td><td class='ev'>{e(r['evidence'])} <i>({e(r['level'])})</i></td></tr>" for r in out)
    if not OUT_HTML.exists():
        OUT_HTML.write_text(f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPML conflicts settled</title><style>
:root{{--ink:#1b1b1b;--muted:#555;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7}}
html,body{{background:#fff;color:var(--ink)}} body{{font:14px/1.45 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:76rem;padding:24px 16px 48px}}
h1{{font-size:1.4rem;color:var(--head);margin:0 0 4px}} .muted{{color:var(--muted)}} .note{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band);margin:10px 0}}
table{{border-collapse:collapse;width:100%;font-size:.8rem}} th,td{{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}} th{{background:var(--band)}} td.ev{{font-size:.74rem;color:#333}}
@page{{size:auto;margin:12mm}} @media print{{body{{max-width:none;padding:0;font-size:9pt}} table{{font-size:7.5pt}} tr,.note{{break-inside:avoid}} th,.note{{background:#fff}}}}
</style></head><body>
<h1>PPML review: the conflicts between your screening answers and the extraction, settled</h1>
<p class="muted">5 October 2026 · scripts/paper_ppml/resolve_conflicts.py · criteria search-ppml/CRITERIA-V8-2026-10-05.md · record search-ppml/evidence/RESOLVE-CONFLICTS-2026-10-05.csv</p>
<div class="note"><b>{len(out)} decisions</b>: {changes} change an answer, {len(out) - changes} confirm your answer. The earlier list counted 42 conflicts; six of
them were not conflicts, because criterion IC3b also covers dishonest aggregators, malicious clients and authentication, and two further
omissions were found (blockchain not ticked for n3299 and n3855). A threat that a study only claims is left as you answered it; a tick is added
where the study tests it. Two extraction records are corrected as well (n0414, n3813: what the proof shows). No Include/Exclude decision changes.
To undo any change: open the full-text app (<code>run-screening-app.sh --fulltext</code>) and change the answer back; it is saved at once.
Your answers before these changes: search-ppml/AUTHOR-FULLTEXT-BEFORE-CORRECTIONS-V2-2026-10-05.csv.</div>
<table><tr><th>Id</th><th>Item</th><th>You</th><th>Extraction</th><th>Verdict</th><th>Change</th><th>Basis (criteria V8)</th><th>Evidence</th></tr>{body}</table>
</body></html>""", encoding='utf-8')
    print(len(out), 'decisions,', changes, 'changes ->', OUT_CSV.name, '|', OUT_HTML.name)
    if '--apply' in sys.argv:
        apply()


if __name__ == '__main__':
    main()
