"""Statistics, tables and figure registry of the V14 review, computed from the coded records
(myliteraturereviewpaper/_src/V14/coding/<ID>.json), the corpus records and the reference list.
Used by build_v14.py and figures_data.py."""
import csv, json, pathlib, re, collections

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'myliteraturereviewpaper' / '_src' / 'V14'
EXT = ROOT / 'corpus' / '_extraction'
csv.field_size_limit(10 ** 9)

THEMES = collections.OrderedDict([
    ('T4', 'Blockchain-enabled distributed learning'),
    ('T3', 'Privacy-preserving mechanisms for machine learning'),
    ('T5', 'Attacks on learning and their defences'),
    ('T1', 'The NG-IoT fabric and its security'),
    ('T2', 'Distributed learning at the edge'),
    ('T6', 'Regulation, erasure and unlearning'),
])
PRIV_LABEL = {'DP': 'DP', 'LDP': 'LDP', 'HE': 'HE', 'FHE': 'FHE', 'SMPC': 'SMPC', 'secret_sharing': 'SS',
              'secure_aggregation': 'SecAgg', 'TEE': 'TEE', 'ZKP': 'ZKP', 'perturbation_obfuscation': 'Obf.',
              'GAN_synthetic': 'GAN', 'anonymisation': 'Anon.', 'split_learning': 'Split', 'unlearning': 'Unlearn.',
              'none': '–'}
THREAT_GROUPS = collections.OrderedDict([
    ('Poisoning', {'data_poisoning', 'model_poisoning', 'backdoor', 'byzantine'}),
    ('Fake nodes', {'sybil_fake_nodes', 'collusion'}),
    ('Free riding', {'free_riding'}),
    ('DoS / DDoS', {'dos_ddos', 'jamming', 'single_point_of_failure'}),
    ('Inference', {'membership_inference', 'property_attribute_inference', 'reconstruction_inversion'}),
])
CHALLENGE = collections.OrderedDict([
    ('C01', 'Privacy–utility trade-off'),
    ('C02', 'Overhead of cryptographic privacy'),
    ('C03', 'Ledger scalability and cost'),
    ('C04', 'Verification under privacy'),
    ('C05', 'Poisoning, Byzantine and backdoor robustness'),
    ('C06', 'Identity, Sybil and collusion'),
    ('C07', 'Incentives, fairness and free riding'),
    ('C08', 'Availability: DoS, dropouts, single point of failure'),
    ('C09', 'Heterogeneity of data and devices'),
    ('C10', 'Resource, energy and communication efficiency'),
    ('C11', 'Evaluation gap: datasets, testbeds, reproducibility'),
    ('C12', 'Regulation and erasure'),
    ('C13', 'Security of the network fabric'),
    ('C14', 'Interoperability and standardisation'),
    ('C15', 'Post-quantum security'),
    ('C16', 'Trustworthy AI beyond privacy'),
    ('C17', 'Emerging paradigms (LLMs, 6G, digital twins)'),
    ('C18', 'Privacy attacks and privacy measurement'),
    ('C99', 'Other'),
])
YES, NO = '✓', '–'


def load():
    papers = {r['id']: r for r in csv.DictReader(open(EXT / 'papers.csv', encoding='utf-8'))}
    refs = json.loads((SRC / 'references.json').read_text())
    excluded = json.loads((SRC / 'screening.json').read_text())['excluded']
    coding = {}
    for f in sorted((SRC / 'coding').glob('*.json')):
        coding[f.stem] = json.loads(f.read_text(encoding='utf-8'))
    ov = json.loads((SRC / 'theme-overrides.json').read_text())['overrides']
    for pid, o in ov.items():
        if pid in coding:
            coding[pid]['theme'] = o['theme']
    included = [i for i in papers if i not in excluded]
    return {'papers': papers, 'refs': refs['refs'], 'order': refs['order'], 'excluded': excluded,
            'coding': coding, 'included': included,
            'prisma': json.loads((SRC / 'prisma.json').read_text()),
            'onchain': json.loads((SRC / 'onchain.json').read_text())['studies'],
            'qgs': json.loads((SRC / 'search-check.json').read_text())}


def kind(d, i):
    return 'secondary' if d['papers'][i]['document_type'] in ('survey', 'systematic review') else 'primary'


def year(d, i):
    return d['refs'][i]['year']


def cite(i):
    return f'@{i}'


