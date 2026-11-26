#!/usr/bin/env python3
"""Writes the report of the Phase 2 design study: the six designs compared, their datasets and credibility, their runs and set-ups as the baseline to follow, and the qualitative analysis of the 48 not carried forward.

Reads the study's records only: design-evaluation/study/CARDS.json (study_cards.py), datasets/DATASETS.json (study_datasets.py),
datasets/CREDIBILITY.json, and each design's study/reader.json and 02-quote-check.json. Every count is computed here from those
records; the per-design baseline approach (BASELINE) is the reviewer's reading of the readers' findings and says so. Writes
Docs/PHASE2-DESIGN-STUDY-<date>.html (printable in portrait and landscape; never overwritten: -V2-, -V3-).

Usage: python3 scripts/design_eval/study_report.py [trial-output.html]
"""
import collections, datetime, html, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import EVAL, ROOT   # noqa: E402
from report import CSS   # noqa: E402
from study_packets import QUALITATIVE, SIX, resolve   # noqa: E402

E = lambda x: html.escape(str(x))
STUDY = EVAL / 'study'
ORDER = ['n2721', 'n3378', 'Z01', 'Z04', 'Z06', 'Z07']
EXTRA_CSS = """
table.long, table.long tr { break-inside:auto; } .grade-Strong { color:var(--ok); font-weight:600; } .grade-Adequate { color:var(--mid); font-weight:600; }
.grade-Weak { color:var(--no); font-weight:600; } .card { border:1px solid var(--line); border-radius:8px; padding:10px 14px; margin:12px 0; }
.card h3 { margin:2px 0 6px; font-size:1.02rem; } h3 { font-size:1.02rem; margin:18px 0 6px; } ol { margin:6px 0 6px 22px; padding:0; }
td.n { text-align:right; white-space:nowrap; } .flag { font-weight:600; }
@media print { .card { break-inside:auto; } h3 { break-after:avoid; } }
"""
BASELINE = {   # the reviewer's reading of the readers' records (study/reader.json): how each baseline can follow the paper
    'n2721': ('yes (ran natively in October 2026)',
              'Follow the paper for the sites, clusters and model; the released code has no clustering and no proof aggregation, so those '
              'parts follow the paper\'s description and are marked as ours. Repetitions are not stated: five seeds.'),
    'n3378': ('yes, with an arm64 build (Ray failed under Rosetta in October)',
              'Follow the paper\'s run types (compact, stress, long-round) and its ten seeds (42 to 51) where it used them; seed 42 elsewhere, '
              'with five seeds added and marked as ours. The paper\'s public test network (Sepolia) needs a funded wallet: a local chain '
              'stands in, recorded as a deviation.'),
    'Z01': ('no: the formal runs need Linux, CUDA and two GPUs',
            'Needs a GPU machine for the paper\'s scale; on our hardware only a reduced run on the CPU backend, stated as such. The paper '
            'states no repetitions; the code uses three seeds, which the baseline follows (the code\'s value where the paper is silent).'),
    'Z04': ('no: x86 with AVX2 or AVX-512, Python 3.7, TensorFlow 2.1 and a GPU',
            'Needs an x86 Linux machine. The prototype runs with zero blinding and without Shamir sharing or key agreement, so its '
            'privacy part is not the paper\'s: the baseline measures what the code does and says so. Microbenchmarks over four runs, '
            'as the paper; five seeds elsewhere.'),
    'Z06': ('partly: the headline size needed a 512 GB machine; Rust nightly',
            'A cost baseline at sizes our hardware holds, of the paper\'s shape, stated as smaller. The code leaves zero-knowledge '
            'masking and some verifier checks unfinished, so the baseline measures the unfinished proof and says so.'),
    'Z07': ('yes (arm64 macOS; no GPU needed)',
            'Follow the paper: every operation timed 30 times; the 60 attack tests as shipped. The run script covers up to 100 '
            'participants and one threshold; the sweep to 500 is run separately, and the cap on recoverable sums is recorded.'),
}
FAMILIES = [   # families of design, by the privacy mechanism and the check (a design can sit in several)
    ('Zero-knowledge proof about each update or its training', lambda c: bool(set(c.get('zk_shows') or []) & {'training', 'bounded', 'similarity'})),
    ('Zero-knowledge proof of aggregation or inference', lambda c: bool(set(c.get('zk_shows') or []) & {'aggregation', 'inference'})),
    ('Zero-knowledge proof of identity', lambda c: 'identity' in (c.get('zk_shows') or [])),
    ('Homomorphic encryption of updates', lambda c: 'HE' in (c.get('mechanisms') or [])),
    ('Secret sharing, SMPC or masking', lambda c: bool(set(c.get('mechanisms') or []) & {'secret-sharing', 'SMPC', 'masking-secure-aggregation'})),
    ('Noise: differential privacy (DP or LDP)', lambda c: bool(set(c.get('mechanisms') or []) & {'DP', 'LDP'})),
    ('Trusted hardware (TEE)', lambda c: 'TEE' in (c.get('mechanisms') or []) or 'enclave-TEE' in (c.get('trusted') or [])),
    ('Pseudonymous or anonymous participation', lambda c: 'pseudonyms-anonymity' in (c.get('mechanisms') or [])),
    ('Validation by test accuracy (committee or server scores updates)', lambda c: 'test-accuracy-quality' in (c.get('checked') or [])),
    ('Reputation or contribution scoring', lambda c: 'contribution-reputation' in (c.get('checked') or [])),
]
BIAS = [   # (group, label, predicate) for the representativeness check
    ('Privacy', 'Zero-knowledge proofs', lambda c: c.get('zk_used') is True),
    ('Privacy', 'Homomorphic encryption', lambda c: 'HE' in (c.get('mechanisms') or [])),
    ('Privacy', 'Secret sharing, SMPC or masking', FAMILIES[4][1]),
    ('Privacy', 'Differential privacy (DP or LDP)', FAMILIES[5][1]),
    ('Privacy', 'Trusted hardware (TEE)', FAMILIES[6][1]),
    ('Privacy', 'Pseudonyms or anonymity', FAMILIES[7][1]),
    ('Ledger', 'A ledger in the design', lambda c: c.get('ledger') != 'none'),
    ('Ledger', 'Consortium or permissioned ledger', lambda c: c.get('ledger') == 'consortium-permissioned' or 'consortium-permissioned' in (c.get('ledger') or [])),
    ('Ledger', 'Ethereum', lambda c: 'Ethereum' in (c.get('platform') or [])),
    ('Ledger', 'Hyperledger Fabric', lambda c: 'Hyperledger-Fabric' in (c.get('platform') or [])),
    ('Checking', 'Checks identity or membership', lambda c: 'identity-membership' in (c.get('checked') or [])),
    ('Checking', 'Scores contribution or reputation', FAMILIES[9][1]),
    ('Checking', 'Validates by test accuracy', FAMILIES[8][1]),
    ('Checking', 'Checks a norm bound', lambda c: 'norm-bound' in (c.get('checked') or [])),
    ('Checking', 'Checks correct training', lambda c: 'correct-training' in (c.get('checked') or [])),
    ('Checking', 'Checks correct aggregation', lambda c: 'correct-aggregation' in (c.get('checked') or [])),
    ('Checking', 'The checker sees no individual update', lambda c: c.get('checker_sees_update') == 'no'),
    ('Trust', 'Trusts the server or aggregator', lambda c: 'server-aggregator' in (c.get('trusted') or [])),
    ('Trust', 'Trusts an authority or key centre', lambda c: 'trusted-authority-key-centre' in (c.get('trusted') or [])),
    ('Trust', 'Relies on a trusted set-up', lambda c: 'trusted-setup' in (c.get('trusted') or [])),
    ('Setting', 'A named IoT domain (IIoT, IoMT, IoV, smart grid, city, UAV, maritime, supply chain)',
     lambda c: bool(set(c.get('settings') or []) - {'IoT-general'} - {x for x in (c.get('settings') or []) if str(x).startswith('other')})),
    ('Evaluation', 'Real devices or emulation', lambda c: bool(set(c.get('environment') or []) & {'real-devices', 'emulation'})),
    ('Evaluation', 'Tests poisoning or backdoors', lambda c: c['phd_threats']['poisoning']['tested']),
    ('Evaluation', 'Tests malicious or fake participants', lambda c: c['phd_threats']['malicious_fake']['tested']),
    ('Evaluation', 'Tests free riding', lambda c: c['phd_threats']['free_riding']['tested']),
    ('Conditions', 'C1: a cost measured on device-class hardware', lambda c: c['conditions']['C1']),
    ('Conditions', 'C2: no checking or aggregating party sees an individual update', lambda c: c['conditions']['C2']),
    ('Conditions', 'C3: tested against poisoning, malicious or fake participants, or free riding', lambda c: c['conditions']['C3']),
]


