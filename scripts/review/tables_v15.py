"""Tables, statistics and figure registry of the V15 review.

The synthesis records (one per study) are shared with V14 in _src/V14; V15 has its own eligibility decisions,
PRISMA counts and search check in _src/V15, because its review period starts in January 2020. Statistics and most
helpers come from tables_v14 and are recomputed over the V15 set of included studies."""
import collections, json, re
import tables_v14 as V14
from tables_v14 import kind, year, norm_dataset, THEMES, CHALLENGE, challenge_counts, YES, NO  # noqa: F401

SRC15 = V14.ROOT / 'myliteraturereviewpaper' / '_src' / 'V15'


def load():
    d = V14.load()
    ex = json.loads((SRC15 / 'screening.json').read_text())['excluded']
    d['excluded'] = ex
    d['included'] = [i for i in d['papers'] if i not in ex]
    d['prisma'] = json.loads((SRC15 / 'prisma.json').read_text())
    q = json.loads((SRC15 / 'search-check.json').read_text())
    d['qgs'] = {'per_string': {str(n): q['per_string'][k] for n, k in enumerate('ABCD', 1)},
                'combined': q['combined'], 'n': q['n'], 'missed': q['missed']}
    return d


# threat groups of V15: fake nodes and collusion, and denial of service and the single point of failure, are kept apart
THREATS15 = collections.OrderedDict([
    ('P', ('Poisoning', {'data_poisoning', 'model_poisoning', 'backdoor', 'byzantine'})),
    ('S', ('Fake nodes (Sybil)', {'sybil_fake_nodes'})),
    ('C', ('Collusion', {'collusion'})),
    ('R', ('Free riding', {'free_riding'})),
    ('D', ('DoS / DDoS', {'dos_ddos', 'jamming'})),
    ('I', ('Inference', {'membership_inference', 'property_attribute_inference', 'reconstruction_inversion'})),
])
# ledger-based studies whose proofs concern the clients' updates themselves (reviewer's reading of each design):
# N002 proves correct training, N015 a norm bound on each update, O083 the authenticity of each update
ZK_CLIENT = ['N002', 'N015', 'O083']


def stats(d):
    s = V14.stats(d)
    C = d['coding']
    for n in '1234':
        s['qgs_' + n] = d['qgs']['per_string'][n]
    s['qgs_missed'] = len(d['qgs']['missed'])
    prim = [i for i in d['included'] if kind(d, i) == 'primary']
    ledger = [i for i in prim if C[i]['ledger'].get('used')]
    for k, (_, codes) in THREATS15.items():
        s['lt_' + k] = sum(1 for i in ledger if set(C[i]['threats']) & codes)
    s['lt_spof'] = sum(1 for i in ledger if 'single_point_of_failure' in C[i]['threats'])
    s['zk_client'] = len([i for i in ZK_CLIENT if i in ledger])
    s['prim_ledger_zkp'] = sum(1 for i in ledger if 'ZKP' in C[i]['privacy_mechanisms'])
    s['surveys_zkp'] = 6
    per, full, best = cmp_counts(d)
    s['cmp_n'] = len(CLOSEST)
    s['cmp_full'] = full
    s['cmp_best'] = best
    s['cmp_ver'] = per['Update verif.']
    s['cmp_reg'] = per['Data prot. law']
    s['cmp_sys'] = per['Syst. method']
    s['cmp_eval'] = per['Evalu-ation']
    s['cmp_iot'] = per['IoT / edge']
    s['appr_n'] = len(APPROACH)
    mech = lambda i, codes: bool(set(C[i]['privacy_mechanisms']) & codes)
    s['appr_he'] = sum(1 for i in APPROACH if mech(i, {'HE', 'FHE'}))
    s['appr_dp'] = sum(1 for i in APPROACH if mech(i, {'DP', 'LDP'}))
    s['appr_ss'] = sum(1 for i in APPROACH if mech(i, {'secret_sharing', 'SMPC', 'secure_aggregation'}))
    s['appr_tee'] = sum(1 for i in APPROACH if mech(i, {'TEE'}))
    s['appr_zkp'] = sum(1 for i in APPROACH if mech(i, {'ZKP'}))
    s['appr_rpi'] = sum(1 for i in APPROACH if C[i]['evaluation'].get('real_device_cost') is True)
    oc = collections.Counter(d['onchain'].get(i) for i in APPROACH)
    s['appr_C'] = oc['C']
    s['appr_updates'] = oc['U'] + oc['E']
    s['appr_G'] = oc['G']
    s['appr_agg'] = sum(1 for i in APPROACH if 'A' in APPROACH[i][1])
    for r in 'ARVI':
        s['appr_role_' + r] = sum(1 for i in APPROACH if r in APPROACH[i][1].split())
    s['appr_none'] = sum(1 for i in APPROACH if APPROACH[i][2] == 'None')
    s['n_T4_p_early'] = sum(1 for i in prim if C[i]['theme'] == 'T4' and year(d, i) <= 2021)
    return s