# ------------------------------------------------------------------ statistics
def stats(d):
    inc = d['included']
    C = d['coding']
    s = {}
    s['included'] = len(inc)
    s['primary'] = sum(1 for i in inc if kind(d, i) == 'primary')
    s['secondary'] = sum(1 for i in inc if kind(d, i) == 'secondary')
    s['preprints'] = sum(1 for i in inc if d['refs'][i]['kind'] in ('arxiv', 'preprint'))
    q = d['qgs']
    s['qgs_hit'] = q['combined']
    s['qgs_pct'] = f"{100 * q['combined'] / q['n']:.1f}%"
    for k, v in q['per_string'].items():
        s['qgs_' + k.split()[0]] = v
    # author keywords
    kw = collections.Counter()
    for i in inc:
        seen = set()
        for k in d['papers'][i]['keywords_authors'].split(';'):
            k = k.strip().lower()
            if not k:
                continue
            k = re.sub(r'\s*\(.*?\)', '', k)
            k = {'iot': 'internet of things', 'internet-of-things': 'internet of things', 'fl': 'federated learning'}.get(k, k)
            if k not in seen:
                kw[k] += 1
                seen.add(k)
    s['kw_fl'] = kw['federated learning']
    s['kw_bc'] = kw['blockchain']
    s['kw_priv'] = kw['privacy']
    s['kw_iot'] = kw['internet of things']
    s['kw_sec'] = kw['security']
    s['kw_ml'] = kw['machine learning']
    # publication kinds and publishers, as cited in the reference list
    def pubkind(i):
        r = d['refs'][i]
        if r['kind'] in ('arxiv', 'preprint'):
            return 'preprint'
        if r['kind'] == 'proc':
            return 'conference'
        return 'magazine' if 'Magazine' in r.get('container', '') or 'IEEE Network' == r.get('container', '') else 'journal'
    pk = collections.Counter(pubkind(i) for i in inc)
    s['pt_journal'], s['pt_conf'], s['pt_mag'] = pk['journal'], pk['conference'], pk['magazine']
    def publisher(i):
        r = d['refs'][i]
        if r['kind'] == 'arxiv':
            return 'arXiv'
        f = SRC / 'crossref' / f'{i}.json'
        if f.exists() and r['kind'] != 'preprint':
            pb = json.loads(f.read_text()).get('publisher', '')
        else:
            pb = r.get('publisher') or r.get('container', '')
        if 'Electrical and Electronics' in pb or pb == 'IEEE':
            return 'IEEE'
        if 'Computing Machinery' in pb or pb == 'ACM':
            return 'ACM'
        if 'Elsevier' in pb:
            return 'Elsevier'
        return pb
    pubs = collections.Counter(publisher(i) for i in inc)
    s['pub_ieee'], s['pub_acm'], s['pub_elsevier'] = pubs['IEEE'], pubs['ACM'], pubs['Elsevier']
    cont = collections.Counter(d['refs'][i].get('container', '') for i in inc if d['refs'][i]['kind'] != 'arxiv')
    s['v_csur'] = cont['ACM Computing Surveys']
    s['v_iotj'] = cont['IEEE Internet of Things Journal']
    s['v_access'] = cont['IEEE Access']
    s['v_tii'] = cont['IEEE Transactions on Industrial Informatics']
    s['v_comst'] = cont['IEEE Communications Surveys & Tutorials']
    # research and evaluation types (from the notes' header fields)
    rt = collections.Counter(d['papers'][i]['research_type'].split(';')[0].strip() for i in inc)
    s['rt_solution'] = rt['solution proposal']
    ev = collections.Counter()
    for i in inc:
        for e in d['papers'][i]['evaluation_type'].split(';'):
            ev[e.strip()] += 1
    s['ev_experiment'] = ev['experiment on datasets']
    s['ev_security'] = ev['security analysis']
    s['ev_cost'] = ev['complexity or cost analysis']
    s['ev_prototype'] = ev['prototype or testbed']
    s['ev_simulation'] = ev['simulation']
    s['ev_proof'] = ev['formal proof']
    s['ev_real'] = ev['testing of real devices or software'] + ev['measurement of real systems'] + ev['real deployment or field study']
    years = [year(d, i) for i in inc]
    s['year_min'], s['year_max'] = min(years), max(years)
    s['since2022'] = sum(1 for y in years if y >= 2022)
    s['since2022_pct'] = f"{100 * s['since2022'] / len(inc):.0f}%"
    if not C:
        return s
    coded = [i for i in inc if i in C]
    s['coded'] = len(coded)
    th = collections.Counter(C[i]['theme'] for i in coded)
    for t in THEMES:
        s['n_' + t] = th[t]
        s['n_' + t + '_p'] = sum(1 for i in coded if C[i]['theme'] == t and kind(d, i) == 'primary')
        s['n_' + t + '_s'] = sum(1 for i in coded if C[i]['theme'] == t and kind(d, i) == 'secondary')
    prim = [i for i in coded if kind(d, i) == 'primary']
    sec = [i for i in coded if kind(d, i) == 'secondary']
    ledger_prim = [i for i in prim if C[i]['ledger'].get('used')]
    s['prim_ledger'] = len(ledger_prim)
    s['bc_early'] = sum(1 for i in ledger_prim if year(d, i) <= 2021)
    s['bc_recent'] = sum(1 for i in ledger_prim if year(d, i) >= 2022)
    s['prim_zkp_all'] = sum(1 for i in prim if 'ZKP' in C[i]['privacy_mechanisms'])
    s['prim_real_device'] = sum(1 for i in prim if C[i]['evaluation'].get('real_device_cost') is True)
    learn = [i for i in prim if C[i]['theme'] != 'T1']          # primary studies that build or attack a learning system
    s['learn_prim'] = len(learn)
    s['learn_real_device'] = sum(1 for i in learn if C[i]['evaluation'].get('real_device_cost') is True)
    s['learn_real_device_ids'] = [i for i in learn if C[i]['evaluation'].get('real_device_cost') is True]
    s['prim_ledger_real_device'] = sum(1 for i in ledger_prim if C[i]['evaluation'].get('real_device_cost') is True)
    s['prim_spread'] = sum(1 for i in prim if (C[i].get('rigour') or {}).get('spread'))
    s['prim_test'] = sum(1 for i in prim if (C[i].get('rigour') or {}).get('significance_test'))
    s['prim_code'] = sum(1 for i in prim if (C[i].get('rigour') or {}).get('code_available'))
    s['prim_runs'] = sum(1 for i in prim if not re.match(r'(?i)not stated|^$', (C[i].get('rigour') or {}).get('runs', '')))
    for key, name in (('iot_edge', 'cov_iot'), ('distributed_learning', 'cov_learning'), ('privacy_mechanisms', 'cov_privacy'),
                      ('blockchain', 'cov_blockchain'), ('attacks_defences', 'cov_attacks'), ('evaluation', 'cov_eval'),
                      ('regulation', 'cov_regulation')):
        s[name] = sum(1 for i in sec if (C[i].get('survey') or {}).get('covers', {}).get(key))
    s['sec_systematic'] = sum(1 for i in sec if (C[i].get('survey') or {}).get('protocol') == 'systematic')
    s['sec_partial'] = sum(1 for i in sec if (C[i].get('survey') or {}).get('protocol') == 'partial')
    s['sec_none'] = sum(1 for i in sec if (C[i].get('survey') or {}).get('protocol') == 'none')
    # what ledger-based primary studies write on-chain (reviewer's classification, onchain.json)
    oc = collections.Counter(d['onchain'].get(i, '?') for i in ledger_prim)
    for k in 'UEGC?':
        s['oc_' + k] = oc[k]
    s['oc_updates'] = oc['U'] + oc['E']
    # threat coverage among ledger-based primary studies
    for g, codes in THREAT_GROUPS.items():
        s['bc_threat_' + g] = sum(1 for i in ledger_prim if set(C[i]['threats']) & codes)
    s['bc_poison'] = s['bc_threat_Poisoning']
    s['bc_fake'] = s['bc_threat_Fake nodes']
    s['bc_free'] = s['bc_threat_Free riding']
    s['bc_dos'] = s['bc_threat_DoS / DDoS']
    s['bc_inf'] = s['bc_threat_Inference']
    s['bc_all_four'] = sum(1 for i in ledger_prim if all(set(C[i]['threats']) & THREAT_GROUPS[g]
                                                           for g in ('Poisoning', 'Fake nodes', 'Free riding', 'DoS / DDoS')))
    s['bc_all_four_ids'] = [i for i in ledger_prim if all(set(C[i]['threats']) & THREAT_GROUPS[g]
                                                          for g in ('Poisoning', 'Fake nodes', 'Free riding', 'DoS / DDoS'))]
    # datasets (a study counted once per dataset)
    ds = collections.Counter()
    for i in prim:
        for x in set(norm_dataset(v) for v in C[i]['evaluation'].get('datasets', [])):
            ds[x] += 1
    s['datasets'] = ds
    s['ds_MNIST'] = ds['MNIST']
    s['ds_CIFAR'] = ds['CIFAR-10']
    iot_names = {'Edge-IIoTset', 'TON_IoT', 'NSL-KDD', 'KDD Cup 99', 'UNSW-NB15', 'CIC datasets'}
    s['ds_iot'] = sum(1 for i in prim if any(norm_dataset(v) in iot_names or re.search(r'(?i)iot|intrusion|n-baiot|bot-iot', v)
                                             for v in C[i]['evaluation'].get('datasets', [])))
    s['prim_zkp_ids'] = [i for i in ledger_prim if 'ZKP' in C[i]['privacy_mechanisms']]
    s['prim_zkp'] = len(s['prim_zkp_ids'])
    # challenges
    s['ds_FMNIST'] = ds['Fashion-MNIST']
    s['ds_EMNIST'] = ds['EMNIST']
    tc = tool_counts(d)
    for key, (g, name) in (('tool_pytorch', ('Machine-learning libraries', 'PyTorch')),
                           ('tool_tf', ('Machine-learning libraries', 'TensorFlow / Keras')),
                           ('tool_eth', ('Ledgers and smart contracts', 'Ethereum (Geth, Ganache, Truffle, Solidity)')),
                           ('tool_fabric', ('Ledgers and smart contracts', 'Hyperledger Fabric')),
                           ('tool_own', ('Ledgers and smart contracts', 'Own or simulated chain')),
                           ('tool_seal', ('Cryptographic libraries', 'Microsoft SEAL / TenSEAL')),
                           ('tool_zk', ('Cryptographic libraries', 'circom / snarkjs / libsnark')),
                           ('tool_sgx', ('Trusted execution', 'Intel SGX (Gramine, Occlum)'))):
        s[key] = len(tc[(g, name)])
    learn = [i for i in prim if C[i]['theme'] != 'T1']
    pats = [('m_acc', r'accura|f1|auc|error rate|test error|loss|mse|rmse'), ('m_time', r'time|latency|delay|runtime|duration'),
            ('m_comm', r'communicat|bandwidth|traffic|bytes|message|upload'),
            ('m_attack', r'attack success|asr|detection|true positive|false positive|tpr|fpr|backdoor'),
            ('m_priv', r'epsilon|ε|privacy budget|leak|psnr|membership|inference'),
            ('m_ledger', r'gas|throughput|tps|tx/s|storage|block'), ('m_comp', r'computation|cpu|memory|flops|overhead'),
            ('m_energy', r'energy|power|joule')]
    for key, rx in pats:
        s[key] = sum(1 for i in learn if re.search(rx, ' '.join(C[i]['evaluation'].get('metrics', [])).lower()))
    yrs = collections.Counter((year(d, i), kind(d, i)) for i in inc)
    s['y2024'] = yrs[(2024, 'primary')] + yrs[(2024, 'secondary')]
    s['surveys_lead_since'] = min(y for y in range(2017, 2027) if all(yrs[(z, 'secondary')] > yrs[(z, 'primary')] for z in range(y, 2027)))
    ch = challenge_counts(d)
    s['challenges'] = ch
    for code, ids in ch.items():
        s['ch_' + code] = len(ids)
        s['ch_' + code + '_p'] = sum(1 for i in ids if kind(d, i) == 'primary')
    top = [c for c, ids in sorted(ch.items(), key=lambda kv: -len(kv[1])) if c != 'C99'][:3]
    names = [CHALLENGE[c][0].lower() + CHALLENGE[c][1:] for c in top]
    s['top_challenges'] = f"{names[0]} ({len(ch[top[0]])} studies), {names[1]} ({len(ch[top[1]])}) and {names[2]} ({len(ch[top[2]])})"
    return s


