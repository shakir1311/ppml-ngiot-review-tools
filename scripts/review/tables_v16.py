"""Tables, statistics and figure registry of the V16 review.

V16 adds six studies found by citation searching after the search rounds (O096-O101), so it has its own
eligibility decisions, selection counts and search check in _src/V16. Everything else is shared with V15: the
synthesis records stay in _src/V14, and statistics and most tables come from tables_v15, recomputed over the V16
set of included studies. The comparison with the closest surveys gains Qu et al. and a row for this review."""
import json, re
import tables_v15 as V15
import tables_v14 as V14
from tables_v15 import *  # noqa: F401,F403  (helpers, abbreviations and method tables are unchanged)
from tables_v14 import kind, year, YES, NO  # noqa: F401

SRC16 = V14.ROOT / 'myliteraturereviewpaper' / '_src' / 'V16'
PARTIAL = '◐'


def load():
    d = V14.load()
    ex = json.loads((SRC16 / 'screening.json').read_text())['excluded']
    d['excluded'] = ex
    d['included'] = [i for i in d['papers'] if i not in ex]
    d['prisma'] = json.loads((SRC16 / 'prisma.json').read_text())
    q = json.loads((SRC16 / 'search-check.json').read_text())
    d['qgs'] = {'per_string': q['per_string'], 'combined': q['combined'], 'n': q['n'], 'missed': q['missed']}
    return d


# ------------------------------------------------------------------ dataset names
# V14 matched substrings in a fixed order, so MedMNIST sets counted as MNIST (TissueMNIST even as EMNIST), FMNIST and
# F-MNIST were missed as Fashion-MNIST, and a UNSW IoT traffic trace counted as UNSW-NB15. V16 matches whole names.
_V14_NORM = V14.norm_dataset


def norm_dataset(x):
    t = x.lower().strip()
    if re.search(r'(tissue|oct|path|organ[acs]?|blood|derma|breast|pneumonia|retina|chest|organa)mnist|medmnist|ch-mnist', t):
        return 'MedMNIST and other medical images'
    if re.search(r'fashion|^f-?mnist$', t):
        return 'Fashion-MNIST'
    if re.search(r'femnist|federated[- ]?e?mnist', t):
        return 'FEMNIST'
    if re.search(r'^emnist', t):
        return 'EMNIST'
    if re.search(r'^mnist$|^mnist\b', t):
        return 'MNIST'
    if 'unsw iot' in t or 'iot analytics' in t or 'iot traffic' in t:
        return 'IoT traffic traces'
    if re.search(r'\bton[_ ]?iot\b', t):
        return 'TON_IoT'
    return _V14_NORM(x)


V14.norm_dataset = norm_dataset          # V14.stats and V15.t_approaches look the name up at call time
V15.norm_dataset = norm_dataset


# ------------------------------------------------------------------ comparison with the closest surveys
CLOSEST = V15.CLOSEST + [('O100', 'Blockchain-enabled FL: decentralisation, incentives, attacks')]
V15.CLOSEST = CLOSEST            # V15.stats and cmp_counts read the list from their own module
THIS_WORK = {'focus': 'PPML for NG-IoT security',
             'marks': [YES, YES, YES, YES, YES, YES, YES, PARTIAL]}


def scope(d, i):
    """Number of studies and period, as the survey states them: '41 (2016–22)', '>200 (2014–26)', 'n.s.'."""
    sv = d['coding'][i].get('survey') or {}
    n = str(sv.get('studies_reviewed') or '')
    m = re.search(r'\d[\d,]*(?=\+?\s*(?:works|studies|papers|publications|systems|schemes))', n)
    pre = '>' if ('more than' in n or '+' in n) else '~' if 'about' in n else ''
    per = re.findall(r'(?:19|20)\d\d', str(sv.get('years_covered') or ''))
    return (pre + m.group(0) if m else 'n.s.') + (f" ({per[0]}–{per[-1][2:]})" if len(per) >= 2 else '')


def t_surveys_cmp(d, s):
    rows, marks_all = [], []
    for i, focus in sorted(CLOSEST, key=lambda x: (year(d, x[0]), d['refs'][x[0]]['narrative_ieee'])):
        m = survey_marks(d, i)
        marks_all.append(m)
        rows.append([f'@{i}', str(year(d, i)), focus, scope(d, i)] + [YES if x else NO for x in m])
    for j, (h, _, _) in enumerate(CMP_COLS):       # a column that no survey meets tells the reader nothing
        if not any(m[j] for m in marks_all):
            raise SystemExit(f'comparison column {h!r} is met by no survey')
    own = ['This work', '2026', THIS_WORK['focus'], f"{len(d['included'])} (2020–26)"] + THIS_WORK['marks']
    rows.append([{'runs': [{'text': x, 'bold': True}], 'fill': 'EEF5FD'} for x in own])
    cols = [{'header': 'Survey', 'width': 1000}, {'header': 'Year', 'width': 450, 'align': 'center'},
            {'header': 'Focus', 'width': 1650}, {'header': 'Studies (period)', 'width': 900, 'align': 'center'}]
    cols += [{'header': hd, 'width': 628, 'align': 'center'} for _, _, hd in CMP_COLS]
    return {'caption': 'Comparison of the closest surveys (2022–2026) with this work.',
            'columns': cols, 'rows': rows, 'font_size': 7.5,
            'note': '✓ = treated as a subject of its own (a section, a branch of the taxonomy, a table or a comparison axis); '
                    f'{PARTIAL} = treated in part; – = absent or mentioned only in passing. Studies (period) = the number of '
                    'studies reviewed and the period covered, as each survey states them; n.s. = not stated. IoT / edge = the '
                    'IoT, edge or 5G/6G setting; Priv. mech. = privacy mechanisms; Att., def. = attacks and defences; Upd. '
                    'verif. = how model updates or their aggregation are checked; Eval. = frameworks, datasets, testbeds or '
                    'metrics; Data law = the GDPR or other data-protection law; Syst. meth. = a search strategy and selection '
                    'criteria are reported. This work reports both, but its search was iterative and screened by one '
                    'reviewer (Section IX).'}


def t_gaps(d, s):
    rows = [
        ['G1 Checking updates without seeing them, verifiably', 'In most compared approaches, a party that sees the updates or servers that must not collude check them; two included ledger-based studies implement proofs about client updates', 'Publicly verifiable proofs of simple predicates about each update, bound to the update and recorded on a ledger'],
        ['G2 Little testing on IoT hardware', '{{N:learn_real_device}} of the {{N:learn_prim}} learning studies measure their cost on IoT or edge hardware; proof generation is measured on one phone and on no gateway; no study measures device energy', 'A shared benchmark of proofs on gateway-class devices: time, memory, energy and proof size'],
        ['G3 Networks assumed rather than tested', 'No study evaluates learning over a real or emulated wireless IoT or 5G link', 'Evaluation over emulated IoT links with loss, delay, dropouts and jamming'],
        ['G4 Personal data on the ledger', '{{N:oc_C}} of the {{N:prim_ledger}} ledger-based studies keep only commitments, hashes, proofs or payments on-chain', 'Ledgers that hold only proofs and salted, hiding commitments, with erasure designed in'],
    ]
    return {'caption': 'Research gaps identified by this survey, the evidence for each, and a direction for research.',
            'columns': [{'header': 'Gap', 'width': 2000}, {'header': 'Evidence from this survey', 'width': 4026},
                        {'header': 'Direction', 'width': 3000}],
            'rows': rows, 'font_size': 8}