# ------------------------------------------------------------------ abbreviations used in the text and tables
ABBREVIATIONS = [
    ('5G / 6G', 'Fifth / sixth generation of mobile networks'),
    ('AI', 'Artificial intelligence'),
    ('BCFL', 'Blockchain-based federated learning'),
    ('BFT', 'Byzantine fault tolerance'),
    ('BLE', 'Bluetooth Low Energy'),
    ('CKKS', 'Cheon–Kim–Kim–Song homomorphic encryption scheme'),
    ('DAG', 'Directed acyclic graph'),
    ('DDoS', 'Distributed denial of service'),
    ('DFL', 'Decentralised federated learning'),
    ('DP', 'Differential privacy'),
    ('DSR', 'Design science research'),
    ('EDPB', 'European Data Protection Board'),
    ('FHE', 'Fully homomorphic encryption'),
    ('FL', 'Federated learning'),
    ('GAN', 'Generative adversarial network'),
    ('GDPR', 'General Data Protection Regulation'),
    ('HE', 'Homomorphic encryption'),
    ('IC / EC', 'Inclusion / exclusion criterion'),
    ('IID', 'Independent and identically distributed'),
    ('IIoT', 'Industrial Internet of Things'),
    ('IoMT', 'Internet of Medical Things'),
    ('IoT', 'Internet of Things'),
    ('IPFS', 'InterPlanetary File System'),
    ('LDP', 'Local differential privacy'),
    ('LLM', 'Large language model'),
    ('LPWAN', 'Low-power wide-area network'),
    ('MEC', 'Multi-access edge computing'),
    ('ML', 'Machine learning'),
    ('NB-IoT', 'Narrowband Internet of Things'),
    ('NG-IoT', 'Next-generation Internet of Things'),
    ('NIZK', 'Non-interactive zero-knowledge (proof)'),
    ('PBFT', 'Practical Byzantine fault tolerance'),
    ('PoW', 'Proof of work'),
    ('PPML', 'Privacy-preserving machine learning'),
    ('PRISMA', 'Preferred Reporting Items for Systematic Reviews and Meta-Analyses'),
    ('QP / QS', 'Quality criterion for primary / secondary studies'),
    ('RQ', 'Research question'),
    ('SGX', 'Intel Software Guard Extensions'),
    ('SLR', 'Systematic literature review'),
    ('SMPC', 'Secure multi-party computation'),
    ('SoK', 'Systematisation of knowledge'),
    ('SQ', 'Survey question'),
    ('TEE', 'Trusted execution environment'),
    ('WPA3', 'Wi-Fi Protected Access 3'),
    ('ZKP', 'Zero-knowledge proof'),
    ('zk-SNARK', 'Zero-knowledge succinct non-interactive argument of knowledge'),
]


def t_abbreviations():
    half = (len(ABBREVIATIONS) + 1) // 2
    left, right = ABBREVIATIONS[:half], ABBREVIATIONS[half:]
    rows = []
    for i in range(half):
        a = left[i]
        b = right[i] if i < len(right) else ('', '')
        rows.append([a[0], a[1], b[0], b[1]])
    return {'caption': 'List of abbreviations.',
            'columns': [{'header': 'Abbreviation', 'width': 1250}, {'header': 'Meaning', 'width': 3263},
                        {'header': 'Abbreviation', 'width': 1250}, {'header': 'Meaning', 'width': 3263}],
            'rows': rows, 'font_size': 8}