def norm_dataset(x):
    t = x.lower()
    for key, name in (('fashion', 'Fashion-MNIST'), ('emnist', 'EMNIST'), ('mnist', 'MNIST'), ('cifar-100', 'CIFAR-100'),
                      ('cifar100', 'CIFAR-100'), ('cifar', 'CIFAR-10'), ('femnist', 'FEMNIST'), ('shakespeare', 'Shakespeare'),
                      ('edge-iiot', 'Edge-IIoTset'), ('edge iiot', 'Edge-IIoTset'), ('ton', 'TON_IoT'), ('nsl', 'NSL-KDD'),
                      ('kdd', 'KDD Cup 99'), ('unsw', 'UNSW-NB15'), ('cic', 'CIC datasets'), ('svhn', 'SVHN'),
                      ('imagenet', 'ImageNet / Tiny ImageNet'), ('purchase', 'Purchase-100'), ('texas', 'Texas-100'),
                      ('adult', 'Adult'), ('mimic', 'MIMIC'), ('chest', 'Chest X-ray'), ('tcga', 'TCGA')):
        if key in t:
            return name
    return x.strip()


def challenge_counts(d):
    C = d['coding']
    out = collections.OrderedDict()
    for code in CHALLENGE:
        ids = [i for i in d['included'] if i in C and any(it['code'] == code for it in C[i]['open_issues'] + C[i]['future_directions'])]
        out[code] = ids
    return out