# zero-knowledge toolkits: V14 matched only SNARK tools; the proof libraries of the secure-aggregation studies
# (Bulletproofs, EMP-toolkit) count as well
ZK_TOOLS = r'circom|snarkjs|libsnark|zokrates|gnark|arkworks|halo2|bulletproofs|emp-toolkit|wolverine'


def stats(d):
    s = V15.stats(d)
    p = d['prisma']
    s['other_identified'] = p['other_identified']
    C = d['coding']
    prim = [i for i in d['included'] if kind(d, i) == 'primary']
    s['tool_zk'] = sum(1 for i in prim if re.search(ZK_TOOLS, ' '.join(C[i]['evaluation'].get('tools', [])).lower()))
    names = {i: set(norm_dataset(v) for v in C[i]['evaluation'].get('datasets', [])) for i in prim}
    s['ds_EMNIST'] = sum(1 for i in prim if names[i] & {'EMNIST', 'FEMNIST'})
    s['ds_medical_mnist'] = sum(1 for i in prim if 'MedMNIST and other medical images' in names[i])
    return s


def tables(d, s):
    t = V15.tables(d, s)
    t['surveys'] = t_surveys_cmp(d, s)
    t['gaps'] = t_gaps(d, s)
    return t


def figures(d, s):
    f = V15.figures(d, s)
    f['prisma']['caption'] = 'Selection of studies.'
    return f


def generated_text(d, s):
    return {}


# ------------------------------------------------------------------ evidence and quality over the right denominators
EXPERIMENTAL = ('experiment on datasets', 'prototype or testbed', 'simulation', 'testing of real devices or software',
                'measurement of real systems', 'real deployment or field study')


def experimental(d, i):
    """A primary study that reports experiments or measurements, to which the reporting criteria QP1–QP7 apply."""
    ev = [e.strip() for e in d['papers'][i]['evaluation_type'].split(';')]
    return kind(d, i) == 'primary' and any(e in EXPERIMENTAL for e in ev)


def evidence_stats(d, s):
    C = d['coding']
    prim = [i for i in d['included'] if kind(d, i) == 'primary']
    exp = [i for i in prim if experimental(d, i)]
    rg = lambda i: C[i].get('rigour') or {}
    s['prim_exp'] = len(exp)
    s['prim_runs'] = sum(1 for i in exp if not re.match(r'(?i)not stated|^$', rg(i).get('runs', '') or ''))
    s['prim_spread'] = sum(1 for i in exp if rg(i).get('spread'))
    s['prim_test'] = sum(1 for i in exp if rg(i).get('significance_test'))
    s['prim_code'] = sum(1 for i in exp if rg(i).get('code_available'))
    ev = collections.Counter()
    for i in prim:
        for e in d['papers'][i]['evaluation_type'].split(';'):
            ev[e.strip()] += 1
    s['evp_experiment'] = ev['experiment on datasets']
    s['evp_prototype'] = ev['prototype or testbed']
    s['evp_security'] = ev['security analysis']
    s['evp_cost'] = ev['complexity or cost analysis']
    return s


def t_quality16(d, s):
    C = d['coding']
    inc = [i for i in d['included'] if i in C]
    exp = [i for i in inc if experimental(d, i)]
    named = [i for i in exp if C[i]['evaluation'].get('datasets')]
    sec = [i for i in inc if kind(d, i) == 'secondary']

    def cnt(ids, f):
        n = sum(1 for i in ids if f(C[i]))
        return f'{n} of {len(ids)}'
    rg = lambda c: c.get('rigour') or {}
    sv = lambda c: c.get('survey') or {}
    rows = [
        {'group': f'Primary studies that report experiments or measurements (n = {len(exp)})'},
        ['QP1', 'Is the solution evaluated on named data or a named workload?', cnt(exp, lambda c: bool(c['evaluation'].get('datasets')))],
        ['QP2', 'Is it compared with at least one other approach?', cnt(exp, lambda c: c['id'] not in V14.no_baseline(d))],
        ['QP3', 'Are results repeated over several runs or seeds?', cnt(exp, lambda c: not re.match(r'(?i)not stated|^$', rg(c).get('runs', '') or ''))],
        ['QP4', 'Is the variation between runs reported (standard deviation, error bars or confidence interval)?', cnt(exp, lambda c: bool(rg(c).get('spread')))],
        ['QP5', 'Is a statistical test reported?', cnt(exp, lambda c: bool(rg(c).get('significance_test')))],
        ['QP6', 'Are all datasets public? (studies with named data)', cnt(named, lambda c: bool(rg(c).get('data_public')))],
        ['QP7', 'Is the code released?', cnt(exp, lambda c: bool(rg(c).get('code_available')))],
        {'group': f'Secondary studies (n = {len(sec)})'},
        ['QS1', 'Are the search strategy and the selection criteria reported?', cnt(sec, lambda c: sv(c).get('protocol') == 'systematic')],
        ['QS2', 'Is at least part of the review method reported (e.g. sources or years)? QS1 implies QS2.', cnt(sec, lambda c: sv(c).get('protocol') in ('systematic', 'partial'))],
        ['QS3', 'Is the period covered stated?', cnt(sec, lambda c: not re.match(r'(?i)not stated|^$', sv(c).get('years_covered', '') or ''))],
        ['QS4', 'Is the number of studies reviewed stated?', cnt(sec, lambda c: not re.match(r'(?i)not stated|^$', sv(c).get('studies_reviewed', '') or ''))],
    ]
    return {'caption': 'Quality appraisal criteria and how many included studies meet each. The appraisal describes '
                       'how the evidence is reported; no study was excluded on quality.',
            'columns': [{'header': 'Code', 'width': 700}, {'header': 'Question', 'width': 6126},
                        {'header': 'Studies that meet it', 'width': 2200}],
            'rows': rows, 'font_size': 8.5}