# ------------------------------------------------------------------ comparison with the closest surveys
CLOSEST = [
    ('S006', 'Blockchain-based FL on resource-constrained devices'),
    ('S007', 'Blockchain-based FL for securing IoT'),
    ('S008', 'Blockchain-empowered FL: challenges and system models'),
    ('S011', 'Securing FL with blockchain (41 studies)'),
    ('S014', 'Blockchained FL across four IoT domains'),
    ('S015', 'Security and privacy of decentralised FL'),
    ('S018', 'Privacy in blockchain-based FL (102 studies)'),
    ('S021', 'Blockchain-backed FL aggregation for IIoT'),
    ('S023', 'Benefits and costs of blockchain-empowered FL'),
    ('S026', 'ZKP-based verifiable decentralised ML'),
    ('S030', 'Privacy-preserving ML for IoT across paradigms'),
    ('S031', 'Security, privacy and scalability of blockchain–IoT'),
    ('S032', 'Verifiable integrity claims in private FL'),
]
# surveys that treat the verification of model updates as a subject of its own (a section, taxonomy branch or table),
# read from their heading lists: S006 §III-A, S011 §5.3, S015 §VI, S026 (whole survey), S032 (whole SoK)
VERIFICATION = {'S006', 'S011', 'S015', 'S026', 'S032'}
CMP_COLS = [('IoT / edge', 'iot_edge', 'IoT / edge'), ('Privacy mech.', 'privacy_mechanisms', 'Priv. mech.'),
            ('Blockchain', 'blockchain', 'Block- chain'), ('Attacks, defences', 'attacks_defences', 'Att., def.'),
            ('Update verif.', None, 'Upd. verif.'), ('Evalu-ation', 'evaluation', 'Eval.'),
            ('Data prot. law', 'regulation', 'Data law'), ('Syst. method', None, 'Syst. meth.')]


def survey_marks(d, i):
    C = d['coding']
    cv = C[i]['survey']['covers']
    out = [bool(cv.get(key)) for _, key, _ in CMP_COLS if key]
    out.insert(4, i in VERIFICATION)
    out.append(C[i]['survey']['protocol'] == 'systematic')
    return out


def t_surveys_cmp(d, s):
    rows, marks_all = [], []
    for i, focus in sorted(CLOSEST, key=lambda x: (year(d, x[0]), d['refs'][x[0]]['narrative_ieee'])):
        m = survey_marks(d, i)
        marks_all.append(m)
        rows.append([f'@{i}', str(year(d, i)), focus] + [YES if x else NO for x in m])
    for j, (h, _, _) in enumerate(CMP_COLS):       # a column that no survey meets tells the reader nothing
        if not any(m[j] for m in marks_all):
            raise SystemExit(f'comparison column {h!r} is met by no survey')
    cols = [{'header': 'Survey', 'width': 1150}, {'header': 'Year', 'width': 480, 'align': 'center'},
            {'header': 'Focus', 'width': 2196}]
    cols += [{'header': hd, 'width': 650, 'align': 'center'} for _, _, hd in CMP_COLS]
    return {'caption': 'Comparison of the closest surveys (2023–2026).',
            'columns': cols, 'rows': rows, 'font_size': 7.5,
            'note': '✓ = treated as a subject of its own (a section, a branch of the taxonomy, a table or a comparison axis); '
                    '– = absent or mentioned only in passing. IoT / edge = the IoT, edge or 5G/6G setting; Priv. mech. = privacy '
                    'mechanisms; Att., def. = attacks and defences; Upd. verif. = how model updates or their aggregation are '
                    'checked; Eval. = frameworks, datasets, testbeds or metrics; Data law = the GDPR or other data-protection '
                    'law; Syst. meth. = a search strategy and selection criteria are reported.'}


def cmp_counts(d):
    """How many of the closest surveys meet each column, and how many meet all."""
    ms = [survey_marks(d, i) for i, _ in CLOSEST]
    per = {h: sum(1 for m in ms if m[j]) for j, (h, _, _) in enumerate(CMP_COLS)}
    return per, sum(1 for m in ms if all(m)), max(sum(m) for m in ms)


