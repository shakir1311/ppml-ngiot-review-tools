#!/usr/bin/env python3
"""Writes the two tables of what goes forward to Phase 2: the designs not carried forward, grouped by the reason, and the six designs carried forward with their code.

The reasons come from the records: the code verdicts and readers' verdicts of the review's 45 designs (design-evaluation/
FEASIBILITY.csv, design-evaluation/designs/<id>/), and the code declarations of the new designs (design-evaluation/new-designs/
designs/<Znn>/evidence/code-declaration-summary.json). The six carried forward are those with code that their paper declares
and a licence that lets us run and adapt it (the author, 16 November 2026: "lets keep it 2 + 4"). Writes
Docs/PHASE2-DESIGNS-<date>.html (printable; never overwritten: -V2-, -V3-) and prints both tables as Markdown.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/phase2_tables.py
"""
import csv, datetime, html, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT   # noqa: E402
from report import CSS   # noqa: E402

E = html.escape
CARRIED = {'n2721', 'n3378', 'Z01', 'Z04', 'Z06', 'Z07'}
GROUPS = [
    ('code-no-licence', 'Code exists, but carries no licence', 'The authors\' code is public but no licence lets us run or adapt it; their permission (or an added licence) would make it usable.'),
    ('code-not-declared', 'Licensed code, but the paper does not declare it', 'An author publishes the code under an open licence, but the paper itself names no code, or promises it later: nothing in the paper ties this code to it.'),
    ('no-code-buildable', 'No code; buildable from the paper only with assumptions', 'No code anywhere; the reader judged the design buildable, but at least one core part (privacy mechanism, update check, message flow, ledger) is only partly specified, so we would be filling gaps ourselves.'),
    ('no-code-unclear', 'No code; the core is too unclear to build', 'No code; no core part is missing outright, but the reader judged the core too unclear to build without inventing it.'),
    ('no-code-missing', 'No code; a core part is missing from the paper', 'No code; the paper leaves out the privacy mechanism, the update check or the message flow altogether.'),
]


def collect():
    """-> (rows, SIX): the designs not carried forward by reason {group: [(id, who, title, source, note)]}, and the six carried
    forward. Also used by the meeting deck (meeting_deck_17nov.py), so the slides and this page read the same records."""
    rows = {g[0]: [] for g in GROUPS}
    for r in csv.DictReader(open(EVAL / 'FEASIBILITY.csv')):
        if r['id'] in CARRIED:
            continue
        chk = json.load(open(next((EVAL / 'designs').glob(f"{r['id']}-*")) / 'algorithm' / '02-quote-check.json'))
        note = ''
        if r['code'].startswith('yes, no licence'):
            g = 'code-no-licence'
            note = 'also buildable from the paper with assumptions' if chk['reader_verdict'] == 'viable with assumptions' else ''
        elif chk['reader_verdict'] == 'viable with assumptions':
            g = 'no-code-buildable'
        elif chk['rule_verdict'] == 'not viable':
            g = 'no-code-missing'
        else:
            g = 'no-code-unclear'
        if r['code'].startswith('on request'):
            note = 'the paper offers its code on request'
        rows[g].append((r['id'], r['design'], r['title'], 'review (45)', note))
    for d in sorted((EVAL / 'new-designs' / 'designs').iterdir()):
        m = json.load(open(d / 'design.json'))
        if m['id'] in CARRIED:
            continue
        s = json.load(open(d / 'evidence' / 'code-declaration-summary.json'))
        who = f"{m['authors'].split(',')[0].split()[-1]} {m['year']} · {m['name']}"
        if s.get('usable', '').startswith(('no:', 'the declared code has no licence')):
            rows['code-no-licence'].append((m['id'], who, m['paper'], 'new', s.get('match', '') if m['id'] == 'Z05' else 'the paper declares this code'))
        else:
            rows['code-not-declared'].append((m['id'], who, m['paper'], 'new', s['verdict']))
    carried = []
    for r in csv.DictReader(open(EVAL / 'FEASIBILITY.csv')):
        if r['id'] in CARRIED:
            carried.append(r['id'])
    short = json.load(open(EVAL / 'new-designs' / 'SHORTLIST.json'))['shortlist']
    SIX = [
        ('n2721', 'zkPET', 'Zero-knowledge machine learning models for blockchain peer-to-peer energy trading', 'Fan et al.', 'Internet of Things (Elsevier)', 2025, 'yes',
         'Federated forecasting for peer-to-peer energy trading; zk-SNARK proofs (EZKL, Halo2/KZG) that each forecast comes from the published model, input kept private.',
         'CaixiangFan/zkpet, MIT', 'EZKL (Halo2, KZG)', 'none stated (local EVM in our run)', 'verification of inference', 'reproduced on this Mac (October 2026)'),
        ('n3378', 'FL-BC-IDS', 'FL-BC-IDS: Evidence-Native Privacy-Aware Hierarchical Federated Intrusion Detection for the Internet of Vehicles', 'Alwash et al.', 'Sensors (MDPI)', 2026, 'yes',
         'Hierarchical federated intrusion detection (vehicle, roadside unit, global); DP-XGBoost; self-sovereign identities and Merkle commitments; Groth16 proofs of membership and aggregation; evidence on Ethereum.',
         'wisamalwashYildiz/FL-BC-IDS, MIT', 'Groth16', 'Ethereum (Sepolia test network)', 'fake participants (identity), verification of aggregation', 'reproduced on this Mac (October 2026)'),
    ]
    for z, nm in (('Z01', 'PoL-BFL'), ('Z04', 'RoFL'), ('Z06', 'zkPoT'), ('Z07', 'zk-DEAP')):
        s = next(x for x in short if x['id'] == z)
        approach = {'Z01': 'Blockchain FL with proof of learning: clients prove local training (Groth16) and Solidity contracts verify the proofs on chain; registration, committee election and incentive contracts.',
                    'Z04': 'Secure aggregation in which every client proves in zero knowledge that its hidden update stays within a norm bound, so oversized (poisoning, backdoor) updates are rejected unseen.',
                    'Z06': 'Zero-knowledge proof of training: a party proves a model (logistic regression) was trained correctly on its committed data without revealing data or model.',
                    'Z07': 'Decentralised encrypted aggregation without a central server; each contribution comes with a zero-knowledge proof that it is well formed (Bulletproofs, SNARK and STARK variants); 60 malicious-participant tests.'}[z]
        code = {'Z04': 'pps-lab/rofl-project-code (MIT, stated in its README) and pps-lab/fl-analysis (MIT)', 'Z07': 'NoahApthorpe/zk-DEAP-artifact = Figshare 10.6084/m9.figshare.33411562, MIT'}.get(
            z, f"{s['repo'].replace('https://github.com/', '')}, {s['licence']}")
        venue = s['venue'] if s['peer_reviewed'] else 'arXiv preprint'
        SIX.append((z, nm, s['paper'], s['authors'].split(',')[0] + ' et al.', venue, s['year'], 'yes' if s['peer_reviewed'] else 'no',
                    approach, code, s['zk'].split(';')[0].replace(' (MPC-in-the-head style)', ''), 'none' if s['ledger'].startswith('none') else s['ledger'].split(':')[0],
                    ', '.join(s['threats']), s['testbed']))
    return rows, SIX