# ------------------------------------------------------------------ the dated re-run of the search strings
def t_searchrun(d, s):
    r = json.loads((SRC16 / 'search-runs-2026-09-29.json').read_text())
    rows = []
    tot = collections.Counter()
    for name, v in r['openalex'].items():
        rows.append([name, 'OpenAlex'] + [f"{v[k]['count']:,}" for k in ('1', '2', '3', '4', 'any')])
        for k in ('1', '2', '3', '4', 'any'):
            tot[k] += v[k]['count']
    rows.append(['arXiv', 'arXiv API'] + [f"{r['arxiv'][k]['count']:,}" for k in ('1', '2', '3', '4', 'any')])
    for k in ('1', '2', '3', '4', 'any'):
        tot[k] += r['arxiv'][k]['count']
    rows.append([{'runs': [{'text': 'Sum over sources', 'bold': True}]}, ''] +
                [{'runs': [{'text': f'{tot[k]:,}', 'bold': True}]} for k in ('1', '2', '3', '4', 'any')])
    cols = [{'header': 'Source', 'width': 2600}, {'header': 'Searched through', 'width': 1426},
            {'header': 'String 1', 'width': 1000, 'align': 'center'}, {'header': 'String 2', 'width': 1000, 'align': 'center'},
            {'header': 'String 3', 'width': 1000, 'align': 'center'}, {'header': 'String 4', 'width': 1000, 'align': 'center'},
            {'header': 'Any', 'width': 1000, 'align': 'center'}]
    return {'caption': 'Records returned by the four search strings on 29 September 2026 (titles and abstracts, works '
                       'published from 1 January 2020).',
            'columns': cols, 'rows': rows, 'font_size': 8,
            'note': 'The first five sources were searched through the OpenAlex index, restricted to each publisher; the '
                    'counts for IEEE, ACM, Elsevier and Springer Nature are lower bounds, because OpenAlex attributes only '
                    'about a quarter of IEEE’s and a sixth of ACM’s registered works to them and holds abstracts for '
                    'about a third of Elsevier’s and Springer Nature’s. Any = the union of the four strings within a '
                    'source. Records overlap across sources, for example a preprint and its published version.'}


# ------------------------------------------------------------------ confidentiality, verification, threat model
def t_mechanisms16():
    return {
        'caption': 'Confidentiality mechanisms for distributed learning: what each protects, whom it must trust and what it costs.',
        'columns': [{'header': 'Mechanism', 'width': 1500}, {'header': 'What it protects', 'width': 2400},
                    {'header': 'Whom it must trust', 'width': 1900}, {'header': 'Main cost', 'width': 1900},
                    {'header': 'Surveys', 'width': 1326}],
        'rows': [
            ['Differential privacy (central, local or distributed)', 'Individual records against inference from updates or the model, by calibrated noise; local DP adds the noise on the device, distributed DP sums noise shares under secure aggregation, and shuffling hides who sent what', 'Central DP: the aggregator that adds the noise; local DP: no one; distributed DP: the aggregation protocol', 'Accuracy falls as the privacy budget ε shrinks; local DP costs most', '[@O060; @O101]'],
            ['Homomorphic encryption (additive or fully homomorphic)', 'Updates while the aggregator computes on them in encrypted form', 'The holder of the decryption key (often a key authority)', 'Ciphertext size and computation; fully homomorphic schemes are costly for deep circuits, not for the additions of aggregation', '[@O077; @O076]'],
            ['Secure multi-party computation and secret sharing', 'Inputs of each party during a joint computation; a share alone reveals nothing', 'A threshold of the parties not to collude', 'Communication rounds and messages between parties', '[@O077; @S020]'],
            ['Secure aggregation (masking)', 'Individual updates: a semi-honest server learns only their sum; a malicious server can send inconsistent models to single out one client [@O097]', 'Enough clients to stay online and not to collude with the server', 'Extra rounds; recovery when clients drop out', '[@S020; @S024]'],
            ['Trusted execution environment', 'Code and data inside a hardware-isolated enclave, even from the host', 'The hardware vendor and its attestation service', 'Enclave memory limits; exposure to side channels', '[@O089; @S032]'],
        ],
        'font_size': 8,
    }


def t_verification():
    return {
        'caption': 'Ways of checking model updates, or their aggregation, that privacy mechanisms hide.',
        'columns': [{'header': 'Method', 'width': 1500}, {'header': 'What it can check', 'width': 2200},
                    {'header': 'Who can verify the outcome', 'width': 1700}, {'header': 'Whom it must trust', 'width': 1900},
                    {'header': 'Main cost', 'width': 1726}],
        'rows': [
            ['Inspection by a party that sees the updates', 'Any statistic of the updates (similarity, norm, accuracy on held-out data)', 'That party only', 'The inspecting server, miners, committee or peers', 'Low; privacy limited to what the inspector may see'],
            ['Computation on encrypted or shared updates', 'Simple statistics (cosine similarity, norm, median) computed under HE or SMPC', 'The computing parties', 'Servers not to collude, or an honest majority', 'Computation and communication of the protocol'],
            ['Hardware attestation', 'That a known program (aggregation or a check) ran inside an enclave', 'Parties that trust the vendor’s attestation service', 'The hardware vendor', 'Low per update; enclave memory limits'],
            ['Zero-knowledge proof, designated verifier', 'A predicate on hidden updates (a bound, a range, correct shares), checked within the protocol', 'The protocol’s participants', 'Proof soundness and the honest-majority assumptions of the protocol', 'Prover time and communication'],
            ['Zero-knowledge proof, publicly verifiable', 'A predicate on hidden updates, correct training or correct aggregation', 'Anyone, including a ledger', 'Proof soundness, and the set-up for circuit-specific systems', 'Prover time and memory; verification grows with the public inputs'],
        ],
        'font_size': 8,
    }


def t_threatmodel():
    return {
        'caption': 'Parties of blockchain-based FL, what each may do, the bounds that designs assume, and the goals at risk.',
        'columns': [{'header': 'Party', 'width': 1500}, {'header': 'What it may do', 'width': 3300},
                    {'header': 'Bound usually assumed', 'width': 2226}, {'header': 'Goals at risk', 'width': 2000}],
        'rows': [
            ['Clients (IoT devices or gateways)', 'Poison data or updates; send no real work (free riding); join under many identities (Sybil); collude; drop out', 'A minority of malicious clients, e.g. fewer than a third [@O098]', 'Robustness, fairness'],
            ['Aggregator (server or edge server)', 'Read updates; send inconsistent models to single out one client [@O097]; drop or substitute admitted updates; give clients different global models [@S032]', 'Semi-honest in most designs', 'Confidentiality, verifiability'],
            ['Ledger validators or miners', 'Read updates written on-chain; censor, reorder or collude', 'Fewer than a third faulty for BFT consensus [@N003; @N019]; an honest majority of work for PoW', 'Confidentiality, availability, verifiability'],
            ['Set-up or key authority', 'Keep the trapdoor of a circuit-specific set-up and forge proofs; hold decryption keys; open pseudonyms', 'Trusted', 'Soundness, confidentiality, anonymity'],
            ['Hardware vendor (TEEs)', 'Operate the attestation service; expose enclaves to side channels', 'Trusted', 'Confidentiality, verifiability'],
            ['Network adversary', 'Jam radio links, flood the aggregator or ledger, deplete batteries, eavesdrop on links', 'Not bounded by the designs', 'Availability, confidentiality'],
        ],
        'font_size': 8,
    }


# ------------------------------------------------------------------ survey questions (scope of V16)
def t_questions16():
    rows = [
        ['SQ1', 'What are the building blocks of privacy-preserving and verifiable FL in NG-IoT, and how can they be classified?', 'To fix the concepts and a taxonomy that the rest of the survey uses', 'Section IV'],
        ['SQ2', 'How do existing studies combine privacy mechanisms, checks on updates and blockchains with distributed learning, and which threats do they address?', 'To compare the approaches and find where they differ', 'Section V'],
        ['SQ3', 'Which tools, data, devices and networks are used to evaluate these solutions, and how is the evidence reported?', 'To judge how strong and how realistic the evidence is', 'Section VI'],
        ['SQ4', 'Which trends and open challenges emerge, including those raised by data-protection law?', 'To identify research gaps and directions', 'Section VII'],
    ]
    return {'caption': 'Survey questions.',
            'columns': [{'header': 'ID', 'width': 600}, {'header': 'Question', 'width': 4326},
                        {'header': 'Motivation', 'width': 2900}, {'header': 'Answered in', 'width': 1200}],
            'rows': rows, 'font_size': 8.5}