# ------------------------------------------------------------------ tables
def t_keywords():
    rows = [
        ['L — Learning', '"federated learning" OR "machine learning" OR "deep learning" OR "distributed learning" OR "decentrali?ed learning" OR "collaborative learning" OR "split learning" OR "swarm learning" OR "edge intelligence" OR "artificial intelligence" OR "neural network" OR "large language model"'],
        ['P — Privacy', 'privacy OR "privacy-preserving" OR "differential privacy" OR "homomorphic encryption" OR "multi-party computation" OR "secret sharing" OR "secure aggregation" OR "trusted execution" OR "zero-knowledge"'],
        ['B — Ledger', 'blockchain OR "distributed ledger" OR "smart contract"'],
        ['T — Setting', '"Internet of Things" OR IoT OR IIoT OR "edge computing" OR "fog computing" OR 5G OR 6G OR "next-generation network" OR wireless OR Bluetooth OR Zigbee OR LoRaWAN OR "Wi-Fi" OR WPA3'],
        ['S — Security', 'security OR attack OR poisoning OR Byzantine OR Sybil OR "free-riding" OR DDoS OR "denial of service" OR jamming OR "membership inference" OR vulnerabilit*'],
        ['G — Regulation', 'GDPR OR "General Data Protection Regulation" OR "data protection" OR "right to be forgotten" OR erasure OR unlearning'],
    ]
    return {'caption': 'Keyword groups used to build the search strings. Within a group the terms are joined by OR; '
                       'the strings combine the groups (Section 3.2). The question mark stands for one character '
                       '(decentralised / decentralized) and the asterisk for any ending.',
            'columns': [{'header': 'Group', 'width': 1500}, {'header': 'Terms (searched in title, abstract and keywords)', 'width': 7500}],
            'rows': rows, 'font_size': 8.5}


def t_criteria():
    rows = [
        {'group': 'Inclusion criteria — all must hold'},
        ['IC1', 'Topic', 'The study addresses at least one of: (a) the privacy or security of machine learning, including the privacy mechanisms used for it and ledgers used to coordinate or secure it; (b) the NG-IoT learning fabric — IoT, edge and 5G/6G infrastructure, its wireless technologies, or distributed learning at the edge — including its security; (c) the data-protection regulation of such systems.'],
        ['IC2', 'Study type', 'A primary study (a scheme, system or empirical study) or a secondary study (survey, systematic review or systematisation of knowledge).'],
        ['IC3', 'Publication', 'Published in a journal, conference or magazine, or posted on a public preprint server (arXiv, Preprints.org).'],
        ['IC4', 'Period', 'Published between January 2017 and September 2026.'],
        ['IC5', 'Language and access', 'Written in English, with the full text available.'],
        {'group': 'Exclusion criteria — any one excludes'},
        ['EC1', 'Out of topic', 'The study meets none of the parts of IC1 — for example, machine learning applied to a domain with no privacy, security, distributed-learning or IoT element.'],
        ['EC2', 'Retracted', 'The study has been retracted by its publisher.'],
        ['EC3', 'Duplicate', 'A duplicate record, or an earlier version (e.g. a preprint) of a study whose published version is included.'],
        ['EC4', 'Not a research paper', 'A thesis, book or textbook, call for papers, editorial, standard or guideline (such documents may still be cited as background).'],
        ['EC5', 'Unpublished', 'No venue, publisher or preprint server can be identified for the document.'],
        ['EC6', 'Out of period or language', 'Published before 2017, or not in English.'],
    ]
    return {'caption': 'Inclusion and exclusion criteria.',
            'columns': [{'header': 'Code', 'width': 700}, {'header': 'Criterion', 'width': 1700}, {'header': 'Definition', 'width': 6600}],
            'rows': rows, 'font_size': 8.5}