# ------------------------------------------------------------------ the 21 most recent blockchain-based approaches
# reviewer's classification from each study's synthesis record: ledger and consensus; roles of the ledger
# (A = aggregates in place of a server, R = records updates, models or proofs, V = verifies, I = incentives or
# reputation); what is checked and how; the party or assumption on which the check relies
APPROACH = {
    'N001': ('Consortium; stake-based committee', 'A R V I', 'Aggregate: polynomial commitments', 'Honest committee majority'),
    'N002': ('Ethereum smart contracts', 'A R V I', 'Client training: zk-SNARK', 'Trusted set-up'),
    'N003': ('State channel; BFT', 'A I', 'Updates: median scoring on shares', 'Honest aggregator majority'),
    'N004': ('Private chain; hash majority', 'A R', 'Models: encrypted inference', 'Cloud provider'),
    'N005': ('Simulated; proof of verification', 'A R V I', 'Updates: outlier test by miners', 'Honest miner majority'),
    'N006': ('Private Ethereum', 'R I', 'Updates: encrypted cosine to root data', 'Two non-colluding servers'),
    'N007': ('Simulated; Raft', 'R', 'None', '–'),
    'N008': ('Public; PoW', 'A R V I', 'Updates: checked by miners', 'Miners'),
    'N009': ('Public; PoW', 'A R V', 'Updates: cross-validated by miners', 'Miners'),
    'N010': ('Simulated; hash majority', 'A R', 'Aggregation: SGX attestation', 'SGX hardware'),
    'N011': ('Consortium; IPFS', 'R I', 'Workers: reputation, signatures', 'Key authority'),
    'N012': ('Private Ethereum', 'A R V', 'Key set-up: NIZK; public tally', 'Honest clients'),
    'N013': ('Consortium; PBFT', 'R V I', 'Models: peer evaluation', 'Honest peer majority'),
    'N014': ('Hyperledger Fabric', 'A R', 'Updates: distance-weighted aggregation', 'Endorsing peers'),
    'N015': ('Consortium', 'A R V', 'Updates: norm bound (ZKP)', 'Key authority'),
    'N016': ('Hyperledger Fabric', 'R V', 'Aggregates: redundant edge nodes', 'Honest edge-node majority'),
    'N017': ('Consortium; Algorand', 'A R V I', 'Aggregation: committee vote', 'Honest committee majority'),
    'N018': ('Consortium; PBFT', 'A R V', 'Updates: encrypted cosine and norm', 'Non-colluding helper server'),
    'N019': ('Permissioned; PBFT', 'A R V', 'Updates: signatures, freshness', 'Honest validator majority'),
    'N020': ('Fabric and DAG', 'R', 'Aggregation: SGX attestation', 'SGX hardware'),
    'N021': ('Committee PoW', 'A R V I', 'Updates: committee, cosine score', 'Committee'),
}


def threat_letters(c):
    th = set(c['threats'])
    return ' '.join(k for k, (_, codes) in THREATS15.items() if th & codes) or NO


OTHER_SHORT = {'N006': 'masking', 'N010': 'AES in transit', 'N014': 'data partitioning', 'N020': 'redaction'}
DATASET_SHORT = {'house price data set (HPD)': 'House prices', 'loan data set (LD)': 'Loans',
                 'Great Lakes Tracks AIS ship trajectory dataset': 'AIS ship tracks', 'DelDOT traffic flow': 'DelDOT traffic',
                 'METR-LA (207-sensor, four-month subset)': 'METR-LA', '20newsgroup': '20 Newsgroups',
                 'California Housing': 'California housing', 'Adult (UCI)': 'Adult'}


def priv_short(i, c):
    ms = [V14.PRIV_LABEL.get(m, m) for m in c['privacy_mechanisms'] if m != 'none' and not m.startswith('other')]
    if i in OTHER_SHORT:
        ms.append(OTHER_SHORT[i])
    return ', '.join(ms) if ms else NO