# ------------------------------------------------------------------ V16 classification records
CLASS = SRC16 / 'classify'


def load_class(kind_):
    return {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in sorted((CLASS / kind_).glob('*.json'))}


# ------------------------------------------------------------------ appendix: every included study
THEME_SHORT = {'T4': 'Blockchain-based learning', 'T3': 'Privacy mechanisms', 'T5': 'Attacks and defences',
               'T1': 'NG-IoT fabric', 'T2': 'Distributed learning', 'T6': 'Regulation, erasure'}


def quality_score(d, i):
    C = d['coding'][i]
    rg = C.get('rigour') or {}
    if kind(d, i) == 'secondary':
        sv = C.get('survey') or {}
        met = [sv.get('protocol') == 'systematic', sv.get('protocol') in ('systematic', 'partial'),
               not re.match(r'(?i)not stated|^$', sv.get('years_covered', '') or ''),
               not re.match(r'(?i)not stated|^$', sv.get('studies_reviewed', '') or '')]
        return f'QS {sum(met)}/4'
    if not experimental(d, i):
        return 'n.a.'
    met = [bool(C['evaluation'].get('datasets')), i not in V14.no_baseline(d),
           not re.match(r'(?i)not stated|^$', rg.get('runs', '') or ''), bool(rg.get('spread')),
           bool(rg.get('significance_test')), bool(rg.get('data_public')), bool(rg.get('code_available'))]
    return f'QP {sum(met)}/7'


def t_appendix(d, s):
    fp = SRC16 / 'focus.json'
    focus = json.loads(fp.read_text()) if fp.exists() else {}
    rows = []
    for k, (code, name) in enumerate(THEME_SHORT.items()):
        ids = sorted([i for i in d['included'] if d['coding'][i]['theme'] == code],
                     key=lambda i: (kind(d, i) != 'primary', year(d, i), d['refs'][i]['narrative_ieee']))
        rows.append({'group': f'{name} ({len(ids)} studies)'})
        for i in ids:
            rows.append([f'[@{i}]', str(year(d, i)), 'P' if kind(d, i) == 'primary' else 'S',
                         focus.get(i, d['coding'][i]['description'][:80]), quality_score(d, i)])
    return {'caption': 'Included studies by theme, with the focus of each and its quality appraisal.',
            'columns': [{'header': 'Ref.', 'width': 700}, {'header': 'Year', 'width': 560, 'align': 'center'},
                        {'header': 'Type', 'width': 560, 'align': 'center'}, {'header': 'Focus', 'width': 6006},
                        {'header': 'Quality', 'width': 1200, 'align': 'center'}],
            'rows': rows, 'font_size': 7.5,
            'note': 'Type: P = primary, S = secondary study. Quality: the number of reporting criteria of the quality '
                    'appraisal table met, QP1–QP7 for primary studies that report experiments or measurements and QS1–QS4 '
                    'for secondary studies; n.a. = a primary study without experiments (for example a legal analysis).'}


# ------------------------------------------------------------------ the blockchain-based approaches (V16)
# Selection rule: included ledger-based primary studies published from 2022 that protect the updates with DP, HE,
# SMPC or secret sharing, masking, a TEE or a ZKP (Section V-A). Ledger and roles: reviewer's classification; roles
# A = aggregates, R = records, V = verifies, E = enforces participation (incentives, deposits, reputation).
LEDGER_ROLES = {i: (v[0], v[1].replace('I', 'E')) for i, v in V15.APPROACH.items()}
LEDGER_ROLES.update({'O083': ('Fabric or private Ethereum; PoA', 'A R V'),
                     'O033': ('Hyperledger Fabric; committee (PoMC)', 'A R V')})
ANCHOR_GROUPS = [('single party', 'The check relies on a single party'),
                 ('honest-majority committee or validators', 'The check relies on an honest majority of miners, a committee or validators'),
                 ('non-colluding servers', 'The check relies on servers that do not collude'),
                 ('hardware vendor', 'The check relies on trusted hardware'),
                 ('proof soundness (trusted set-up)', 'The check rests on a proof with a trusted set-up'),
                 ('proof soundness (transparent)', 'The check rests on a proof without a trusted set-up'),
                 ('none', 'No check on the updates')]


def approach_ids(d):
    C = d['coding']
    hide = {'DP', 'LDP', 'HE', 'FHE', 'SMPC', 'secret_sharing', 'secure_aggregation', 'TEE', 'ZKP'}
    ids = []
    for i in d['included']:
        c = C[i]
        if kind(d, i) != 'primary' or not c['ledger'].get('used') or year(d, i) < 2022:
            continue
        ms = set(c['privacy_mechanisms'])
        if ms & hide or any('masking' in m for m in ms):
            ids.append(i)
    return ids


def priv_short16(i, c, r):
    ms = []
    for m in c['privacy_mechanisms']:
        if m in ('none',) or m.startswith('other'):
            continue
        lab = V14.PRIV_LABEL.get(m, m)
        if m in ('DP', 'LDP') and r and r['privacy'].get('gan_perturbation'):
            lab = 'GAN noise'
        elif m in ('DP', 'LDP') and r and r['privacy'].get('dp_epsilon_stated') is False:
            lab += ' (ε n.s.)'
        ms.append(lab)
    if i in V15.OTHER_SHORT:
        ms.append(V15.OTHER_SHORT[i])
    if 'GAN noise' in ms:                      # the GAN is the noise generator, not a separate mechanism
        ms = [m for m in ms if m != 'GAN']
    return ', '.join(dict.fromkeys(ms)) or NO


def threat_runs(r):
    runs = []
    for k in 'PSCRDI':
        v = r['threats'][k]
        if v == 'none':
            continue
        runs.append({'text': k, 'bold': v == 'evaluated'})
        runs.append({'text': ' '})
    return runs[:-1] or [{'text': NO}]


