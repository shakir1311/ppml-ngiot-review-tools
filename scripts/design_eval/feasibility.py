#!/usr/bin/env python3
"""Lists the 45 designs with how feasible each is to execute or simulate in Phase 2, from the design-evaluation records alone.

One row per design: its own code (and licence), whether the paper lets us build it (the reader's verdict, the rule's verdict,
the effort), its data (here, to fetch, not named), its privacy mechanisms and ledger platform (evidence sheet, answer P2),
what the testbed needs for it (enclave hardware, a ZK toolchain, a Fabric network, a local EVM, GPU calls moved to the Mac),
a feasibility tier, and what it needs or what blocks it. Tiers: A ready to run (own code, open licence, data here);
B runnable once the authors allow (code without a licence); C buildable, medium effort or less, data in hand; D buildable but
harder (large effort, data or hardware to obtain, or no experiment of its own to compare against); E not feasible from the
paper. Writes Docs/DESIGN-FEASIBILITY-<date>.html (printable, portrait and landscape; never overwritten: -V2-, -V3-) and
design-evaluation/FEASIBILITY.csv.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/feasibility.py [--out <trial file>]
"""
import collections, csv, datetime, html, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, load_designs   # noqa: E402
from report import CSS   # noqa: E402
from status import load   # noqa: E402

E = html.escape
ITEM = {'C_privacy_mechanism': 'privacy mechanism', 'D_check_defence': 'update check', 'F_protocol': 'message flow', 'E_ledger': 'ledger'}
MECH = [('ZKP', 'ZKP'), ('HE', 'HE'), ('DP', 'DP'), ('LDP', 'LDP'), ('SMPC', 'SMPC'), ('secret-sharing', 'secret sharing'),
        ('masking-secure-aggregation', 'masking'), ('TEE', 'TEE'), ('pseudonyms-anonymity', 'pseudonyms')]
TIERS = {'A': 'ready to run', 'B': 'runnable once the authors allow', 'C': 'buildable, medium effort or less',
         'D': 'buildable, harder', 'E': 'not feasible from the paper'}
NO_TASK = {'N015', 'p4875', 'n1640'}
# what the October reproductions on this Mac used (experiments/zkpet/env, experiments/fl-bc-ids/env)
RUN_NOTES = {'n2721': 'EZKL proofs of the model, local EVM (Foundry Anvil); ran natively on this Mac (experiments/zkpet/env)',
             'n3378': 'arm64 Docker image, Groth16 proofs (Node, powers-of-tau files), CPU training; ran on this Mac (experiments/fl-bc-ids/env)'}      # readers: no learning task or no experiment of its own (reader.json, items A, G, I)


def sheet(d):
    return json.load(open(ROOT / 'search-ppml' / 'evidence' / 'sheets' / f"{d['id']}.json"))['answers']


def as_list(v):
    return v if isinstance(v, list) else ([v] if v else [])


