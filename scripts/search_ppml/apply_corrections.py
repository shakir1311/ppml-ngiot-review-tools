#!/usr/bin/env python3
"""Apply the corrections of the decision check to the author's full-text answers, at the author's request (5 October 2026).

The author: "Go ahead and do the corrections for me and then show me the suggested corrections for my review". The
corrections follow search-ppml/DECISION-CHECK-2026-10-05.csv (check_decisions.py): each one is an answer the check
questioned, set to what the study's summary, notes or full text support. Every change is written to
search-ppml/AUTHOR-FULLTEXT-2026-10-05.csv, logged with its old value in AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl
("changed": "correction by Claude Code at the author's request"), and listed in search-ppml/CORRECTIONS-2026-10-05.csv
(the net changes against AUTHOR-FULLTEXT-BEFORE-CORRECTIONS-2026-10-05.csv, the author's answers before) for the author's review; the author can undo any of them in the full-text app. No decision (Include/Exclude) is changed.

Usage: python3 scripts/search_ppml/apply_corrections.py      (the screening app must be closed)
"""
import csv, datetime, json, pathlib, sys

csv.field_size_limit(10 ** 9)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402

P = M.P
FT = P / 'AUTHOR-FULLTEXT-2026-10-05.csv'
LOG = P / 'AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl'
OUT = P / 'CORRECTIONS-2026-10-05.csv'
BEFORE = P / 'AUTHOR-FULLTEXT-BEFORE-CORRECTIONS-2026-10-05.csv'   # the author's answers before any correction (kept)

# (corpus id, field, new value, why) — the evidence for each is in DECISION-CHECK-2026-10-05.csv
CORRECTIONS = [
    # privacy left at Can't tell; the texts show the privacy treated or the mechanism used
    *[(cid, 'privacy', 'yes', "Can't tell left at full text; the summary or notes name the privacy techniques treated")
      for cid in ('S028', 'S026', 'S021', 'p1162', 'S014', 'S005', 'n3837', 'O043')],
    # NG-IoT left at Can't tell, or No although included; the texts name the setting
    *[(cid, 'ngiot', 'yes', "Can't tell left at full text; the summary or notes name the NG-IoT setting")
      for cid in ('p0086', 'S016', 'n3855', 'N013', 'N014', 'N016', 'n2721', 'n2723', 'n3813')],
    ('S018', 'ngiot', 'yes', 'No although included; the summary names the setting'),
    ('N021', 'ngiot', 'yes', 'No although included; the summary names the setting (industrial IoT)'),
    # S028: included with no angle; its summary describes defences against backdoors and Sybil clients
    ('S028', 'focus_parts', 'poisoning; malicious or fake participants',
     'Included with no angle ticked; the summary names pruning against backdoors and learning-rate control against Sybil clients'),
    ('S028', 'focus', 'yes', 'follows from the angles ticked'),
    # n0207: ZK proofs are not checked on a chain
    ('n0207', 'focus_parts', lambda old: '; '.join(x for x in old.split('; ') if x and x != 'ZK on blockchain'),
     'ZK checked on-chain removed: the paper runs its ZKP scheme without the blockchain (p7)'),
    # what the ZK proof shows
    ('n3299', 'zk_proves', 'identity', 'inference removed: the Groth16 proof shows credential membership only'),
    ('N015', 'zk_proves', 'bounded', 'identity and inference removed: the proofs are norm bounds on the updates'),
    ('n0763', 'zk_proves', 'other', 'training replaced by other: the proof shows knowledge of the hidden training loss'),
    ('n1640', 'zk_proves', 'bounded', 'identity removed: a Bulletproofs range proof on the committed gradient'),
    ('n2405', 'zk_proves', 'training', 'identity replaced by training: the Binius proof attests the encoded gradient (legitimate training)'),
    ('n2723', 'zk_proves', 'training', 'identity replaced by training: zk-SNARK proofs of update correctness'),
    ('n3348', 'zk_proves', 'bounded', 'identity and aggregation removed: client signatures are not a ZK proof, and the paper says the aggregation is not proven (p6: "verifiable aggregation proofs could further enhance accountability"); the norm proof stays'),
]


def main():
    rows = list(csv.DictReader(open(FT, encoding='utf-8')))
    fields = list(rows[0])
    final = {r['corpus_id']: r['n'] for r in csv.DictReader(open(P / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8'))}
    by_n = {r['n']: r for r in rows}
    before = {r['n']: r for r in csv.DictReader(open(BEFORE, encoding='utf-8'))}
    why_of = {(final[cid], field): why for cid, field, _, why in CORRECTIONS}
    ids = {n: cid for cid, n in final.items()}
    now = datetime.datetime.now().isoformat(timespec='seconds')
    done = []
    with open(LOG, 'a', encoding='utf-8') as log:
        for cid, field, new, why in CORRECTIONS:
            r = by_n[final[cid]]
            old = r[field]
            if callable(new):                                  # a change relative to the author's own answer
                new = new(before[r['n']][field])
            if old == new:
                continue
            r[field] = new
            log.write(json.dumps({'time': now, 'n': int(r['n']), 'changed': "correction by Claude Code at the author's request",
                                  'note': f'{field}: {old!r} -> {new!r}; {why}',
                                  **{k: r[k] for k in ('decision', 'code', 'type', 'privacy', 'focus', 'focus_parts', 'zk_proves', 'ngiot', 'comment')}},
                                 ensure_ascii=False) + '\n')
    tmp = FT.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(FT)
    done = [{'id': ids[n], 'n': n, 'title': by_n[n]['title'], 'field': f, 'old': before[n][f], 'new': by_n[n][f], 'why': why_of.get((n, f), '')}
            for n in by_n for f in ('privacy', 'ngiot', 'focus', 'focus_parts', 'zk_proves') if before[n][f] != by_n[n][f]]
    with open(OUT, 'w', encoding='utf-8', newline='') as fh:          # the net changes against the author's answers before
        w = csv.DictWriter(fh, fieldnames=['id', 'n', 'title', 'field', 'old', 'new', 'why'])
        w.writeheader()
        w.writerows(done)
    print(len(done), 'corrections applied ->', OUT.name)


if __name__ == '__main__':
    main()