def t_approaches16(d, s):
    A = load_class('approaches')
    C = d['coding']
    ids = approach_ids(d)
    missing = [i for i in ids if i not in A]
    if missing:
        raise SystemExit(f'approaches without a V16 classification record: {missing}')
    rows = []
    for anchor, label in ANCHOR_GROUPS:
        grp = sorted([i for i in ids if A[i]['trust_anchor']['value'] == anchor],
                     key=lambda i: (year(d, i), d['refs'][i]['narrative_ieee']))
        if not grp:
            continue
        rows.append({'group': f'{label} ({len(grp)})'})
        for i in grp:
            r = A[i]
            ledger, roles = LEDGER_ROLES[i]
            scheme = r['scheme'].split('(')[0].strip() or NO
            rows.append([f'[@{i}]', scheme, priv_short16(i, C[i], r), ledger, roles,
                         ', '.join(r['claim_checked']['codes']) or NO, r['verifiable_by']['value'],
                         d['onchain'].get(i, '?'), {'runs': threat_runs(r)}])
    cols = [{'header': 'Ref.', 'width': 580}, {'header': 'Scheme', 'width': 1100},
            {'header': 'Privacy', 'width': 1300}, {'header': 'Ledger', 'width': 1500},
            {'header': 'Roles', 'width': 700, 'align': 'center'}, {'header': 'Checked', 'width': 1000, 'align': 'center'},
            {'header': 'Verifiable by', 'width': 1100}, {'header': 'On-chain', 'width': 646, 'align': 'center'},
            {'header': 'Threats', 'width': 1100, 'align': 'center'}]
    return {'caption': f'The {len(ids)} blockchain-based privacy-preserving FL approaches compared (2022–2026), grouped by '
                       'what their check on updates relies on.',
            'columns': cols, 'rows': rows, 'font_size': 7,
            'note': 'Selection: the included ledger-based primary studies published from 2022 onwards that protect the '
                    'updates with DP, HE, SMPC or secret sharing, masking, a TEE or a ZKP. Privacy: DP / LDP = (local) '
                    'differential privacy (ε n.s. = no privacy budget stated); GAN noise = perturbation generated by a '
                    'generative adversarial network; HE = homomorphic encryption; SMPC = secure multi-party computation; '
                    'SS = secret sharing; SecAgg = secure aggregation; TEE = trusted execution; ZKP = zero-knowledge proof; '
                    'AES = Advanced Encryption Standard. Roles of the ledger: A = aggregates in place of a server; '
                    'R = records updates, models or proofs; V = verifies updates or their aggregation; E = enforces '
                    'participation (incentives, deposits, reputation). Checked, after Rizzini et al.: CL1 data binding, '
                    'CL2 training, CL3 admissibility of each update, CL4 uniqueness and freshness; AG1 admitted set, AG2 '
                    'aggregation, AG3 non-equivocation. On-chain: U = local updates in plaintext or only noised; E = local '
                    'updates encrypted or masked; G = global or aggregated models; C = only commitments, hashes, proofs or '
                    'payments. Threats: P = poisoning; S = fake nodes (Sybil); C = collusion; R = free riding; D = denial '
                    'of service; I = inference; bold = evaluated with an implemented attack or a measured leakage, plain = '
                    'claimed without such an experiment.'}


# ------------------------------------------------------------------ what the checker sees, and what it checks
# From the V16 classification records (privacy mechanisms and the text of the check): what the party that checks
# sees of each update. Proof-based checks are marked in the table.
SEES = {
    'N002': 'clear', 'N005': 'clear', 'N008': 'clear', 'N009': 'clear', 'N014': 'clear', 'N021': 'clear',
    'O033': 'clear', 'O083': 'clear',
    'N001': 'hidden', 'N003': 'hidden', 'N004': 'hidden', 'N006': 'hidden', 'N007': 'hidden', 'N011': 'hidden',
    'N012': 'hidden', 'N013': 'hidden', 'N015': 'hidden', 'N016': 'hidden', 'N017': 'hidden', 'N018': 'hidden',
    'N019': 'hidden',
    'N010': 'enclave', 'N020': 'enclave',
}
SEES_LABEL = [('clear', 'In the clear or only noised'), ('hidden', 'Encrypted, masked or secret-shared'),
              ('enclave', 'Inside an enclave')]
OBJ_LABEL = [('content', 'The content of each update (CL1–CL3)'), ('aggregate', 'Only the aggregate or the admitted set'),
             ('identity', 'Only identity, freshness or the global model’s consistency'), ('nothing', 'Nothing')]


def check_object(r):
    c = set(r['claim_checked']['codes'])
    if c & {'CL1', 'CL2', 'CL3'}:
        return 'content'
    if c & {'AG1', 'AG2'}:
        return 'aggregate'
    if c:
        return 'identity'
    return 'nothing'


def t_crosstab(d, s):
    A = load_class('approaches')
    ids = approach_ids(d)
    rows = []
    for sk, slab in SEES_LABEL:
        cells = []
        for ok, _ in OBJ_LABEL:
            grp = sorted([i for i in ids if SEES[i] == sk and check_object(A[i]) == ok],
                         key=lambda i: (year(d, i), d['refs'][i]['narrative_ieee']))
            cells.append('; '.join(f'[@{i}]' + ('*' if A[i]['trust_anchor']['value'].startswith('proof') else '')
                                   for i in grp) or NO)
        rows.append([slab] + cells)
    cols = [{'header': 'What the checking party sees of each update', 'width': 2126}] + \
           [{'header': lab, 'width': 1725, 'align': 'center'} for _, lab in OBJ_LABEL]
    return {'caption': f'What the checking party sees of each update, against what it checks, for the {len(ids)} compared approaches.',
            'columns': cols, 'rows': rows, 'font_size': 7.5,
            'note': '* = the check rests on a zero-knowledge proof. The claims follow Rizzini et al.: CL1 data binding, CL2 '
                    'training, CL3 admissibility; AG1 admitted set, AG2 aggregation.'}


# ------------------------------------------------------------------ deployment and evaluation of the approaches
# Short forms of the V16 classification records (classify/approaches/<ID>.json), for the table.
DEPLOY = {  # ledger nodes run on; costs measured on; data; clients; runs; attacks implemented
    'N001': ('edge servers (design)', 'desktop', 'CIFAR-10, 20 Newsgroups', '30', 'n.s.', NO),
    'N002': ('Ethereum nodes', 'cloud VM', 'none named', 'n.s.', 'n.s.', NO),
    'N003': ('aggregators off-chain', 'server; emulated WAN', 'MNIST, CIFAR-10', '10–100', 'n.s.', 'noise'),
    'N004': ('private chain (VMs)', 'cloud VMs', 'MedMNIST', '10', 'n.s.', 'label flipping'),
    'N005': ('simulated miners', 'server', 'MNIST, EMNIST, F-MNIST, CIFAR-10', '20–200', 'n.s.', 'noise, Sybil, label flipping, backdoor'),
    'N006': ('private Ethereum, one host', 'desktop', 'MNIST, F-MNIST', '10–50', 'n.s.', 'arbitrary updates, label flipping'),
    'N007': ('simulated (Spark)', 'Spark cluster', 'Adult', 'n.s.', '15 (timing)', NO),
    'N008': ('the devices (PoW)', 'Raspberry Pi', 'MNIST', '2–6', 'n.s.', NO),
    'N009': ('the devices (PoW)', 'Raspberry Pi', 'KDD Cup 1999', '2–6', 'n.s.', NO),
    'N010': ('SGX servers (simulated)', 'cloud VM with SGX', 'MNIST, F-MNIST, CIFAR-10', '2–40', 'n.s.', NO),
    'N011': ('authority, publishers, edge nodes', 'laptop-class PC', 'MNIST, F-MNIST, CIFAR-10', '100', 'n.s.', 'noise'),
    'N012': ('permissioned validators', 'workstation', 'MNIST', '3–6', 'n.s.', 'gradient inversion'),
    'N013': ('publisher and edge servers', 'simulation only', 'house prices, loans', '3–7', 'n.s.', 'data poisoning, tampering'),
    'N014': ('Fabric peers of the organisations', 'server', 'MNIST, F-MNIST, CIFAR-10', '20', 'n.s.', 'backdoor, model poisoning'),
    'N015': ('consortium nodes (simulated)', 'laptop', 'none', '10³–10⁷ (simulated)', '10', NO),
    'N016': ('base stations, access points', 'desktop', 'MNIST, CIFAR-10', '100–10,000', 'n.s.', 'membership inference'),
    'N017': ('consortium committee', 'workstation', 'California housing', '100–500', 'n.s.', NO),
    'N018': ('base stations (emulated)', 'desktop (Mac Mini)', 'MNIST, F-MNIST, CIFAR-10, SVHN', '100', 'n.s.', 'label flipping, random updates'),
    'N019': ('shore validators', 'desktop', 'AIS tracks, Ocean-of-Things, Edge-IIoTset', '10', 'n.s.', 'inference, replay (method n.s.)'),
    'N020': ('roadside units', 'compute node, cloud VM', 'DelDOT, METR-LA', '5–35', '30 (hashing)', NO),
    'N021': ('elected committee', 'desktop', 'EMNIST, MNIST, F-MNIST', '100–200', 'n.s.', 'backdoor, crafted gradients, Sybil'),
    'O033': ('Fabric committee servers', 'server', 'CIFAR-100, TinyImageNet', '20', 'n.s.', 'label flipping, model scaling'),
    'O083': ('Fabric or private Ethereum', 'Raspberry Pi (named)', 'unnamed', 'n.s.', 'n.s.', NO),
}