def t_quality(d, s):
    C = d['coding']
    inc = [i for i in d['included'] if i in C]
    prim = [i for i in inc if kind(d, i) == 'primary']
    sec = [i for i in inc if kind(d, i) == 'secondary']
    P = len(prim) or 1
    S = len(sec) or 1

    def cnt(ids, f):
        n = sum(1 for i in ids if f(C[i]))
        return f'{n} of {len(ids)} ({100 * n / max(len(ids), 1):.0f}%)'
    rg = lambda c: c.get('rigour') or {}
    sv = lambda c: c.get('survey') or {}
    rows = [
        {'group': f'Primary studies (n = {len(prim)})'},
        ['PQ1', 'Is the solution evaluated on named data or a named workload?', cnt(prim, lambda c: bool(c['evaluation'].get('datasets')))],
        ['PQ2', 'Is it compared with at least one other approach?', cnt(prim, lambda c: c['id'] not in no_baseline(d))],
        ['PQ3', 'Are results repeated over several runs or seeds?', cnt(prim, lambda c: not re.match(r'(?i)not stated|^$', rg(c).get('runs', '')))],
        ['PQ4', 'Is the variation between runs reported (standard deviation, error bars or confidence interval)?', cnt(prim, lambda c: bool(rg(c).get('spread')))],
        ['PQ5', 'Is a statistical test reported?', cnt(prim, lambda c: bool(rg(c).get('significance_test')))],
        ['PQ6', 'Are all datasets public?', cnt(prim, lambda c: bool(rg(c).get('data_public')))],
        ['PQ7', 'Is the code released?', cnt(prim, lambda c: bool(rg(c).get('code_available')))],
        ['PQ8', 'Is cost measured on real IoT or edge hardware?', cnt(prim, lambda c: c['evaluation'].get('real_device_cost') is True)],
        {'group': f'Secondary studies (n = {len(sec)})'},
        ['SQ-a', 'Is a systematic review protocol reported (search strategy and selection criteria)?', cnt(sec, lambda c: sv(c).get('protocol') == 'systematic')],
        ['SQ-b', 'Is at least part of the review method reported (e.g. sources or years)?', cnt(sec, lambda c: sv(c).get('protocol') in ('systematic', 'partial'))],
        ['SQ-c', 'Is the period covered stated?', cnt(sec, lambda c: not re.match(r'(?i)not stated|^$', sv(c).get('years_covered', '')))],
        ['SQ-d', 'Is the number of studies reviewed stated?', cnt(sec, lambda c: not re.match(r'(?i)not stated|^$', sv(c).get('studies_reviewed', '')))],
        ['SQ-e', 'Are open issues or future directions identified?', cnt(sec, lambda c: bool(c['open_issues'] or c['future_directions']))],
    ]
    return {'caption': 'Quality appraisal criteria and how many included studies meet each. The appraisal describes '
                       'the evidence; no study was excluded on quality.',
            'columns': [{'header': 'Code', 'width': 700}, {'header': 'Question', 'width': 5600}, {'header': 'Studies that meet it', 'width': 2200}],
            'rows': rows, 'font_size': 8.5}


def no_baseline(d):
    """Primary studies whose notes (section 15, 'Baselines and comparison') record no comparison with another approach."""
    if '_nobase' in d:
        return d['_nobase']
    rows = {r['id']: r for r in csv.DictReader(open(EXT / 'rigour.csv', encoding='utf-8')) if r['item'] == 'Baselines and comparison'}
    out = set()
    for i in d['included']:
        r = rows.get(i)
        st = re.sub(r'"[^"]*"', '', r['statement']).split(':', 1)[1].strip() if r else ''
        if (not r) or r['absent'] == '1' or re.match(r'(?i)(not stated|none\b|no other|no baseline|no comparison|not compared|nothing|no system)', st):
            out.add(i)
    d['_nobase'] = out
    return out


def marks(v):
    return YES if v else NO


def t_surveys(d, s):
    C = d['coding']
    sec = [i for i in d['included'] if kind(d, i) == 'secondary' and i in C]
    rows = []
    for t, name in THEMES.items():
        ids = sorted([i for i in sec if C[i]['theme'] == t], key=lambda i: (year(d, i), d['refs'][i]['cite']))
        if not ids:
            continue
        rows.append({'group': f'{name} ({len(ids)})'})
        for i in ids:
            sv = C[i]['survey'] or {}
            cv = sv.get('covers', {})
            prot = {'systematic': 'SLR', 'partial': 'part', 'none': NO}.get(sv.get('protocol'), NO)
            rows.append([f'@{i}', C[i]['description'], prot,
                         marks(cv.get('iot_edge')), marks(cv.get('distributed_learning')), marks(cv.get('privacy_mechanisms')),
                         marks(cv.get('blockchain')), marks(cv.get('attacks_defences')), marks(cv.get('evaluation')),
                         marks(cv.get('regulation'))])
    cols = [{'header': 'Survey', 'width': 1250}, {'header': 'Focus', 'width': 3900}, {'header': 'Proto-col', 'width': 470, 'align': 'center'}]
    for h in ('IoT / edge', 'Learn-ing', 'Priv-acy', 'Led-ger', 'Att-acks', 'Eval-uation', 'Regul-ation'):
        cols.append({'header': h, 'width': 470, 'align': 'center'})
    note = ('Protocol: SLR = a search strategy and selection criteria are reported; part = part of the method is reported; '
            '– = none. Topic columns: ✓ = the survey treats the topic as a subject of its own (a section, a branch of its '
            'taxonomy, a table or a comparison axis); – = absent or mentioned only in passing. IoT / edge = the IoT, '
            'edge or 5G/6G setting; Learning = distributed learning; Privacy = privacy mechanisms; Ledger = blockchain; '
            'Attacks = attacks and defences; Evaluation = frameworks, datasets, testbeds or metrics; Regulation = law, '
            'standards or policy.')
    return {'caption': f'Surveys and reviews included in this review ({len(sec)}), grouped by theme, with the topics '
                       'each treats. This review is the last row.',
            'columns': cols, 'rows': rows + [['This review', 'Systematic review of privacy-preserving ML for NG-IoT security: fabric, learning, privacy mechanisms, ledger, threats, evaluation practice and regulation, leading to a research design.', 'SLR'] + [YES] * 7],
            'font_size': 7.5, 'note': note}