def t_approaches(d, s):
    C = d['coding']
    ids = sorted(APPROACH, key=lambda i: (year(d, i), d['refs'][i]['narrative_ieee']))
    rows = []
    for i in ids:
        c = C[i]
        ledger, roles, check, relies = APPROACH[i]
        e = c['evaluation']
        names = sorted(set(DATASET_SHORT.get(x, norm_dataset(x)) for x in e.get('datasets', [])), key=str.lower)
        ev = (', '.join(names) or 'No named dataset') + ('; RPi' if e.get('real_device_cost') is True else '')
        rows.append([f'[@{i}]', str(year(d, i)), priv_short(i, c), ledger, roles, check, relies, d['onchain'].get(i, '?'),
                     threat_letters(c), ev])
    cols = [{'header': 'Ref.', 'width': 560}, {'header': 'Year', 'width': 480, 'align': 'center'},
            {'header': 'Privacy', 'width': 900}, {'header': 'Ledger', 'width': 1150},
            {'header': 'Roles', 'width': 760, 'align': 'center'}, {'header': 'What is checked, and how', 'width': 1400},
            {'header': 'Check relies on', 'width': 1100}, {'header': 'On-chain', 'width': 560, 'align': 'center'},
            {'header': 'Threats', 'width': 820, 'align': 'center'}, {'header': 'Evaluation', 'width': 1296}]
    return {'caption': 'Comparison of recent blockchain-based privacy-preserving FL approaches (2022–2026).',
            'columns': cols, 'rows': rows, 'font_size': 7,
            'note': 'Privacy: DP / LDP = (local) differential privacy; HE / FHE = (fully) homomorphic encryption; SMPC = secure '
                    'multi-party computation; SS = secret sharing; SecAgg = secure aggregation; TEE = trusted execution; ZKP = '
                    'zero-knowledge proof; GAN = synthetic data from a generative adversarial network; Anon. = anonymisation. '
                    'Roles of the ledger: A = aggregates in place of a server; R = records updates, models or proofs; V = '
                    'verifies updates or their aggregation; I = incentives or reputation. On-chain: U = local updates in '
                    'plaintext or only noised; E = local updates encrypted or masked; G = global or aggregated models; C = only '
                    'commitments, hashes, proofs or payments. Threats addressed: P = poisoning; S = fake nodes (Sybil); '
                    'C = collusion; R = free riding; D = denial of service; I = inference. RPi = cost measured on '
                    'Raspberry Pi devices.'}


# ------------------------------------------------------------------ method tables
def t_questions():
    rows = [
        ['SQ1', 'What are the building blocks of PPML in NG-IoT, and how can they be classified?', 'To fix the concepts and a taxonomy that the rest of the review uses', 'Section IV'],
        ['SQ2', 'How do existing studies combine privacy mechanisms and blockchain with distributed learning, and which threats do they address?', 'To compare the approaches and find where they differ', 'Section V'],
        ['SQ3', 'Which tools, datasets and measures are used to build and evaluate these solutions, and what do they cost IoT devices?', 'To judge how strong and how realistic the evidence is', 'Section VI'],
        ['SQ4', 'Which trends and open challenges emerge, including those raised by data-protection law?', 'To identify research gaps and directions', 'Section VII'],
    ]
    return {'caption': 'Survey questions of this review.',
            'columns': [{'header': 'ID', 'width': 600}, {'header': 'Question', 'width': 4326},
                        {'header': 'Motivation', 'width': 2900}, {'header': 'Answered in', 'width': 1200}],
            'rows': rows, 'font_size': 8.5}


def t_keywords():
    rows = [
        ['L — Learning', '"federated learning" OR "decentrali?ed learning" OR "distributed learning" OR "split learning" OR "swarm learning" OR "machine learning" OR "deep learning" OR "edge intelligence"'],
        ['P — Privacy', 'privacy OR "homomorphic encryption" OR "multi-party computation" OR "secret sharing" OR "secure aggregation" OR "trusted execution" OR "zero-knowledge"'],
        ['A — Attacks on learning', 'poisoning OR backdoor OR Byzantine OR Sybil OR "free-riding" OR "membership inference" OR "inference attack"'],
        ['B — Ledger', 'blockchain OR "distributed ledger" OR "smart contract"'],
        ['T — Setting', '"Internet of Things" OR IoT OR IIoT OR "edge computing" OR "fog computing" OR 5G OR 6G OR Bluetooth OR Zigbee OR LoRaWAN OR WPA3'],
        ['S — Security', 'security OR attack* OR DDoS OR "denial of service" OR jamming'],
        ['G — Regulation', 'GDPR OR "General Data Protection Regulation" OR "right to be forgotten" OR unlearning'],
    ]
    return {'caption': 'Keyword groups used to build the search strings.',
            'columns': [{'header': 'Group', 'width': 1900}, {'header': 'Terms (searched in title, abstract and keywords)', 'width': 7126}],
            'rows': rows, 'font_size': 8.5,
            'note': 'Within a group the terms are joined by OR, and the four search strings combine the groups (Section III-B). '
                    '? stands for one character (decentralised or decentralized) and * for any ending.'}