def t_deploy(d, s):
    A = load_class('approaches')
    ids = sorted(approach_ids(d), key=lambda i: (year(d, i), d['refs'][i]['narrative_ieee']))
    rows = []
    for i in ids:
        nodes, cost, data, clients, runs, attacks = DEPLOY[i]
        rows.append([f'[@{i}]', A[i]['client_tier']['value'].replace('not stated', 'n.s.'), nodes, cost, data, clients, runs, attacks])
    cols = [{'header': 'Ref.', 'width': 560}, {'header': 'Who trains', 'width': 880}, {'header': 'Ledger runs on', 'width': 1500},
            {'header': 'Costs measured on', 'width': 1260}, {'header': 'Data', 'width': 1700},
            {'header': 'Clients', 'width': 850, 'align': 'center'}, {'header': 'Runs', 'width': 700, 'align': 'center'},
            {'header': 'Attacks implemented', 'width': 1576}]
    return {'caption': f'Deployment and evaluation of the {len(ids)} compared approaches.',
            'columns': cols, 'rows': rows, 'font_size': 7,
            'note': 'Who trains: the party that runs local training (organisation = hospitals, firms or other silos). Runs: '
                    'number of repetitions or seeds; n.s. = not stated. F-MNIST = Fashion-MNIST; noise = updates replaced '
                    'or perturbed with random noise; VM = virtual machine; WAN = wide-area network.'}


def t_fabric(d, s):
    A = load_class('approaches')
    ids = approach_ids(d)
    hm = sum(1 for i in ids if A[i]['trust_anchor']['value'] == 'honest-majority committee or validators')
    rows = [
        ['Radio links can be jammed selectively from one node [@O022]; jamming of 5G New Radio can be detected at the user side [@O025]; a Wi-Fi denial of service keeps a station off its access point for up to 5,370 s [@O027]',
         'Honest devices miss rounds; selection and reputation mechanisms can mistake them for free riders, and an attacker can steer who is selected',
         'No approach evaluates learning under jamming or attack-induced dropouts; one simulates dropouts as failures [@N017]'],
        ['Energy-depletion attacks exhaust Zigbee, 5G and Wi-Fi devices [@O016; @O024; @O027]',
         'Devices leave the federation; proving and mining add their own energy cost',
         'None measures device energy; in two, the devices themselves mine proof-of-work blocks [@N008; @N009]'],
        ['Link protection fails in practice: BLE pairing [@O017], the Zigbee network key [@O016], WPA3-Personal on IoT boards [@O026]; eavesdropping is the physical-layer threat most likely to cost privacy [@O005]',
         'Updates in transit, and on the ledger, can be read unless they are protected end to end',
         f"{sum(1 for i in ids if d['onchain'].get(i) == 'U')} write updates on-chain in plaintext or only noised"],
        ['Memory-safety flaws cause most vulnerabilities of consumer wireless devices [@O015]; compromised devices feed botnets [@salim2020]',
         'Many registered devices can be compromised at once, which defeats checks that assume an honest majority',
         f'{hm} of the {len(ids)} checks rely on an honest majority of miners, a committee or validators'],
        ['Devices can be identified by radio fingerprints [@O014], and malicious nodes detected at the physical layer [@O013]',
         'Participation can be bound to a device identity, which stops fake nodes',
         'None binds participation to a device identity; two evaluate fake nodes [@N005; @N021]'],
        ['LPWAN data rates are at most about 1 Mbit/s [@O020]',
         'Uploading whole models each round is costly; gateways acting as clients, or short proofs instead of models, relieve the link',
         f"IoT devices train in {sum(1 for i in ids if A[i]['client_tier']['value'] == 'IoT device')}, but none states the link rate it needs"],
        ['IoT trust schemes rarely support heterogeneous devices [@O052]',
         'Reputation that penalises late or missing updates punishes poorly connected devices',
         'Reputation weights aggregation or rewards in several approaches [@N011; @N013; @N021]; one folds bandwidth into reputation [@N011]'],
    ]
    return {'caption': 'Findings about the NG-IoT fabric, their consequences for learning, and how the compared approaches treat them.',
            'columns': [{'header': 'Finding about the fabric', 'width': 3300}, {'header': 'Consequence for learning', 'width': 2926},
                        {'header': 'In the compared approaches', 'width': 2800}],
            'rows': rows, 'font_size': 7.5}