def fmt_list(xs, n=4):
    xs = [x for x in xs if x]
    return ', '.join(xs[:n]) + (' …' if len(xs) > n else '')


def priv(c):
    ms = [PRIV_LABEL.get(m, m.replace('other: ', '')) for m in c['privacy_mechanisms'] if m != 'none']
    return ', '.join(ms) if ms else NO


def ledger_cell(c):
    L = c['ledger']
    if not L.get('used'):
        return NO
    parts = [p for p in (L.get('platform'), L.get('consensus')) if p]
    return '; '.join(parts) if parts else 'ledger (not named)'


def threat_cell(c):
    labs = [g for g, codes in THREAT_GROUPS.items() if set(c['threats']) & codes]
    return ', '.join(labs) if labs else NO


def eval_cell(c):
    e = c['evaluation']
    ds = fmt_list([norm_dataset(x) for x in e.get('datasets', [])], 3)
    dev = 'real devices' if e.get('real_device_cost') is True else ''
    parts = [p for p in (ds, dev) if p]
    return '; '.join(parts) if parts else NO


def t_primary(d, s, theme):
    C = d['coding']
    ids = sorted([i for i in d['included'] if kind(d, i) == 'primary' and i in C and C[i]['theme'] == theme],
                 key=lambda i: (year(d, i), d['refs'][i]['cite']))
    rows = [[f'@{i}', C[i]['description'], priv(C[i]), ledger_cell(C[i]), threat_cell(C[i]), eval_cell(C[i])] for i in ids]
    cols = [{'header': 'Study', 'width': 1250}, {'header': 'What it does', 'width': 3600}, {'header': 'Privacy', 'width': 900},
            {'header': 'Ledger', 'width': 1150}, {'header': 'Threats addressed', 'width': 1050}, {'header': 'Evaluation', 'width': 1050}]
    return {'caption': f'Primary studies: {THEMES[theme]} ({len(ids)}).', 'columns': cols, 'rows': rows,
            'font_size': 7.5,
            'note': 'Privacy: DP = differential privacy, LDP = local DP, HE / FHE = (fully) homomorphic encryption, SMPC = secure '
                    'multi-party computation, SS = secret sharing, SecAgg = secure aggregation, TEE = trusted execution, '
                    'ZKP = zero-knowledge proof, Obf. = obfuscation. Threats: the four threats of the proposal and inference '
                    '(Section 5.5). Evaluation: main datasets; "real devices" = cost measured on IoT or edge hardware.'}


def t_threats(d, s):
    C = d['coding']
    ids = sorted([i for i in d['included'] if kind(d, i) == 'primary' and i in C and C[i]['ledger'].get('used')],
                 key=lambda i: (year(d, i), d['refs'][i]['cite']))
    rows = []
    for i in ids:
        c = C[i]
        th = set(c['threats'])
        rows.append([f'@{i}'] + [marks(th & codes) for codes in THREAT_GROUPS.values()] +
                    [marks(c['privacy_mechanisms'] and c['privacy_mechanisms'] != ['none']),
                     d['onchain'].get(i, '?'),
                     marks(c['evaluation'].get('real_device_cost') is True)])
    oc = collections.Counter(d['onchain'].get(i, '?') for i in ids)
    tot = ['Studies covering it'] + [str(sum(1 for i in ids if set(C[i]['threats']) & codes)) for codes in THREAT_GROUPS.values()] + \
          [str(sum(1 for i in ids if C[i]['privacy_mechanisms'] and C[i]['privacy_mechanisms'] != ['none'])),
           f"U {oc['U']} · E {oc['E']} · G {oc['G']} · C {oc['C']}",
           str(sum(1 for i in ids if C[i]['evaluation'].get('real_device_cost') is True))]
    rows.append(tot)
    cols = [{'header': 'Study', 'width': 2000}] + [{'header': g, 'width': 850, 'align': 'center'} for g in THREAT_GROUPS] + \
           [{'header': 'Privacy mechanism', 'width': 900, 'align': 'center'}, {'header': 'On-chain', 'width': 1100, 'align': 'center'},
            {'header': 'Cost on real devices', 'width': 900, 'align': 'center'}]
    return {'caption': f'Threats addressed by the {len(ids)} primary studies that use a ledger, against the threats named in '
                       'the PhD proposal and inference attacks.', 'columns': cols, 'rows': rows, 'font_size': 8,
            'note': 'Poisoning includes data and model poisoning, backdoors and Byzantine updates; fake nodes include Sybil '
                    'identities and collusion; DoS / DDoS includes jamming and the single point of failure of a server; '
                    'inference includes membership, property and reconstruction attacks. ✓ = the study defends against, '
                    'analyses or evaluates the threat. On-chain: U = local updates in plaintext or only noised; E = local '
                    'updates encrypted or masked; G = global or aggregated models and metadata; C = only commitments, hashes, '
                    'proofs or metadata, with models off-chain (the reviewer\'s classification of what each study stores).'}


def t_challenges(d, s):
    C = d['coding']
    ch = s['challenges']
    rows = []
    for code, ids in sorted(ch.items(), key=lambda kv: -len(kv[1])):
        if code == 'C99' or not ids:
            continue
        p = sum(1 for i in ids if kind(d, i) == 'primary')
        q = len(ids) - p
        ex = sorted(ids, key=lambda i: -year(d, i))[:4]
        rows.append([CHALLENGE[code], str(len(ids)), str(p), str(q), '[' + '; '.join('@' + i for i in ex) + ']'])
    cols = [{'header': 'Open challenge', 'width': 2900}, {'header': 'Studies', 'width': 800, 'align': 'center'},
            {'header': 'Primary', 'width': 800, 'align': 'center'}, {'header': 'Secondary', 'width': 900, 'align': 'center'},
            {'header': 'Most recent studies raising it', 'width': 3600}]
    return {'caption': 'Open challenges raised by the included studies, counted from the open issues and future directions '
                       'recorded for each study. A study is counted once per challenge.', 'columns': cols, 'rows': rows,
            'font_size': 8}