def row(d):
    f = d['folder']
    ev = f / 'evidence'
    code, lic = load(ev / '11-code-verdict.json') or {}, load(ev / '12-licence.json') or {}
    reader, check = load(f / 'algorithm' / 'reader.json'), load(f / 'algorithm' / '02-quote-check.json')
    data = (load(f / 'datasets' / 'DATASETS.json') or {}).get('datasets')
    s = sheet(d)
    own = [r for r in lic.get('repositories', []) if r.get('reviewer_verdict') == 'official']
    status = code.get('code_status', '')
    if any(r.get('can_run_and_adapt') for r in own):
        code_txt = f"yes, {own[0].get('licence_spdx')}, cloned"
    elif status == 'released, no licence':
        code_txt = 'yes, no licence: authors\' permission needed'
    elif status == 'on request':
        code_txt = 'on request from the authors'
    else:
        code_txt = 'none found'
    related = [r for r in lic.get('repositories', []) if r.get('reviewer_verdict') in ('third-party tool named in the paper', "author's related code") and r.get('cloned_to')]
    if related:
        code_txt += f"; related code cloned ({len(related)})"
    # algorithm
    if own and any(r.get('can_run_and_adapt') for r in own):
        alg, effort = 'not needed: own code', 'run as published'
    elif check:
        st = check.get('statuses', {})
        weak = [ITEM[k] + (' missing' if st.get(k) == 'missing' else ' partly') for k in ITEM if st.get(k) in ('missing', 'partly')]
        alg = ('yes, with assumptions' if check['reader_verdict'] == 'viable with assumptions' else 'no') + \
              (f" ({', '.join(weak)})" if weak else '')
        effort = reader.get('effort', '–')
    else:
        alg, effort = '–', '–'
    # data
    names = as_list(s['P3']['values'].get('datasets'))
    if data:
        here = [x['name'] for x in data if str(x.get('status', '')).startswith('here')]
        need = [x['name'] for x in data if 'needs the author' in str(x.get('status', ''))]
        data_txt = ('all here' if here and not need else (f"{len(here)} here, {len(need)} to fetch or identify" if here else
                    f"{len(need)} to fetch or identify")) if (here or need) else 'none named'
    elif not names:
        data_txt, need = 'none named', []
    else:
        data_txt, need = f"{len(names)} named, not fetched (not buildable)", []
    # mechanisms, platform, testbed needs
    mechs = as_list(s['P2']['values'].get('mechanisms'))
    mech_txt = ', '.join(lbl for key, lbl in MECH if key in mechs) or 'other'
    plat = [p for p in as_list(s['P2']['values'].get('platform')) if p not in ('not-stated',)]
    plat_txt = ', '.join(p.replace('other: ', '').replace('Hyperledger-Fabric', 'Fabric') for p in plat) or 'not stated'
    needs = []
    if 'TEE' in mechs:
        needs.append('Intel SGX enclave (not on Apple silicon: Azure DCsv2/3 or a simulated enclave)')
    if 'ZKP' in mechs:
        needs.append('ZK circuit toolchain (circom/snarkjs or similar)')
    if any('Fabric' in p for p in plat):
        needs.append('Hyperledger Fabric network (Docker)')
    if any('Ethereum' in p for p in plat):
        needs.append('local EVM (Anvil or Ganache)')
    if any('FISCO' in p for p in plat):
        needs.append('FISCO-BCOS network (Docker)')
    if any('Besu' in p for p in plat):
        needs.append('Hyperledger Besu network (Docker)')
    if any(p in ('custom', 'simulated') for p in plat) or not plat:
        needs.append('ledger simulated in code')
    if d['id'] in RUN_NOTES:
        needs = [RUN_NOTES[d['id']]]
    # tier
    rd = (check or {}).get('reader_verdict')
    if own and any(r.get('can_run_and_adapt') for r in own):
        tier = 'A'
    elif status == 'released, no licence':
        tier = 'B'
    elif rd == 'viable with assumptions':
        hard = effort == 'large' or need or 'TEE' in mechs or d['id'] in NO_TASK
        tier = 'D' if hard else 'C'
    else:
        tier = 'E'
    # what it needs
    what = []
    if tier == 'A':
        what.append('reproduced on this Mac in October 2026 (experiments/); port to the Gotham + 5G testbed')
    if status == 'released, no licence':
        what.append('ask the authors for an open licence; else build from the paper')
    if status == 'on request':
        what.append('ask the authors for the code: the paper alone is not codeable')
    if tier in ('C', 'D') or (tier == 'B' and rd):
        n = len((reader or {}).get('assumptions') or [])
        what.append(f"{n} assumptions to fix (listed in its README)")
    if d['id'] in NO_TASK:
        what.append('the paper has no learning task or experiment of its own: nothing to compare a run against')
    if need:
        what.append(f"data: {', '.join(need)}")
    if tier == 'E' and status != 'on request':
        gaps = (reader or {}).get('blocking_gaps') or []
        what.append('blocked: ' + (gaps[0][:140] + ('…' if len(gaps[0]) > 140 else '')) if gaps else 'blocked: core not codeable')
    return {'id': d['id'], 'design': f"{d['first_author']} {d['year']}" + (f" · {d['acronym']}" if d['acronym'] else ''),
            'title': d['title'], 'code': code_txt, 'algorithm': alg, 'effort': effort, 'data': data_txt, 'mechanisms': mech_txt,
            'ledger': plat_txt, 'testbed_needs': '; '.join(dict.fromkeys(needs)) or '–', 'tier': tier,
            'feasibility': f"{tier}: {TIERS[tier]}", 'needs': '; '.join(what), 'folder': f.name}