def t_criteria():
    rows = [
        {'group': 'Inclusion criteria — all must hold'},
        ['IC1', 'Topic', 'The study addresses at least one of: (a) the privacy or security of machine learning, including the privacy mechanisms used for it and ledgers used to coordinate or secure it; (b) the NG-IoT fabric on which such learning runs — IoT, edge and 5G/6G infrastructure, its wireless technologies, or distributed learning at the edge — and its security; (c) the data-protection regulation of such systems.'],
        ['IC2', 'Study type', 'A primary study (a scheme, system or empirical study) or a secondary study (a survey, systematic review or systematisation of knowledge).'],
        ['IC3', 'Venue', 'Published in a journal, conference proceedings or magazine, or posted on a public preprint server.'],
        ['IC4', 'Period', 'Published between January 2020 and September 2026.'],
        ['IC5', 'Language and access', 'Written in English, with the full text available.'],
        {'group': 'Exclusion criteria — any one excludes'},
        ['EC1', 'Retracted', 'The study has been retracted by its publisher.'],
        ['EC2', 'Duplicate', 'A duplicate record, or an earlier version (e.g. a preprint) of a study whose published version is included.'],
    ]
    return {'caption': 'Inclusion and exclusion criteria.',
            'columns': [{'header': 'Code', 'width': 700}, {'header': 'Criterion', 'width': 1700}, {'header': 'Definition', 'width': 6626}],
            'rows': rows, 'font_size': 8.5}


def t_extraction():
    rows = [
        ['Bibliographic data', 'Authors, year, venue, publication type, DOI', 'All'],
        ['Study type', 'Primary or secondary; kind of contribution and of evaluation', 'All'],
        ['Aims and contributions', 'Stated aims, questions and contributions', 'SQ2'],
        ['Setting', 'IoT tier, network technology and application domain', 'SQ1, SQ2'],
        ['Learning', 'Paradigm, model, aggregation, data distribution', 'SQ1, SQ2'],
        ['Privacy', 'Mechanisms, what they protect, parameters, trust assumptions', 'SQ1, SQ2'],
        ['Ledger', 'Type, platform, consensus, role, on-chain content, incentives', 'SQ1, SQ2'],
        ['Threats and defences', 'Adversary model, attacks addressed, defences, what is checked and whom the check trusts', 'SQ2'],
        ['Evaluation', 'Datasets, tools, hardware, number of clients, measures, repetitions, code', 'SQ3'],
        ['Results and limitations', 'Main results with figures; limitations stated by the authors', 'SQ2, SQ3'],
        ['Open issues', 'Open challenges and future directions, classified into eighteen categories', 'SQ4'],
        ['Surveys only', 'Period and number of studies covered, search method, topics treated', 'Section II'],
    ]
    return {'caption': 'Data extraction form.',
            'columns': [{'header': 'Field', 'width': 2000}, {'header': 'Content', 'width': 5526}, {'header': 'Used for', 'width': 1500}],
            'rows': rows, 'font_size': 8.5}


def t_quality(d, s):
    t = V14.t_quality(d, s)
    ren = {'SQ-a': 'QS1', 'SQ-b': 'QS2', 'SQ-c': 'QS3', 'SQ-d': 'QS4'}
    rows = []
    for r in t['rows']:
        if isinstance(r, list):
            if r[0] in ('PQ8', 'SQ-e'):       # PQ8 is reported in Section VI-C; SQ-e is met by every survey
                continue
            r[0] = ren.get(r[0], r[0].replace('PQ', 'QP'))
        rows.append(r)
    t['rows'] = rows
    t['columns'][2]['width'] = 2726
    t['caption'] = 'Quality assessment criteria and the number of included studies that meet each.'
    return t