def approach_stats(d, s):
    A = load_class('approaches')
    ids = approach_ids(d)
    C = d['coding']
    s['appr_n'] = len(ids)
    anc = collections.Counter(A[i]['trust_anchor']['value'] for i in ids)
    s['appr_single'] = anc['single party']
    s['appr_hm'] = anc['honest-majority committee or validators']
    s['appr_noncol'] = anc['non-colluding servers']
    s['appr_hw'] = anc['hardware vendor']
    s['appr_proof'] = anc['proof soundness (trusted set-up)'] + anc['proof soundness (transparent)']
    s['appr_nocheck'] = anc['none']
    s['appr_anyone'] = sum(1 for i in ids if A[i]['verifiable_by']['value'] == 'anyone')
    s['appr_content'] = sum(1 for i in ids if check_object(A[i]) == 'content')
    s['appr_content_clear'] = sum(1 for i in ids if check_object(A[i]) == 'content' and SEES[i] == 'clear')
    s['appr_content_hidden'] = sum(1 for i in ids if check_object(A[i]) == 'content' and SEES[i] == 'hidden')
    for k in 'PSCRDI':
        s['appr_ev_' + k] = sum(1 for i in ids if A[i]['threats'][k] == 'evaluated')
        s['appr_cl_' + k] = sum(1 for i in ids if A[i]['threats'][k] != 'none')
    tier = collections.Counter(A[i]['client_tier']['value'] for i in ids)
    s['appr_client_iot'] = tier['IoT device']
    s['appr_client_gwedge'] = tier['gateway'] + tier['edge server']
    s['appr_client_org'] = tier['organisation']
    s['appr_client_ns'] = tier['not stated']
    s['appr_cost_device'] = sum(1 for i in ids if 'raspberry' in DEPLOY[i][1].lower() or 'jetson' in DEPLOY[i][1].lower()
                                or 'phone' in DEPLOY[i][1].lower())
    oc = collections.Counter(d['onchain'].get(i) for i in ids)
    for k in 'UEGC':
        s['appr_oc_' + k] = oc[k]
    mech = lambda i, codes: bool(set(C[i]['privacy_mechanisms']) & codes)
    s['appr_he'] = sum(1 for i in ids if mech(i, {'HE', 'FHE'}))
    s['appr_dp'] = sum(1 for i in ids if mech(i, {'DP', 'LDP'}))
    s['appr_ss'] = sum(1 for i in ids if mech(i, {'secret_sharing', 'SMPC', 'secure_aggregation'}) or any('masking' in m for m in C[i]['privacy_mechanisms']))
    s['appr_tee'] = sum(1 for i in ids if mech(i, {'TEE'}))
    s['appr_zkp'] = sum(1 for i in ids if mech(i, {'ZKP'}))
    for r in 'ARVE':
        s['appr_role_' + r] = sum(1 for i in ids if r in LEDGER_ROLES[i][1].split())
    return s


def trend_stats(d, s):
    C = d['coding']
    hide = {'DP', 'LDP', 'HE', 'FHE', 'SMPC', 'secret_sharing', 'secure_aggregation', 'TEE', 'ZKP'}
    prim = [i for i in d['included'] if kind(d, i) == 'primary']
    led = [i for i in prim if C[i]['ledger'].get('used')]
    priv = lambda i: bool(set(C[i]['privacy_mechanisms']) & hide) or any('masking' in m for m in C[i]['privacy_mechanisms'])
    early = [i for i in led if year(d, i) <= 2021]
    recent = [i for i in led if year(d, i) >= 2022]
    s['bc_early'], s['bc_recent'] = len(early), len(recent)
    s['bc_early_priv'] = sum(1 for i in early if priv(i))
    s['bc_recent_priv'] = sum(1 for i in recent if priv(i))
    pre = [i for i in led if year(d, i) < 2024]
    post = [i for i in led if year(d, i) >= 2024]
    s['ledger_pre2024'], s['ledger_2024'] = len(pre), len(post)
    s['oc_C_pre2024'] = sum(1 for i in pre if d['onchain'].get(i) == 'C')
    s['oc_C_2024'] = sum(1 for i in post if d['onchain'].get(i) == 'C')
    return s


_V15_STATS = stats


def stats(d):          # noqa: F811  (the V16 statistics: V15's, corrected and extended)
    s = _V15_STATS(d)
    s = evidence_stats(d, s)
    s = approach_stats(d, s)
    s = trend_stats(d, s)
    if (CLASS / 'surveys').exists():
        S = load_class('surveys')
        ids = closest_ids(d)
        s['cmp16_n'] = len(ids)
        s['cmp16_sys'] = sum(1 for i in ids if S[i]['method']['mark'] == '✓')
    for k in ('appr_rpi', 'appr_C', 'appr_updates', 'appr_G', 'appr_agg', 'appr_role_I', 'appr_none', 'zk_client',
              'cmp_n', 'cmp_full', 'cmp_best', 'cmp_ver', 'cmp_reg', 'cmp_sys', 'cmp_eval', 'cmp_iot'):
        s.pop(k, None)          # V15 counts over its own sets; V16 text must not use them
    return s


ABBREVIATIONS16 = [a for a in V15.ABBREVIATIONS if a[0] not in ('DSR', 'RQ', 'SLR', 'IC / EC', 'QP / QS')] + [
    ('AES', 'Advanced Encryption Standard'),
    ('gNB', '5G base station (next-generation Node B)'),
    ('IC / EC', 'Inclusion / exclusion criterion'),
    ('LoRaWAN', 'Long Range wide-area network'),
    ('LTE-M', 'Long-Term Evolution for machines'),
    ('QP / QS', 'Quality criterion for primary / secondary studies'),
]
ABBREVIATIONS16.sort(key=lambda a: a[0].lower())


def t_abbreviations16():
    t = V15.t_abbreviations()
    half = (len(ABBREVIATIONS16) + 1) // 2
    left, right = ABBREVIATIONS16[:half], ABBREVIATIONS16[half:]
    rows = []
    for k in range(half):
        a = left[k]
        b = right[k] if k < len(right) else ('', '')
        rows.append([a[0], a[1], b[0], b[1]])
    t['rows'] = rows
    return t


def tables(d, s):      # noqa: F811
    t = {
        'abbreviations': t_abbreviations16(),
        'questions': t_questions16(),
        'keywords': V15.t_keywords(),
        'searchrun': t_searchrun(d, s),
        'criteria': V15.t_criteria(),
        'quality': t_quality16(d, s),
        'extraction': V15.t_extraction(),
        'mechanisms': t_mechanisms16(),
        'verification': t_verification(),
        'threatmodel': t_threatmodel(),
        'approaches': t_approaches16(d, s),
        'crosstab': t_crosstab(d, s),
        'fabric': t_fabric(d, s),
        'deploy': t_deploy(d, s),
        'gaps': t_gaps(d, s),
        'appendix': t_appendix(d, s),
    }
    t['surveys'] = t_surveys_cmp16(d, s)
    t['concordance'] = t_concordance(d, s)
    return t


def figures(d, s):     # noqa: F811
    return {
        'prisma': {'file': 'fig-prisma.png', 'caption': 'Selection of studies.', 'width_in': 6.3},
        'overview': {'file': 'fig-overview.png', 'caption': 'Included studies (a) per year of publication and (b) per theme, by study type.', 'width_in': 6.0},
        'taxonomy': {'file': 'fig-taxonomy.png', 'caption': 'Taxonomy of privacy-preserving and verifiable FL for NG-IoT. Numbers give the primary studies classified under each leaf (of 66; a study can fall under several leaves); threats are counted as the studies claim to address them.', 'width_in': 6.3},
        'architecture': {'file': 'fig-architecture.png', 'caption': 'Reference architecture: where the reviewed designs place their mechanisms on the NG-IoT tiers, and where the threats enter. The ledger may hold local updates in plaintext or noised (U), encrypted updates (E), global models (G) or only commitments and proofs (C).', 'width_in': 6.3},
        'mechanisms': {'file': 'fig-mechanisms.png', 'caption': 'Privacy mechanisms used by the primary studies, with and without a ledger. A study can use several mechanisms.', 'width_in': 5.8},
        'challenges': {'file': 'fig-challenges.png', 'caption': 'Open challenges and the number of primary and secondary studies that raise each. A study can raise several challenges; challenges outside the eighteen categories are not shown.', 'width_in': 6.0},
    }