def main():
    rows = sorted((row(d) for d in load_designs()), key=lambda r: (r['tier'], r['id'].lower()))
    with open(EVAL / 'FEASIBILITY.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['id', 'design', 'title', 'feasibility', 'code', 'algorithm', 'effort', 'data',
                                           'mechanisms', 'ledger', 'testbed_needs', 'needs', 'folder', 'tier'])
        w.writeheader()
        w.writerows(rows)
    c = collections.Counter(r['tier'] for r in rows)
    today = datetime.date.today().isoformat()
    out = ROOT / 'Docs' / f'DESIGN-FEASIBILITY-{today}.html'
    if '--out' in sys.argv:
        out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1])
    n = 2
    while out.exists() and '--out' not in sys.argv:
        out = ROOT / 'Docs' / f'DESIGN-FEASIBILITY-V{n}-{today}.html'
        n += 1
    cls = {'A': 'ok', 'B': 'ok', 'C': 'mid', 'D': 'mid', 'E': 'no'}
    H = [f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
         f'<title>Design feasibility</title><style>{CSS} td.t {{ white-space:nowrap; }}</style></head><body>',
         '<h1>The 45 designs: feasibility for execution and simulation</h1>',
         f'<p class="sub">Phase 2 runs the designs in Gotham with a 5G simulator. This list says, design by design, what that takes: its own code, '
         f'whether the paper lets us build it, its data, and what the testbed must provide. From the Phase 1 records, {today}; each design\'s '
         f'evidence is in <span class="mono">design-evaluation/designs/&lt;id&gt;/</span>.</p><div class="tiles">']
    H += [f'<div class="tile"><b>{c.get(t, 0)}</b><span>{t}: {TIERS[t]}</span></div>' for t in TIERS]
    H += ['</div>', '<div class="note"><b>Tiers.</b> <b>A</b> own code with an open licence and its data in hand. <b>B</b> the authors\' code exists '
          'but carries no licence; the paper is buildable as a fallback. <b>C</b> buildable from the paper with stated assumptions, medium effort '
          'or less, data in hand or public. <b>D</b> buildable, but large effort, data still to obtain, enclave hardware, or no experiment of its '
          'own to compare against. <b>E</b> the reader found a core part not codeable. For every buildable design at least one core item '
          '(privacy mechanism, update check, message flow, ledger) is only partly specified, so building it means fixing the assumptions its '
          'README lists; the author decides which to build.</div>',
          '<div class="wrap"><table><thead><tr><th>Design</th><th>Feasibility</th><th>Own code</th><th>Buildable from the paper</th>'
          '<th>Effort</th><th>Data</th><th>Privacy mechanisms</th><th>Ledger</th><th>Testbed needs</th><th>What it needs</th></tr></thead><tbody>']
    for r in rows:
        H.append(f"<tr><td><b>{E(r['id'])}</b> {E(r['design'])}<br><span class='muted'>{E(r['title'])}</span></td>"
                 f"<td class='{cls[r['tier']]}'>{E(r['feasibility'])}</td><td>{E(r['code'])}</td><td>{E(r['algorithm'])}</td>"
                 f"<td>{E(r['effort'])}</td><td>{E(r['data'])}</td><td>{E(r['mechanisms'])}</td><td>{E(r['ledger'])}</td>"
                 f"<td>{E(r['testbed_needs'])}</td><td>{E(r['needs'])}</td></tr>")
    H += ['</tbody></table></div>',
          '<p class="muted">Privacy mechanisms and ledger platform: the evidence sheets (answer P2). Effort: the readers\' estimate '
          '(small: days; medium: one to three weeks; large: more). Also in design-evaluation/FEASIBILITY.csv. '
          'Generated by scripts/design_eval/feasibility.py.</p></body></html>']
    out.write_text('\n'.join(H))
    print(out, dict(sorted(c.items())))


if __name__ == '__main__':
    main()