TOOL_GROUPS = collections.OrderedDict([
    ('Machine-learning libraries', [('PyTorch', r'pytorch|torch'), ('TensorFlow / Keras', r'tensorflow|keras'), ('scikit-learn', r'scikit|sklearn')]),
    ('Federated-learning frameworks', [('PySyft', r'pysyft|syft'), ('Flower', r'flower|flwr'), ('FATE', r'\bfate\b'), ('TensorFlow Federated', r'tensorflow federated|\btff\b'), ('FedML', r'fedml'), ('HPE Swarm Learning', r'swarm learning')]),
    ('Ledgers and smart contracts', [('Ethereum (Geth, Ganache, Truffle, Solidity)', r'ethereum|geth|ganache|truffle|solidity|hardhat'), ('Hyperledger Fabric', r'fabric'), ('FISCO BCOS', r'fisco'), ('IPFS (off-chain storage)', r'ipfs'), ('Own or simulated chain', r"authors'? own|own block|own chain|simulat|custom|python blockchain|virtual blockchain|written in python")]),
    ('Cryptographic libraries', [('Microsoft SEAL / TenSEAL', r'seal'), ('OpenFHE / Lattigo / HElib', r'openfhe|lattigo|helib|palisade'), ('circom / snarkjs / libsnark', r'circom|snarkjs|libsnark|zokrates|gnark|arkworks|halo2'), ('Charm / PBC / MIRACL / OpenSSL', r'charm|pbc|miracl|openssl|jpbc|gmp')]),
    ('Trusted execution', [('Intel SGX (Gramine, Occlum)', r'sgx|gramine|occlum'), ('ARM TrustZone', r'trustzone')]),
    ('Network simulators and testbeds', [('NS-3 / OMNeT++', r'ns-?3|omnet'), ('Software-defined radio (USRP, GNU Radio)', r'usrp|gnu ?radio|sdr|hackrf|bladerf'), ('Docker / Kubernetes', r'docker|kubernetes')]),
])


def tool_counts(d):
    C = d['coding']
    prim = [i for i in d['included'] if i in C and kind(d, i) == 'primary']
    out = collections.OrderedDict()
    for g, items in TOOL_GROUPS.items():
        for name, rx in items:
            ids = []
            for i in prim:
                e = C[i]['evaluation']
                blob = ' '.join(e.get('tools', []) + [C[i]['ledger'].get('platform', ''), e.get('hardware', '')]).lower()
                if re.search(rx, blob):
                    ids.append(i)
            out[(g, name)] = ids
    return out


def t_tools(d, s):
    tc = tool_counts(d)
    rows = []
    last = None
    for (g, name), ids in tc.items():
        if not ids:
            continue
        if g != last:
            rows.append({'group': g})
            last = g
        ex = sorted(ids, key=lambda i: -year(d, i))[:5]
        rows.append([name, str(len(ids)), '[' + '; '.join('@' + i for i in ex) + ']'])
    return {'caption': 'Tools and platforms named by the primary studies for their implementation and evaluation.',
            'columns': [{'header': 'Tool or platform', 'width': 3000}, {'header': 'Studies', 'width': 800, 'align': 'center'},
                        {'header': 'Most recent studies using it', 'width': 5200}],
            'rows': rows, 'font_size': 8,
            'note': 'Counted from the tools, ledger platform and hardware each study names; a study appears once per tool. '
                    'Tools a study uses but does not name are not counted.'}


def tables(d, s):
    out = {'keywords': t_keywords(), 'criteria': t_criteria()}
    if d['coding']:
        out['quality'] = t_quality(d, s)
        out['surveys'] = t_surveys(d, s)
        for t in THEMES:
            out['prim_' + t] = t_primary(d, s, t)
        out['threats'] = t_threats(d, s)
        out['challenges'] = t_challenges(d, s)
        out['tools'] = t_tools(d, s)
    out.update(static_tables())
    return out


