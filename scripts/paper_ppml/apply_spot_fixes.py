#!/usr/bin/env python3
"""Apply the corrections found by the independent verification of six extraction records (5 October 2026;
search-ppml/evidence/checks/spot-output-{1,2}.jsonl, all 'minor', no 'disagree'). Old and new values are appended to
search-ppml/evidence/SHEET-CORRECTIONS-2026-10-05.json; n0414's 'what the proof shows' is set in the author's
full-text answers as well (logged in AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl). The screening app must be closed.

Usage: python3 scripts/paper_ppml/apply_spot_fixes.py
"""
import csv, datetime, json, pathlib

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
SH, LOG = P / 'evidence' / 'sheets', P / 'evidence' / 'SHEET-CORRECTIONS-2026-10-05.json'
FIX = [
    ('S018', 'S7', 'answer', lambda a: a.replace('; poisoning-resilient defences.', '.'),
     'verification p7: "poisoning-resilient defences" comes from the background list of general FL challenges (Sec. 4.2.3), not the review\'s own open issues'),
    ('S018', 'S7', ('values', 'open_issues'), lambda v: [x for x in v if x != 'poisoning-resilient defences'], 'as above'),
    ('n0763', 'P4', 'answer', lambda a: a.replace('the server receives them in the clear and checks only a hash tag of the encrypted model, against impersonation.',
                                                  'how they are protected is not specified, and the server checks only a hash tag of the plain model with the participant\'s public key, H(M, pk), against impersonation.'),
     'verification p11-12: the tag is a hash of the plain model with the public key; protection of the gradients is not specified'),
    ('n0763', 'P6', 'answer', lambda a: a.replace('Loss-based selection gives higher accuracy and faster, steadier convergence than random selection (values in Figs. 4 and 5 only);',
                                                  'Loss-based selection gives higher accuracy and faster, steadier convergence than random selection on MNIST, while on FashionMNIST the authors say the difference is not so obvious (values in Figs. 4 and 5 only);'),
     'verification p14: the faster convergence holds for MNIST only'),
    ('N012', 'P2', 'answer', lambda a: a.replace('Cost: ciphertext expansion raises communication to about 145 kB per iteration; encryption takes 1.09 s or 0.86 s per client with 3 clients;',
                                                 'Cost: ciphertext expansion raises communication to about 145 kB per iteration, calculated for c = 4 and l = 9 (not measured); encryption takes 1.09 s or 0.86 s per client with 3 clients, for packs of l = 3 and l = 4 gradient signs;'),
     'verification p8-9: the two times differ by pack length; the 145 kB is calculated, not measured'),
    ('N012', 'P6', 'answer', lambda a: a.replace('Per client with 3 clients: registration 0.03 s, encryption 1.09/0.86 s, aggregation 0.23/0.16 s; about 145 kB per iteration.',
                                                 'Per client with 3 clients: registration 0.03 s; encryption 1.09/0.86 s and aggregation 0.23/0.16 s for packs of l = 3/l = 4 gradient signs; about 145 kB per iteration, calculated.'),
     'as above'),
    ('n0414', 'P4', ('values', 'zk_shows'), lambda v: ['training', 'inference'],
     'verification p9-p13: the authors claim correctness of the local updates (p9), while Eq. 6-9 (p10) prove the SVM decision function on a new example, which the authors relate to inference (p12); both values recorded'),
]


def main():
    done = json.loads(LOG.read_text(encoding='utf-8')) if LOG.exists() else []
    now = datetime.datetime.now().isoformat(timespec='seconds')
    for cid, key, field, fn, why in FIX:
        f = SH / f'{cid}.json'
        s = json.loads(f.read_text(encoding='utf-8'))
        a = s['answers'][key]
        if isinstance(field, tuple):
            old = a[field[0]][field[1]]
            new = fn(old)
            a[field[0]][field[1]] = new
        else:
            old = a[field]
            new = fn(old)
            a[field] = new
        if old == new:
            print('unchanged:', cid, key, field)
            continue
        s['remarks'] = (s.get('remarks', '') + f' Corrected 5 Oct 2026 after independent verification ({key}): {why}.').strip()
        f.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding='utf-8')
        done.append({'time': now, 'id': cid, 'key': key, 'field': str(field), 'old': old, 'new': new, 'why': why})
    LOG.write_text(json.dumps(done, indent=1, ensure_ascii=False), encoding='utf-8')
    ft = P / 'AUTHOR-FULLTEXT-2026-10-05.csv'
    rows = list(csv.DictReader(open(ft, encoding='utf-8')))
    for r in rows:
        if r.get('in_corpus') == 'n0414' or r['n'] == '6056':
            if r['zk_proves'] != 'training; inference':
                with open(P / 'AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl', 'a', encoding='utf-8') as log:
                    log.write(json.dumps({'time': now, 'n': int(r['n']), 'changed': "correction by Claude Code after independent verification",
                                          'note': f"zk_proves: {r['zk_proves']!r} -> 'training; inference'"}, ensure_ascii=False) + '\n')
                r['zk_proves'] = 'training; inference'
    with open(ft, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(FIX), 'corrections applied')


if __name__ == '__main__':
    main()