def t_mechanisms():
    return {
        'caption': 'Privacy mechanisms for distributed learning: what each protects, whom it trusts and what it costs.',
        'columns': [{'header': 'Mechanism', 'width': 1500}, {'header': 'What it protects', 'width': 2300},
                    {'header': 'Whom it must trust', 'width': 1900}, {'header': 'Main cost', 'width': 1900},
                    {'header': 'Surveys', 'width': 1426}],
        'rows': [
            ['Differential privacy (central or local)', 'Individual records against inference from updates or the model, by adding calibrated noise; local DP adds the noise on the device', 'Central DP: the aggregator that adds the noise; local DP: no one', 'Accuracy falls as the privacy budget ε shrinks', '[@O060; @S024]'],
            ['Homomorphic encryption (additive or fully homomorphic)', 'Updates while the aggregator computes on them in encrypted form', 'The holder of the decryption key (often a key authority)', 'Computation and ciphertext size, highest for fully homomorphic schemes', '[@O077; @O076]'],
            ['Secure multi-party computation and secret sharing', 'Inputs of each party during a joint computation; each share alone reveals nothing', 'A threshold of the parties not to collude', 'Communication rounds and messages between parties', '[@O077; @S020]'],
            ['Secure aggregation (pairwise masking)', 'Individual updates: the server learns only their sum', 'Enough clients to stay online and not to collude with the server', 'Extra rounds; recovery when clients drop out', '[@S020; @S024]'],
            ['Trusted execution environment', 'Code and data inside a hardware-isolated enclave, even from the host', 'The hardware vendor and the attestation service', 'Enclave memory limits; exposure to side channels', '[@O089; @S032]'],
            ['Zero-knowledge proof', 'The witness (e.g. an update or credential) while proving a statement about it', 'The soundness of the proof system and, for some systems, the set-up', 'Prover time and memory; proof size and verification cost', '[@S025; @S026]'],
        ],
        'font_size': 8,
    }


def t_gaps(d, s):
    rows = [
        ['G1 Checking updates without seeing them', 'Proofs about client updates are established for secure aggregation with servers, but only {{N:zk_client}} of the {{N:prim_ledger}} ledger-based studies prove properties of client updates in zero knowledge; most rely on a trusted party', 'RQ; H2, H3'],
        ['G2 Little testing on IoT hardware', '{{N:learn_real_device}} of the {{N:learn_prim}} learning studies measure their cost on IoT or edge hardware; none measures proof generation there', 'RQ1; H1'],
        ['G3 Networks assumed rather than tested', 'No primary study evaluates learning over an emulated IoT or 5G network', 'A later phase'],
        ['G4 Personal data on the ledger', 'Only {{N:oc_C}} of the {{N:prim_ledger}} ledger-based studies keep models and updates off-chain', 'Requirement R1'],
    ]
    return {'caption': 'Research gaps identified by this review and how the proposed research addresses them.',
            'columns': [{'header': 'Gap', 'width': 2300}, {'header': 'Evidence from this review', 'width': 5026},
                        {'header': 'Addressed by', 'width': 1700}],
            'rows': rows, 'font_size': 8}


def tables(d, s):
    return {
        'abbreviations': t_abbreviations(),
        'surveys': t_surveys_cmp(d, s),
        'questions': t_questions(),
        'keywords': t_keywords(),
        'criteria': t_criteria(),
        'extraction': t_extraction(),
        'quality': t_quality(d, s),
        'mechanisms': t_mechanisms(),
        'approaches': t_approaches(d, s),
        'gaps': t_gaps(d, s),
    }


def figures(d, s):
    return {
        'prisma': {'file': 'fig-prisma.png', 'caption': 'Selection of studies (PRISMA 2020 flow diagram).', 'width_in': 6.0},
        'overview': {'file': 'fig-overview.png', 'caption': 'Included studies (a) per year of publication and (b) per theme.', 'width_in': 6.0},
        'taxonomy': {'file': 'fig-taxonomy.png', 'caption': 'Taxonomy of privacy-preserving machine learning for NG-IoT security.', 'width_in': 6.3},
        'architecture': {'file': 'fig-architecture.png', 'caption': 'Reference architecture: the NG-IoT tiers, the planes that span them and the main threats.', 'width_in': 6.3},
        'mechanisms': {'file': 'fig-mechanisms.png', 'caption': 'Privacy mechanisms used by the primary studies, with and without a ledger.', 'width_in': 5.8},
        'challenges': {'file': 'fig-challenges.png', 'caption': 'Open challenges and the number of included studies that raise each.', 'width_in': 6.0},
        'design': {'file': 'fig-design.png', 'caption': 'Research design following the design science research process of Peffers et al.', 'width_in': 6.3},
    }


def generated_text(d, s):
    return {}