# ------------------------------------------------------------------ comparison with the closest surveys (V16)
# Selection rule: included surveys published from 2022 that treat, as a subject of their own, either blockchain-based
# FL (ledger ✓) or the checking of updates by proofs or by input validation (P or V among the check families).
SURVEY_COLS = [('devices', 'Dev.'), ('network', 'Net.'), ('ledger', 'Ledger'), ('checks', 'Checks'), ('trust', 'Trust'),
               ('onchain_law', 'On-chain, law'), ('evaluation', 'Eval.'), ('method', 'Method')]
THIS_WORK16 = {'devices': '✓', 'network': '✓', 'ledger': '✓', 'checks': 'R C H P V', 'trust': '✓', 'onchain_law': '✓',
               'evaluation': '✓', 'method': PARTIAL}


def closest_ids(d):
    S = load_class('surveys')
    return [i for i, r in S.items() if year(d, i) >= 2022 and
            (r['ledger']['mark'] == '✓' or set(r['checks']['families']) & {'P', 'V'})]


def studies_cell(r):
    st = r['studies']
    n = str(st.get('n') or '')
    m = re.search(r'\d[\d,]*', n)
    if not m:
        return 'n.s.'
    pre = '>' if re.search(r'more than|over|\+', n) else '~' if 'about' in n else ''
    per = re.findall(r'(?:19|20)\d\d', str(st.get('period') or ''))
    return pre + m.group(0) + ('†' if st.get('derived') else '') + (f" ({per[0]}–{per[-1][2:]})" if len(per) >= 2 else '')


def t_surveys_cmp16(d, s):
    S = load_class('surveys')
    fp = SRC16 / 'focus.json'
    focus = json.loads(fp.read_text()) if fp.exists() else {}
    ids = sorted(closest_ids(d), key=lambda i: (year(d, i), d['refs'][i]['narrative_ieee']))
    rows = []
    for i in ids:
        r = S[i]
        f = re.sub(r'^(Survey of|Systematic review of|SoK:)\s*', '', focus.get(i, '')).strip()
        f = f[:1].upper() + f[1:]
        cells = []
        for key, _ in SURVEY_COLS:
            cells.append(' '.join(r['checks']['families']) or NO if key == 'checks' else r[key]['mark'])
        rows.append([f'@{i}', str(year(d, i)), f, studies_cell(r)] + cells)
    own = ['This work', '2026', 'Privacy-preserving, verifiable FL on ledgers for NG-IoT',
           f"{s['primary']} + {s['secondary']}; {s['appr_n']} compared (2020–26)"] + [THIS_WORK16[k] for k, _ in SURVEY_COLS]
    rows.append([{'runs': [{'text': x, 'bold': True}], 'fill': 'EEF5FD'} for x in own])
    cols = [{'header': 'Survey', 'width': 880}, {'header': 'Year', 'width': 520, 'align': 'center'},
            {'header': 'Focus', 'width': 1886}, {'header': 'Studies (period)', 'width': 900, 'align': 'center'}]
    widths = {'devices': 500, 'network': 500, 'ledger': 640, 'checks': 800, 'trust': 520, 'onchain_law': 620,
              'evaluation': 500, 'method': 760}
    cols += [{'header': h, 'width': widths[k], 'align': 'center'} for k, h in SURVEY_COLS]
    return {'caption': 'Comparison of this work with the closest surveys (2022–2026).',
            'columns': cols, 'rows': rows, 'font_size': 7,
            'note': 'Selection: the included surveys published from 2022 that treat blockchain-based FL, or the checking of '
                    'updates by proofs or input validation, as a subject of their own. ✓ = a subject of its own (a section, a '
                    'taxonomy branch, a table or a comparison axis); ◐ = treated in part; – = absent or mentioned in passing. '
                    'Studies (period): the number of studies reviewed and the period covered, as stated; † = counted from the '
                    'survey’s tables or references; n.s. = not stated; for this work, primary + secondary studies, and the approaches compared in Section V-A. Dev. = '
                    'constraints of IoT devices analysed or measured; Net. = threats at the network or physical layer; Checks = '
                    'families of checks on updates treated: R robust aggregation, C miners, committee or peers, H hardware '
                    'attestation, P proofs, V input validation for secure aggregation; Trust = checks classified by whom they '
                    'trust; On-chain, law = what a ledger should hold judged against data-protection law; Eval. = evaluation '
                    'practice analysed across studies (◐ = catalogued); Method: ✓ = search strategy, criteria and per-source '
                    'counts reported, ◐ = reported in part. This work reports its strategy and criteria but not per-source '
                    'counts of its executed search (Section III-B).'}


# ------------------------------------------------------------------ what the closest surveys conclude
def t_concordance(d, s):
    rows = [
        ['Blockchain-based FL resists poisoning', 'All 31 designs rated by @O100 claim it; @S006 and @S007 doubt it (slow and clean-label poisoning, poisoning by devices)',
         f"Poisoning is claimed by {s['appr_cl_P']} of the {s['appr_n']} compared approaches and tested with an implemented attack by {s['appr_ev_P']}", 'Qualified: mostly claimed'],
        ['Checking updates remains open, above all when computation is off-chain or updates are encrypted', '[@S011; @S007; @S015; @S018]',
         f"{s['appr_content']} approaches check the content of each update, {s['appr_content_clear']} of them in the clear; one checks hidden updates with a public proof [@N015]", 'Agrees'],
        ['The ledger exposes the updates it stores', '[@O100; @S007; @S023]',
         f"{s['oc_updates']} of the {s['prim_ledger']} ledger-based studies write local updates on-chain, and encryption does not take them out of data protection [@edpb2026]", 'Agrees; extended to the law'],
        ['Ledgers and cryptography are heavy for IoT devices', '[@S006; @S007; @S011; @S030]',
         f"Costs are measured on IoT hardware for {s['appr_cost_device']} of the {s['appr_n']} approaches; no study measures device energy", 'Agrees; evidence thin'],
        ['Proof generation is the main obstacle to verifiable learning', '[@S015; @S026; @S032]',
         'Proofs are measured on servers, cloud instances and one phone [@O097]; none on IoT gateways', 'Agrees'],
        ['Fake identities need an external trust anchor', '[@S032; @S023]',
         'No approach binds participation to a device identity; two test fake nodes [@N005; @N021]', 'Agrees'],
        ['Proof of work is the mainstream consensus', 'Designs of 2018–2021 [@O100]; 102 studies to 2023 [@S018]',
         'Three of the compared approaches of 2022–2026 use proof of work; most use consortium or permissioned ledgers', 'Differs: a move away from proof of work'],
        ['No single privacy mechanism suffices', '[@S015; @S030]', 'The compared approaches combine HE, DP, secret sharing and masking', 'Agrees'],
    ]
    return {'caption': 'Conclusions of the related surveys, set against the evidence of this survey.',
            'columns': [{'header': 'Conclusion of the surveys', 'width': 2400}, {'header': 'Surveys', 'width': 2300},
                        {'header': 'Evidence of this survey', 'width': 2926}, {'header': 'Agreement', 'width': 1400}],
            'rows': rows, 'font_size': 7.5}