def tags(v, n=60):
    vs = v if isinstance(v, list) else ([] if v in (None, '') else [v])
    out = [('other: ' + str(x)[6:].strip()[:n] + ('…' if len(str(x)) > n + 6 else '')) if str(x).startswith('other') else str(x) for x in vs]
    return ', '.join(out) if out else '–'


def short(v):
    """tags with every 'other: …' counted as 'other', for the compact table of the 48"""
    vs = v if isinstance(v, list) else ([] if v in (None, '') else [v])
    out = list(dict.fromkeys('other' if str(x).startswith('other') else str(x) for x in vs))
    return ', '.join(out) if out else '–'


def ul(items):
    items = [x for x in (items or []) if str(x).strip()]
    return '<ul>' + ''.join(f'<li>{E(x)}</li>' for x in items) + '</ul>' if items else '<p class="muted">–</p>'


def pct(k, n):
    return f'{k}/{n} ({round(100 * k / n)}%)'


def main():
    cards = {c['id']: c for c in json.load(open(STUDY / 'CARDS.json'))['cards']}
    six = [cards[i] for i in ORDER]
    rest = sorted((c for c in cards.values() if c['status'] != 'carried forward'), key=lambda c: (c['group'], c['who']))
    readers = {i: json.load(open(resolve(i)['folder'] / 'study' / 'reader.json')) for i in SIX + QUALITATIVE}
    qc = {i: json.load(open(resolve(i)['folder'] / 'study' / '02-quote-check.json')) for i in SIX + QUALITATIVE}
    nq, nf = sum(q['quotations'] for q in qc.values()), sum(q['found'] for q in qc.values())
    ds = json.load(open(STUDY / 'datasets' / 'DATASETS.json'))['datasets']
    cred = json.load(open(STUDY / 'datasets' / 'CREDIBILITY.json'))
    groups = {c['group']: c['group_label'] for c in cards.values()}
    today = datetime.date.today().isoformat()
    H = [f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
         f'<title>Phase 2 design study</title><style>{CSS}{EXTRA_CSS}</style></head><body>',
         '<h1>Phase 2 design study: the six designs, their data and set-ups, and the 48 not carried forward</h1>',
         f'<p class="sub">The five actions of the supervision meeting of 17 November 2026, on all 54 designs considered for Phase 2. '
         f'From the review\'s evidence sheets, the Phase 1 records and eleven study readers ({nf} of {nq} quotations found on their pages). {today}.</p>']
    # ---------------------------------------------------------------- at a glance
    bias_rows = [(g, lab, sum(1 for c in six if f(c)), sum(1 for c in rest if f(c))) for g, lab, f in BIAS]
    over = [r for r in bias_rows if r[2] / 6 - r[3] / 48 >= 0.25]
    under = [r for r in bias_rows if r[3] / 48 - r[2] / 6 >= 0.25]
    no_six_fam = [lab for lab, f in FAMILIES if not any(f(c) for c in six) and any(f(c) for c in rest)]
    H += ['<h2>At a glance</h2><div class="tiles">',
          f'<div class="tile"><b>54</b><span>designs on one frame: 6 carried forward, 48 not (43 from the review, 5 new)</span></div>',
          f'<div class="tile"><b>{len(ds)}</b><span>datasets across the 54; {len(cred["datasets"])} used by the six, each judged for credibility</span></div>',
          f'<div class="tile"><b>{sum(len(r["experiments"]) for i, r in readers.items() if i in SIX)}</b><span>experiments of the six recorded with their set-ups and results</span></div>',
          f'<div class="tile"><b>{sum(1 for i in ORDER if BASELINE[i][0].startswith("yes"))} of 6</b><span>run on our hardware as published</span></div>',
          '</div><div class="note"><b>Findings.</b><ul>',
          f'<li>The six over-represent: {"; ".join(f"{lab.lower()} ({a}/6 against {b}/48)" for g, lab, a, b in over)}.</li>' if over else '',
          f'<li>The six under-represent: {"; ".join(f"{lab.lower()} ({a}/6 against {b}/48)" for g, lab, a, b in under)}.</li>' if under else '',
          f'<li>Families of design held only by the 48: {"; ".join(no_six_fam).lower()}. The evaluation\'s results do not extend to them; '
          'the qualitative analysis below is their evidence.</li>' if no_six_fam else '',
          f'<li>No design of the six measures a cost on device-class hardware (C1); {sum(c["conditions"]["C1"] for c in rest)} of the 48 do. '
          'Device-class cost will come from our own runs, not from the papers.</li>',
          '<li>Code and paper differ in every one of the six; the differences are listed per design, and the baseline follows the paper where '
          'it states a value, the code where the paper is silent, and a stated assumption where both are.</li>',
          f'<li>Repetitions: {sum(1 for i in ORDER if not str(readers[i]["runs"].get("repetitions", "")).lower().startswith("not stated"))} of the six state how often their '
          'experiments were run; variance is reported by '
          f'{sum(1 for i in ORDER if str(readers[i]["runs"].get("variance_reported", "")).lower().startswith("yes"))}.</li>',
          '</ul></div>']
    H.append('<p class="muted">Contents: 1 The six compared · 2 Datasets and their credibility · 3 Runs and set-ups: the baseline · '
             '4 The 48 not carried forward · 5 Method and records</p>')
    # ---------------------------------------------------------------- 1. the six compared
    H.append('<h2>1. The six designs compared</h2><p>The six on the review\'s frame (the evidence sheets\' fields for zkPET and FL-BC-IDS; '
             'the readers\' classification in the same fields for the four new designs). The table states what each design does; it does not rank them.</p>')
    rows = [('From', lambda c: c['from']), ('Paper', lambda c: f"{c['title']} ({c['who']})"), ('Setting', lambda c: tags(c['settings'])),
            ('FL arrangement', lambda c: tags(c['fl'])), ('Privacy mechanisms', lambda c: tags(c['mechanisms'])),
            ('Hidden from', lambda c: tags(c['hidden_from'])), ('What is checked', lambda c: tags(c['checked'])),
            ('Checked by', lambda c: tags(c['checker'])), ('Checker sees an update', lambda c: tags(c['checker_sees_update'])),
            ('A zero-knowledge proof shows', lambda c: tags(c['zk_shows'])), ('Ledger', lambda c: f"{tags(c['ledger'])}; {tags(c['platform'])}"),
            ('On chain', lambda c: tags(c['on_chain'])), ('Still trusted', lambda c: tags(c['trusted'])),
            ('Threats claimed', lambda c: tags(c['claimed'])), ('Threats tested', lambda c: tags(c['tested'])),
            ('Environment; largest scale', lambda c: f"{tags(c['environment'])}; {c['scale']}"), ('Costs reported (where)', lambda c: f"{tags(c['costs_reported'])} ({tags(c['cost_where'])})"),
            ('C1 · C2 · C3', lambda c: ' · '.join('yes' if c['conditions'][k] else 'no' for k in ('C1', 'C2', 'C3')))]
    H.append('<div class="wrap"><table><thead><tr><th></th>' + ''.join(f'<th>{E(c["name"])}</th>' for c in six) + '</tr></thead><tbody>')
    H += [f'<tr><th>{E(lab)}</th>' + ''.join(f'<td>{E(f(c))}</td>' for c in six) + '</tr>' for lab, f in rows]
    H.append('</tbody></table></div><p class="muted">C1: a cost measured on device-class hardware. C2: no party that checks or aggregates '
             'sees an individual update. C3: a test by an attack of poisoning, malicious or fake participants, or free riding. Computed by the review\'s own rule.</p>')
    for i in ORDER:
        c, r = cards[i], readers[i]['card']
        H.append(f'<div class="card"><h3>{E(c["name"])}: {E(c["title"])} ({E(c["who"])})</h3><p>{E(r.get("summary", ""))}</p>')
        H.append('<b>Parties</b>' + ul(f"{p.get('party', '')}: {p.get('role', '')} ({p.get('tier', '')}; trusted: {p.get('trusted', '')})" for p in r.get('parties', [])))
        H.append('<b>One round</b><ol>' + ''.join(f'<li>{E(s)}</li>' for s in r.get('round', [])) + '</ol>')
        H.append(f'<b>Task and model</b><p>{E(r.get("task_and_model", ""))} {E(r.get("aggregation", ""))}</p>')
        H.append('<b>Privacy</b>' + ul(f"{p.get('mechanism', '')}: hides {p.get('hides', '')} from {p.get('from_whom', '')}. {p.get('parameters', '')}" for p in r.get('privacy', [])))
        H.append('<b>Verification</b>' + ul(f"{v.get('what_is_checked', '')}, by {v.get('by_whom', '')}: {v.get('how', '')} Sees the update: "
                                             f"{v.get('checker_sees_update', '')}. A rejected update: {v.get('rejected_update', '')}" for v in r.get('verification', [])))
        lg = r.get('ledger') or {}
        H.append(f"<b>Ledger</b><p>{'none' if lg.get('present') is False else E('; '.join(str(lg.get(k, '')) for k in ('platform', 'consensus', 'on_chain', 'contracts') if lg.get(k)))}</p>")
        H.append('<b>Trust assumptions</b>' + ul(r.get('trust_assumptions')))
        H.append(f'<b>Threat model</b><p>{E(r.get("threat_model", ""))}</p>')
        pt = r.get('phd_threats') or {}
        H.append('<b>The PhD\'s threats</b>' + ul(f"{lab}: claimed {'yes' if (pt.get(k) or {}).get('claimed') else 'no'}, tested "
                                                 f"{'yes' if (pt.get(k) or {}).get('tested') else 'no'}. {(pt.get(k) or {}).get('how', '')}"
                                                 for k, lab in (('poisoning', 'Poisoning'), ('sybil_fake', 'Malicious or fake participants'), ('free_riding', 'Free riding'))))
        H.append('<b>Limitations the authors state</b>' + ul(r.get('stated_limitations')) + '</div>')
    # ---------------------------------------------------------------- 2. datasets
    H.append('<h2>2. Datasets and their credibility</h2><p>Each dataset the six use, judged on six criteria (FRAMEWORK.md): '
             '<span class="grade-Strong">Strong</span>, <span class="grade-Adequate">Adequate</span> or <span class="grade-Weak">Weak</span>, '
             'with no total. The reasons and sources follow the table.</p>')
    crit = [('provenance', 'Provenance'), ('documentation', 'Documentation'), ('access_licence_integrity', 'Access, licence, integrity'),
            ('known_problems', 'Known problems'), ('adoption', 'Adoption'), ('fit_to_phd', 'Fit to the PhD')]
    H.append('<div class="wrap"><table><thead><tr><th>Dataset</th><th>Used by</th>' + ''.join(f'<th>{E(l)}</th>' for _, l in crit) + '</tr></thead><tbody>')
    for d in cred['datasets']:
        H.append(f'<tr><td><b>{E(d["dataset"])}</b></td><td>{E(", ".join(d["used_by"]))}</td>' +
                 ''.join(f'<td class="grade-{E(d["criteria"][k]["grade"])}">{E(d["criteria"][k]["grade"])}</td>' for k, _ in crit) + '</tr>')
    H.append('</tbody></table></div>')
    for d in cred['datasets']:
        H.append(f'<div class="card"><h3>{E(d["dataset"])}</h3><p>{E(d["what"])}</p><ul>' +
                 ''.join(f'<li><b>{E(l)}</b> ({E(d["criteria"][k]["grade"])}). {E(d["criteria"][k]["why"])}</li>' for k, l in crit if d["criteria"][k]["why"]) +
                 f'</ul><p><b>Overall.</b> {E(d["overall"])}</p><p class="muted">Sources: ' +
                 '; '.join((f'<a href="{E(s["url"])}">{E(s["what"])}</a>' if s['url'].startswith('http') else f'{E(s["what"])} (<span class="mono">{E(s["url"])}</span>)')
                           for s in d['sources']) + '</p></div>')
    kinds = collections.Counter(r['kind'] for r in ds)
    H.append(f'<h3>All {len(ds)} datasets of the 54 designs, by kind</h3><p>' + '; '.join(f'{E(k)}: {v}' for k, v in kinds.most_common()) +
             '. The full list, with the designs using each, is in <span class="mono">design-evaluation/study/datasets/DATASETS.csv</span>. '
             'The most used:</p><div class="wrap"><table><thead><tr><th>Dataset</th><th>Kind</th><th>Designs</th><th>Of the six</th></tr></thead><tbody>')
    H += [f'<tr><td>{E(r["dataset"])}</td><td>{E(r["kind"])}</td><td class="n">{r["designs"]}</td><td>{E(r["used_by_six"]) or "–"}</td></tr>'
          for r in ds if r['designs'] >= 2]
    H.append('</tbody></table></div>')
    # ---------------------------------------------------------------- 3. runs and set-ups
    H.append('<h2>3. Runs and set-ups: the baseline to follow</h2><p>For each of the six, what its paper states, what its code does, and how '
             'the baseline follows them: the paper\'s value first, the code\'s value where the paper is silent, a stated assumption where both are. '
             'Where the paper does not state its repetitions, five seeds, reported as mean and standard deviation (our choice, to confirm). '
             'Each design runs first as published, then in Gotham with the 5G simulator.</p>')
    H.append('<div class="wrap"><table><thead><tr><th>Design</th><th>Experiments</th><th>Covered by the code</th><th>Repetitions stated</th>'
             '<th>Variance reported</th><th>Runs on our hardware as published</th><th>Baseline approach (reviewer\'s reading of the records)</th></tr></thead><tbody>')
    for i in ORDER:
        r = readers[i]
        cov = len(r['code_vs_paper'].get('experiments_covered', []))
        H.append(f'<tr><td><b>{E(cards[i]["name"])}</b></td><td class="n">{len(r["experiments"])}</td><td class="n">{cov}</td>'
                 f'<td>{E(r["runs"].get("repetitions", ""))}</td><td>{E(r["runs"].get("variance_reported", ""))}</td>'
                 f'<td>{E(BASELINE[i][0])}</td><td>{E(BASELINE[i][1])}</td></tr>')
    H.append('</tbody></table></div>')
    FL = [('clients', 'Clients'), ('clients_per_round', 'Clients per round'), ('rounds', 'Rounds'), ('local_epochs', 'Local epochs'),
          ('batch_size', 'Batch size'), ('learning_rate', 'Learning rate'), ('global_learning_rate', 'Global learning rate'), ('optimiser', 'Optimiser')]
    for i in ORDER:
        r, c = readers[i], cards[i]
        s = r['setup']
        H.append(f'<div class="card"><h3>{E(c["name"])}</h3><b>Datasets</b>' +
                 ul(f"{d.get('name', '')} ({d.get('variant_or_version', '')}). Source: {d.get('source_given', '')}. Size: {d.get('size_used', '')}. "
                    f"Preprocessing: {d.get('preprocessing', '')}. Split: {d.get('train_test_split', '')}. Among clients: {d.get('partition_among_clients', '')}. "
                    f"Pages {', '.join(map(str, d.get('pages', [])))}." for d in r['datasets']))
        rows = [('Hardware', s.get('hardware')), ('Software', s.get('software'))]
        rows += [(lab, (s.get('fl') or {}).get(k)) for k, lab in FL if (s.get('fl') or {}).get(k) not in (None, '')]
        rows += [('Model', s.get('model')), ('Privacy parameters', s.get('privacy_parameters')), ('Zero-knowledge parameters', s.get('zk_parameters')),
                 ('Ledger parameters', s.get('ledger_parameters')), ('Attack parameters', s.get('attack_parameters')),
                 ('Metrics', ', '.join(map(str, s.get('metrics', [])))),
                 ('Repetitions', r['runs'].get('repetitions')), ('Seeds', r['runs'].get('seeds')),
                 ('How runs are combined', r['runs'].get('how_runs_are_combined')), ('Variance reported', r['runs'].get('variance_reported'))]
        H.append('<b>Set-up and runs, as the paper states them</b><table><tbody>' +
                 ''.join(f'<tr><th style="width:22%">{E(k)}</th><td>{E(v)}</td></tr>' for k, v in rows if v not in (None, '')) + '</tbody></table>')
        H.append('<b>Experiments and their reported results</b><div class="wrap"><table class="long"><thead><tr><th>Id</th><th>Measures</th><th>Setting</th>'
                 '<th>Reported in (page)</th><th>Headline values</th></tr></thead><tbody>' +
                 ''.join(f'<tr><td>{E(e.get("id", ""))}</td><td>{E(e.get("measures", ""))}</td><td>{E(e.get("setting", ""))}</td>'
                         f'<td>{E(e.get("reported_in", ""))} (p{E(e.get("page", ""))})</td><td>{E(e.get("headline_values", ""))}</td></tr>' for e in r['experiments']) +
                 '</tbody></table></div>')
        cv = r['code_vs_paper']
        H.append(f'<b>The code against the paper</b><p>Covers {E(", ".join(cv.get("experiments_covered", [])) or "–")}; '
                 f'not {E(", ".join(cv.get("experiments_not_covered", [])) or "–")}. Defaults: {E(cv.get("defaults_in_code", ""))} '
                 f'Runs in the code: {E(cv.get("runs_in_code", ""))}</p>' + ul(cv.get('differences')))
        rn = r['reproduction_notes']
        H.append(f'<b>To reproduce</b>' + ul(rn.get('needs')) + f'<p><b>Hardware gap.</b> {E(rn.get("hardware_gap", ""))}</p>'
                 '<b>Gaps to fill by assumption</b>' + ul(rn.get('unknowns_to_assume')) + '</div>')
    # ---------------------------------------------------------------- 4. the 48
    H.append(f'<h2>4. The 48 designs not carried forward: qualitative analysis</h2><p>The 48 are read on the same frame as the six, so that '
             'what the evaluation of the six cannot show is visible: where the six are not representative, which families of design only the 48 '
             'hold, and what the 48\'s own evidence shows. The 43 from the review are classified in their evidence sheets, which the author '
             'verified against the papers; the five new ones by study readers in the same fields.</p>')
    H.append('<h3>4.1 Are the six representative?</h3><p>Each feature among the six against the 48. A gap of 25 percentage points or more is marked.</p>'
             '<div class="wrap"><table class="long"><thead><tr><th>Aspect</th><th>Feature</th><th>Six</th><th>48</th><th>Six against 48</th></tr></thead><tbody>')
    for g, lab, a, b in bias_rows:
        d = a / 6 - b / 48
        mark = 'more among the six' if d >= 0.25 else ('fewer among the six' if d <= -0.25 else '')
        H.append(f'<tr><td>{E(g)}</td><td>{E(lab)}</td><td class="n">{pct(a, 6)}</td><td class="n">{pct(b, 48)}</td><td class="flag">{E(mark)}</td></tr>')
    H.append('</tbody></table></div>')
    H.append('<h3>4.2 Families of design</h3><p>By the privacy mechanism and by the check (a design can sit in several families). '
             '"Built from the paper": the Phase 1 or study reader\'s verdict on whether the paper describes the design well enough to build it.</p>'
             '<div class="wrap"><table class="long"><thead><tr><th>Family</th><th>Of the six</th><th>Of the 48</th><th>Built from the paper (of the 48)</th>'
             '<th>Of the 48: C1 · C2 · C3</th><th>Members among the 48</th></tr></thead><tbody>')
    for lab, f in FAMILIES:
        m6, m48 = [c for c in six if f(c)], [c for c in rest if f(c)]
        v = collections.Counter((c.get('buildable') or {}).get('reader') for c in m48)
        H.append(f'<tr><td><b>{E(lab)}</b></td><td>{E(", ".join(c["name"] for c in m6)) or "<b>none</b>"}</td><td class="n">{len(m48)}</td>'
                 f'<td>{E("; ".join(f"{k}: {n}" for k, n in v.most_common() if k))}</td>'
                 f'<td class="n">{" · ".join(str(sum(c["conditions"][k] for c in m48)) for k in ("C1", "C2", "C3"))}</td>'
                 f'<td>{E("; ".join(f"{c["name"] or c["who"]} ({c["who"]})" if c["name"] else c["who"] for c in m48))}</td></tr>')
    H.append('</tbody></table></div>')
    H.append('<h3>4.3 The evidence the 48 carry</h3><div class="wrap"><table><thead><tr><th>Reason not carried forward</th><th>Designs</th>'
             '<th>Test the PhD\'s threats</th><th>C1 · C2 · C3</th><th>Built from the paper</th></tr></thead><tbody>')
    for g in [k for k in dict.fromkeys(c['group'] for c in rest)]:
        m = [c for c in rest if c['group'] == g]
        t = sum(1 for c in m if any(c['phd_threats'][k]['tested'] for k in c['phd_threats']))
        v = collections.Counter((c.get('buildable') or {}).get('reader') for c in m)
        H.append(f'<tr><td>{E(groups[g])}</td><td class="n">{len(m)}</td><td class="n">{t}</td>'
                 f'<td class="n">{" · ".join(str(sum(c["conditions"][k] for c in m)) for k in ("C1", "C2", "C3"))}</td>'
                 f'<td>{E("; ".join(f"{k}: {n}" for k, n in v.most_common() if k))}</td></tr>')
    H.append('</tbody></table></div>')
    H.append('<h3>4.4 The 48, one by one</h3><div class="wrap"><table class="long"><thead><tr><th>Design</th><th>Reason</th><th>Privacy</th>'
             '<th>Checked; by; sees update</th><th>ZK shows</th><th>Ledger</th><th>Tested</th><th>C1 C2 C3</th><th>Built from the paper</th></tr></thead><tbody>')
    for c in rest:
        H.append(f'<tr><td><b>{E(c["name"] or c["who"])}</b><br><span class="muted">{E(c["title"])} ({E(c["who"])}; {E(c["from"])})</span></td>'
                 f'<td>{E(c["group_label"])}</td><td>{E(short(c["mechanisms"]))}</td>'
                 f'<td>{E(short(c["checked"]))}; {E(short(c["checker"]))}; {E(short(c["checker_sees_update"]))}</td>'
                 f'<td>{E(short(c["zk_shows"]))}</td><td>{E(short(c["ledger"]))}; {E(short(c["platform"]))}</td><td>{E(short(c["tested"]))}</td>'
                 f'<td class="n">{" ".join("Y" if c["conditions"][k] else "–" for k in ("C1", "C2", "C3"))}</td>'
                 f'<td>{E((c.get("buildable") or {}).get("reader", ""))}</td></tr>')
    H.append('</tbody></table></div>')
    # ---------------------------------------------------------------- 5. method
    H.append('<h2>5. Method and records</h2><ul>'
             '<li>Method: <span class="mono">design-evaluation/study/FRAMEWORK.md</span>; readers\' instructions: <span class="mono">READER-PROMPT.md</span>.</li>'
             f'<li>Eleven study readers (Sonnet), one per paper, under the author\'s permission of 26 November 2026 (CLAUDE.md): the six carried forward and '
             f'the five new designs not carried forward. {nf} of {nq} quotations found on their pages by script (<span class="mono">verify_study_quotes.py</span>); '
             'the readers\' records are in their own words.</li>'
             '<li>The 43 review designs not carried forward: their evidence sheets (verified by the author) and Phase 1 reader checklists; no new reading.</li>'
             '<li>The conditions C1 to C3 come from the review\'s own rule; on the 45 sheets it gives exactly the review\'s lists.</li>'
             '<li>Dataset credibility: the datasets\' own pages, OpenAlex records of the dataset papers and published critiques, with sources per dataset '
             '(<span class="mono">datasets/CREDIBILITY.json</span>).</li>'
             '<li>Records: <span class="mono">design-evaluation/study/CARDS.json</span> and <span class="mono">CARDS.csv</span>; each design\'s '
             '<span class="mono">study/</span> folder. Scripts: <span class="mono">scripts/design_eval/study_packets.py, verify_study_quotes.py, '
             'study_cards.py, study_datasets.py, study_report.py</span>.</li></ul></body></html>')
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'Docs' / f'PHASE2-DESIGN-STUDY-{today}.html'   # a trial path, or Docs
    n = 2
    while out.exists() and len(sys.argv) == 1:
        out = ROOT / 'Docs' / f'PHASE2-DESIGN-STUDY-V{n}-{today}.html'
        n += 1
    out.write_text('\n'.join(x for x in H if x))
    print(out, '| over-represented:', [r[1] for r in over], '| under:', [r[1] for r in under], '| families only in the 48:', no_six_fam)


if __name__ == '__main__':
    main()