def main():
    rows, SIX = collect()
    # ---- Markdown for the presentation: titles, first author and year; no internal ids
    def fa_year(who):
        return who.split(' · ')[0]
    md = ['TABLE 1', '', '| Paper | First author, year | Venue | Approach | Zero-knowledge | Ledger | PhD threats addressed |', '|---|---|---|---|---|---|---|']
    for z, nm, paper, au, venue, yr, pr, appr, code, zk, led, thr, tb in SIX:
        md.append(f"| {paper} | {au.split(' et al.')[0].split()[-1]} et al., {yr} | {venue}{'' if pr == 'yes' else ' (not peer reviewed)'} | {appr} | {zk} | {led} | {thr} |")
    md += ['', 'TABLE 2', '']
    for key, title, _ in GROUPS:
        md += [f'**{title} ({len(rows[key])})**', '', '| Paper | First author, year |', '|---|---|']
        md += [f"| {t} | {fa_year(w).rsplit(' ', 1)[0]} et al., {fa_year(w).rsplit(' ', 1)[1]} |" for i, w, t, src, nt in rows[key]]
        md.append('')
    print('\n'.join(md))
    # ---- HTML
    today = datetime.date.today().isoformat()
    out = ROOT / 'Docs' / f'PHASE2-DESIGNS-{today}.html'
    n = 2
    while out.exists():
        out = ROOT / 'Docs' / f'PHASE2-DESIGNS-V{n}-{today}.html'
        n += 1
    total = sum(len(v) for v in rows.values())
    H = [f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
         f'<title>Phase 2 designs</title><style>{CSS}</style></head><body>', '<h1>Phase 2: the designs carried forward and those that are not</h1>',
         f'<p class="sub">Six designs go forward to Phase 2: those whose paper declares its code and whose licence lets us run and adapt it, two from the '
         f'review\'s 45 designs and four new ones. The other {total} designs considered are listed by the reason they are not carried forward. {today}.</p>',
         '<h2>Designs carried forward (6)</h2><div class="wrap"><table><thead><tr><th>Design</th><th>Paper</th><th>Venue, year</th><th>Peer reviewed</th>'
         '<th>Approach</th><th>Code and licence</th><th>Zero-knowledge</th><th>Ledger</th><th>PhD threats addressed</th><th>Status and testbed notes</th></tr></thead><tbody>']
    for z, nm, paper, au, venue, yr, pr, appr, code, zk, led, thr, tb in SIX:
        H.append(f"<tr><td><b>{E(nm)}</b></td><td>{E(paper)}<br><span class='muted'>{E(au)}</span></td><td>{E(venue)}, {yr}</td>"
                 f"<td>{E(pr)}</td><td>{E(appr)}</td><td class='mono'>{E(code)}</td><td>{E(zk)}</td><td>{E(led)}</td><td>{E(thr)}</td><td>{E(tb)}</td></tr>")
    H.append('</tbody></table></div>')
    H.append(f'<h2>Designs not carried forward ({total}), by reason</h2>')
    for key, title, why in GROUPS:
        items = rows[key]
        H += [f'<h3>{E(title)} ({len(items)})</h3><p class="muted">{E(why)}</p><div class="wrap"><table><thead><tr><th>First author, year</th><th>Paper</th><th>From</th><th>Note</th></tr></thead><tbody>']
        H += [f"<tr><td>{E(w.split(' · ')[0])}</td><td>{E(t)}</td><td>{E(src)}</td><td>{E(nt)}</td></tr>" for i, w, t, src, nt in items]
        H.append('</tbody></table></div>')
    H.append('<p class="muted">From the Phase 1 records (design-evaluation/) and the new designs\' code declarations (design-evaluation/new-designs/). '
             'Generated by scripts/design_eval/phase2_tables.py.</p></body></html>')
    out.write_text('\n'.join(H))
    print('\n', out, {k: len(v) for k, v in rows.items()})


if __name__ == '__main__':
    main()