def static_tables():
    mech = {
        'caption': 'Privacy mechanisms for distributed learning: what each protects, whom it trusts and what it costs.',
        'columns': [{'header': 'Mechanism', 'width': 1500}, {'header': 'What it protects', 'width': 2300},
                    {'header': 'Whom it must trust', 'width': 1900}, {'header': 'Main cost', 'width': 1900},
                    {'header': 'Origin', 'width': 1400}],
        'rows': [
            ['Differential privacy (central or local)', 'Individual records against inference from updates or the model, by adding calibrated noise; local DP adds the noise on the device', 'Central DP: the aggregator that adds the noise; local DP: no one', 'Accuracy falls as the privacy budget ε shrinks', '[@dwork2006]'],
            ['Homomorphic encryption (partial or fully homomorphic)', 'Updates while the aggregator computes on them in encrypted form', 'The holder of the decryption key (often a key authority)', 'Computation and ciphertext size, highest for fully homomorphic schemes', '[@gentry2009]'],
            ['Secure multi-party computation and secret sharing', 'Inputs of each party during a joint computation; each share alone reveals nothing', 'A threshold of the parties not to collude', 'Communication rounds and messages between parties', '[@yao1982; @shamir1979]'],
            ['Secure aggregation (pairwise masking)', 'Individual updates: the server learns only their sum', 'Enough clients to stay online and not collude with the server', 'Extra rounds; recovery when clients drop out', '[@O068]'],
            ['Trusted execution environment', 'Code and data inside a hardware-isolated enclave, even from the host', 'The hardware vendor and the attestation service', 'Enclave memory limits; exposure to side channels', '[@costan2016]'],
            ['Zero-knowledge proof', 'The witness (e.g. an update or credential) while proving a statement about it', 'Depending on the system, the setup ceremony', 'Prover time and memory; proof size and verification cost', '[@goldwasser1989]'],
        ],
        'font_size': 8,
    }
    gaps = {
        'caption': 'Research gaps found by the review, the part of the PhD proposal each concerns, and the part of the planned research that deals with it.',
        'columns': [{'header': 'Gap', 'width': 1700}, {'header': 'Evidence in this review', 'width': 3300},
                    {'header': 'In the PhD proposal', 'width': 2400}, {'header': 'Dealt with by', 'width': 1300}],
        'rows': [
            ['G1 Checking updates without seeing them', 'Six of the {{N:prim_ledger}} ledger-based primary studies check updates with cryptography, five with zero-knowledge proofs; the rest trust a server, a cloud provider, the other participants or trusted hardware', 'the ledger is to support "data integrity verification" of model updates', 'RQ2; H2, H3'],
            ['G2 Threats covered one or two at a time', 'None of the {{N:prim_ledger}} ledger-based primary studies addresses poisoning, fake nodes, free riding and denial of service together ({{ref:tab:threats}})', 'the four threats named: data poisoning, malicious participants inserting fake nodes, free riding, DDoS', 'RQ2 (poisoning, fake participants); free riding measured only; DDoS discussed'],
            ['G3 Little testing on IoT devices', '{{N:learn_real_device}} of the {{N:learn_prim}} primary studies that build or attack a learning system measure its cost on IoT or edge hardware', 'the impact of blockchain at the network edge "in terms of computation, storage, and network control"', 'RQ1; H1'],
            ['G4 Networks assumed, not tested', 'No primary study evaluates learning over an emulated IoT or 5G network', 'a training environment that "accurately replicates" the attacks likely in NG-IoT', 'later in the PhD (testbed)'],
            ['G5 Personal data on the ledger', 'Only {{N:oc_C}} of the {{N:prim_ledger}} ledger-based studies keep models and updates off the ledger; the EDPB recommends off-chain storage', 'compliance with "recent privacy legislations such as the General Data Protection Regulation"', 'requirement R1'],
        ],
        'font_size': 8,
    }
    experiment = {
        'caption': 'Main settings of the planned experiments and their basis in the reviewed studies.',
        'columns': [{'header': 'Setting', 'width': 1600}, {'header': 'Planned values', 'width': 3300}, {'header': 'Basis in the reviewed studies', 'width': 3800}],
        'rows': [
            ['Starting point', 'Veri-CS-FL, reproduced first, then run with a permissioned ledger and on an IoT-class device', 'Zero-knowledge proofs of model similarity for client selection [@S033]'],
            ['Compared with', 'Federated averaging without checks; federated averaging with the proof check', 'Primary studies compare against federated averaging (Section 7)'],
            ['Threats', 'Data poisoning and fake participants; free riding measured only', 'The threats of the proposal that proofs can address (Section 9.4)'],
            ['Data', 'MNIST and FEMNIST (as in Veri-CS-FL), then an IoT intrusion-detection dataset', 'MNIST is used by {{N:ds_MNIST}} primary studies; IoT-specific datasets by {{N:ds_iot}} (Section 7.2)'],
            ['Clients', '20 clients as in Veri-CS-FL; later 10 to 50, with up to 30% poisoned', 'Primary studies test 10–50% malicious clients [@N003; @N006; @N014; @N018]'],
            ['Devices', 'A Raspberry Pi-class device and a laptop', '{{N:learn_real_device}} learning studies measure cost on IoT or edge hardware'],
            ['Repetitions and statistics', 'Ten runs per proof measurement, five seeds per learning run; mean ± SD and 95% confidence interval', '{{N:prim_spread}} of the {{N:primary}} primary studies report variation between runs; @S025 report means of ten runs'],
        ],
        'font_size': 8,
    }
    return {'mechanisms': mech, 'gaps': gaps, 'experiment': experiment}


def figures(d, s):
    return {
        'storyline': {'file': 'fig-storyline.png', 'caption': 'Survey questions and the sections that answer them, after the storyline of Martínez Beltrán et al. (2023).', 'width_in': 6.3},
        'prisma': {'file': 'fig-prisma.png', 'caption': 'Selection of studies (PRISMA 2020 flow diagram).', 'width_in': 6.0},
        'taxonomy': {'file': 'fig-taxonomy.png', 'caption': 'Taxonomy of privacy-preserving machine learning for NG-IoT security: six branches and their main categories.', 'width_in': 6.3},
        'architecture': {'file': 'fig-architecture.png', 'caption': 'Reference architecture: the NG-IoT tiers, the planes that run across them, and the threats named in the PhD proposal.', 'width_in': 6.3},
        'design': {'file': 'fig-design.png', 'caption': 'Research design: design science research (after Peffers et al., 2007) with controlled experiments in an emulated NG-IoT testbed.', 'width_in': 6.3},
        'years': {'file': 'fig-years.png', 'caption': 'Included studies per year of publication, by kind.', 'width_in': 5.8},
        'themes': {'file': 'fig-themes.png', 'caption': 'Included studies per theme, by kind.', 'width_in': 5.8},
        'mechanisms': {'file': 'fig-mechanisms.png', 'caption': 'Privacy mechanisms used by the primary studies, with and without a ledger.', 'width_in': 5.8},
        'datasets': {'file': 'fig-datasets.png', 'caption': 'Datasets used by the primary studies (a study may use several).', 'width_in': 5.8},
        'challenges': {'file': 'fig-challenges.png', 'caption': 'Open challenges: number of included studies that raise each.', 'width_in': 6.0},
    }


def generated_text(d, s):
    return {}
