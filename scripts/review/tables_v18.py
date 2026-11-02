"""Tables, statistics and figure registry of the V18 review.

V18 reorganises the review on the author's V13 outline (topic questions SQ1-SQ5) and adds a research agenda. It uses the
V17 set of included studies and classification records unchanged (tables_v17 points tables_v16 at _src/V17); what is new
in V18 is added here, with its sources in _src/V18 (evidence/, classify/)."""
import collections, json, re
import tables_v17 as V17
from tables_v17 import *  # noqa: F401,F403

V16 = V17.V16
SRC18 = V16.V14.ROOT / 'myliteraturereviewpaper' / '_src' / 'V18'
EVID = SRC18 / 'evidence'

# N013: the task publisher, the single party its check rests on, decrypts every local model and aggregates in plaintext
# (p7), so the checker sees the updates in the clear (verify/part06.md, entry 16)
V16.SEES['N013'] = 'clear'

# O083 names Raspberry Pi 4 boards for its implementation (p2) but ties no reported cost to them or to any machine;
# its values sit in the bodies of Tables 1, 4 and 5 (the device-cost evidence of 29 Sep 2026). It does not count as a
# study that measures its cost on IoT hardware.
NOT_REAL_DEVICE = {'O083'}
V16.DEPLOY['O083'] = ('Fabric or private Ethereum', 'n.s. (boards named, no cost tied to them)', 'unnamed', 'n.s.',
                      'n.s.', V16.NO)

# V26 (2 Oct 2026), checked against the full texts while drafting the per-study paragraphs:
# N013 names no ledger type — the edge nodes and the task publisher "form a blockchain network that operates using the
# PBFT protocol" (full text) — whereas the records said 'public' (classification, regulation.json) and the comparison
# table 'Consortium'. Recorded as not stated everywhere.
_V17_LOAD = V17.load


def load():          # noqa: F811
    d = _V17_LOAD()
    d['coding']['N013']['ledger']['type'] = ''
    # N015 (PrSeFL) writes each worker's masked update in an update transaction, and the aggregate in a result
    # transaction, to the ledger (full text p10; notes p6, p10): masked updates on-chain (E), not only commitments (C)
    d['onchain']['N015'] = 'E'
    # N016 records "all intermediate aggregation results from the edge nodes" (full text p7): aggregated models (G),
    # not individual masked updates (E). N019 "preserves ... final aggregated ciphertexts" and prunes per-client updates
    # (full text, Module D/E): an aggregated model on-chain (G), not only commitments (C). Checked 2 Oct 2026.
    d['onchain']['N016'] = 'G'
    d['onchain']['N019'] = 'G'
    return d


V16.LEDGER_ROLES['N013'] = ('Not stated; PBFT', V16.LEDGER_ROLES['N013'][1])
# Two compared schemes are both named PBFL; disambiguate by author in the comparison table (coherence review, 2 Oct 2026)
V16.SCHEME_OVERRIDE = {'N006': 'PBFL (Miao et al.)', 'N017': 'PBFL (Han et al.)'}

_V17_TABLES = V17.tables
_V17_STATS = V17.stats
_V17_FIGURES = V17.figures


# ------------------------------------------------------------------ Citation Links (corpus/<folder>/notes/LINKS.json)
def links_records(d):
    """the citation-link record of each primary study"""
    man = json.loads((V16.V14.ROOT / 'corpus' / '_extraction' / 'MANIFEST.json').read_text())
    L = man if isinstance(man, list) else man.get('papers', man.get('items', []))
    folder = {e['id']: e['folder'] for e in L}
    prim = [i for i in d['included'] if d['coding'][i]['kind'] == 'primary']
    return {i: json.loads((V16.V14.ROOT / 'corpus' / folder[i] / 'notes' / 'LINKS.json').read_text(encoding='utf-8'))
            for i in prim}


def links_stats(d, s):
    R = links_records(d)
    links = [(i, l) for i, r in R.items() for l in r['links']]
    typ = collections.Counter(l['type'] for _, l in links)
    s['links_studies'] = len(R)
    s['links_n'] = len(links)
    s['links_measured'] = typ['measured_against']
    s['links_crit'] = typ['critique']
    s['links_builds'] = typ['builds_on']
    s['links_pos'] = typ['positions_against']
    s['links_cnm'] = typ['compared_not_measured']
    inc = set(d['included'])            # links to corpus papers outside the review (e.g. O068, 2017) are not counted here
    to_inc = lambda l: l.get('to') in inc
    s['links_corpus'] = sum(1 for _, l in links if l.get('to'))
    s['links_incl'] = sum(1 for _, l in links if to_inc(l))
    s['links_crit_incl'] = sum(1 for _, l in links if l['type'] == 'critique' and to_inc(l))
    s['links_builds_incl'] = sum(1 for _, l in links if l['type'] == 'builds_on' and to_inc(l))
    s['links_measured_corpus'] = sum(1 for _, l in links if l['type'] == 'measured_against' and to_inc(l))
    s['links_h2h_studies'] = len({i for i, l in links if l['type'] == 'measured_against' and to_inc(l)})
    s['links_nomeasure_studies'] = sum(1 for i, r in R.items() if not any(l['type'] == 'measured_against' for l in r['links']))
    crit = collections.Counter(l['to'] for _, l in links if l['type'] == 'critique' and l.get('to'))
    built = collections.Counter(l['to'] for _, l in links if l['type'] == 'builds_on' and l.get('to'))
    for k in ('O042', 'O068', 'O043', 'O048', 'O096'):
        s['links_crit_' + k] = crit[k]
        s['links_built_' + k] = built[k]
    # the split of the outside comparisons into baselines and named schemes is a classification of the records,
    # made in evidence/LINES-OF-WORK.md (Appendix A) and summarised in evidence/links_stats.json
    J = json.loads((EVID / 'links_stats.json').read_text(encoding='utf-8'))
    s['links_out_baseline'] = J['measured_against']['outside_baseline']
    s['links_out_scheme'] = J['measured_against']['outside_scheme']
    # named schemes outside the included set, counting the one measured comparison with a corpus paper outside the
    # review (the original secure aggregation protocol, which the review no longer cites as old literature)
    s['links_out_named'] = s['links_out_scheme'] + sum(1 for _, l in links if l['type'] == 'measured_against'
                                                      and l.get('to') and not to_inc(l))
    s['links_named_studies'] = J['studies_with_measured_link_to_named_scheme']['count']
    s['links_baseonly_studies'] = J['studies_with_measured_baselines_only']['count']
    s['links_fedavg_studies'] = len(J['fedavg_named_baselines']['studies'])
    shared = J['named_outside_schemes_run_by_more_than_one_study']
    s['links_median_n'], s['links_trim_n'], s['links_krum_n'] = len(shared['Median']), len(shared['Trimmed mean']), len(shared['Krum'])
    return s


# N011 lists LDP, but uses it only on a trial model when workers are selected (p6) and rejects DP for training (p9):
# its updates are protected by HE alone, so it does not combine HE with DP
NOT_HE_DP = {'N011'}
# the groups of the mechanisms figure (figures_v16.mechanisms)
MECH_GROUPS = {'dp': {'DP', 'LDP'}, 'he': {'HE', 'FHE'}, 'ssa': {'secret_sharing', 'SMPC', 'secure_aggregation'},
               'tee': {'TEE'}, 'zkp': {'ZKP'}}


def mechanism_stats(d, s):
    C = d['coding']
    ids = V16.approach_ids(d)
    has = lambda i, codes: bool(set(C[i]['privacy_mechanisms']) & codes)
    s['appr_he_dp'] = sum(1 for i in ids if has(i, {'HE', 'FHE'}) and has(i, {'DP', 'LDP'}) and i not in NOT_HE_DP)
    s['appr_pow'] = sum(1 for i in ids if re.search(r'\bPoW\b|proof[- ]of[- ]work', C[i]['ledger'].get('consensus') or '', re.I))
    prim = [i for i in d['included'] if C[i]['kind'] == 'primary']
    led = [i for i in prim if C[i]['ledger'].get('used')]
    nol = [i for i in prim if not C[i]['ledger'].get('used')]
    s['prim_noledger'] = len(nol)
    for g, codes in MECH_GROUPS.items():
        s['mech_led_' + g] = sum(1 for i in led if has(i, codes))
        s['mech_noled_' + g] = sum(1 for i in nol if has(i, codes))
    return s


# ------------------------------------------------------------------ attack taxonomy (threat codes of the primary studies)
THREAT_CLASSES = {
    'integrity': ['data_poisoning', 'model_poisoning', 'backdoor', 'byzantine', 'free_riding', 'sybil_fake_nodes',
                  'collusion', 'tampering', 'replay_impersonation'],
    'privacy': ['reconstruction_inversion', 'membership_inference', 'property_attribute_inference',
                'malicious_or_curious_server', 'eavesdropping_mitm'],
    'availability': ['dos_ddos', 'jamming', 'single_point_of_failure'],
    'device': ['device_protocol_vulnerabilities', 'malware_botnet'],
}


def threat_stats(d, s):
    C = d['coding']
    prim = [i for i in d['included'] if C[i]['kind'] == 'primary']
    codes = {i: set(C[i].get('threats', [])) for i in prim}
    for cls, members in THREAT_CLASSES.items():
        s['th_' + cls] = sum(1 for i in prim if codes[i] & set(members))
        for c in members:
            s['th_' + c] = sum(1 for i in prim if c in codes[i])
    s['th_poisoning'] = sum(1 for i in prim if codes[i] & {'data_poisoning', 'model_poisoning', 'backdoor', 'byzantine'})
    s['th_inference'] = sum(1 for i in prim if codes[i] & {'reconstruction_inversion', 'membership_inference',
                                                            'property_attribute_inference'})
    return s


def attack_stats(d, s):
    """implemented attacks, defence families and the ledger's role per attack class: evidence/attacks.json, where
    each implemented attack and each role carries its page and quotation (evidence/ATTACKS.md)"""
    J = json.loads((EVID / 'attacks.json').read_text(encoding='utf-8'))
    short = {'integrity': 'int', 'privacy': 'priv', 'availability': 'av', 'device_and_network': 'dev'}
    members = dict(THREAT_CLASSES, device_and_network=THREAT_CLASSES['device'])
    anyimpl = set()
    for cls, k in short.items():
        impl = {i for c in members[cls] for i in J['codes'][c].get('implemented_ids', [])}
        anyimpl |= impl
        s['th_impl_' + k] = len(impl)
        fam = J['classes'][cls]['families']
        for f, ids in fam.items():
            s[f'def_{k}_{f}'] = len(ids)
        for r, ids in J['classes'][cls]['ledger_role'].items():
            s[f'lr_{k}_{r}'] = len(ids)
    s['th_impl_any'] = len(anyimpl)
    for c in ('free_riding', 'sybil_fake_nodes', 'collusion', 'backdoor', 'dos_ddos', 'single_point_of_failure'):
        s['th_impl_' + c] = len(J['codes'][c].get('implemented_ids', []))
    return s


def t_defences18(d, s):
    fam_names = {'consensus_and_replication': 'consensus and replication', 'identity_admission_signatures': 'identity, '
                 'admission and signatures', 'proofs': 'proofs', 'robust_aggregation': 'robust aggregation',
                 'reputation_and_incentives': 'reputation and incentives', 'validation_or_anomaly_detection':
                 'validation by miners, committee or peers', 'secure_aggregation_or_masking': 'secure aggregation or masking',
                 'HE': 'HE', 'DP': 'DP', 'TEE': 'TEE'}
    J = json.loads((EVID / 'attacks.json').read_text(encoding='utf-8'))
    rows = []
    for cls, label, k in (('integrity', 'Integrity (poisoning, backdoors, Byzantine updates, free riding, fake nodes, '
                           'collusion, tampering, replay)', 'int'),
                          ('privacy', 'Privacy (reconstruction, membership and property inference, a curious server or '
                           'miner, eavesdropping)', 'priv'),
                          ('availability', 'Availability (denial of service, jamming, single point of failure)', 'av')):
        fam = sorted(((len(v), f) for f, v in J['classes'][cls]['families'].items() if f in fam_names), reverse=True)[:4]
        lr = J['classes'][cls]['ledger_role']
        rows.append([label, f"{s['th_' + cls]} / {s['th_impl_' + k]}", '; '.join(f'{fam_names[f]} ({n})' for n, f in fam),
                     f"{len(lr.get('mitigates', []))} / {len(lr.get('records', []))} / {len(lr.get('none', []))}"])
    return {'caption': 'Attacks on the primary studies by class, the defences used against each and the role of the ledger.',
            'columns': [{'header': 'Attack class', 'width': 2900}, {'header': 'Claimed / implemented', 'width': 1100,
                         'align': 'center'}, {'header': 'Most common defence families (studies)', 'width': 3326},
                        {'header': 'Ledger mitigates / records / no role', 'width': 1700, 'align': 'center'}],
            'rows': rows, 'font_size': 8,
            'note': 'Claimed = primary studies that claim to address at least one attack of the class; implemented = those '
                    'that run such an attack in their experiments. The role of the ledger is classified, from each '
                    'study’s own description, for the ledger-based studies that claim the class: it mitigates the attack '
                    'when a check, vote or rule in the consensus or a smart contract rejects it, records it when the '
                    'ledger only keeps an auditable trace, and plays no role when the defence lies outside the ledger.'}


def stats(d):          # noqa: F811
    s = _V17_STATS(d)
    for i in NOT_REAL_DEVICE:
        if i in s['learn_real_device_ids']:
            s['learn_real_device_ids'] = [x for x in s['learn_real_device_ids'] if x != i]
            s['learn_real_device'] -= 1
            s['prim_real_device'] -= 1
            if d['coding'][i]['ledger'].get('used'):
                s['prim_ledger_real_device'] -= 1
    s = links_stats(d, s)
    s = mechanism_stats(d, s)
    s = threat_stats(d, s)
    s = attack_stats(d, s)
    s = survey_stats(d, s)
    s = regulation_stats(d, s)
    return s


# ------------------------------------------------------------------ survey questions of V18 (the V13 topics)
def t_questions18():
    rows = [
        ['SQ1', 'What does the NG-IoT fabric look like — its tiers, devices, links and constraints — and where do learning, '
                'privacy and trust mechanisms run on it?', 'The NG-IoT fabric', 'Sections IV-A, V-C'],
        ['SQ2', 'Which mechanisms protect data and model updates in distributed learning, what does each protect and from '
                'whom, and what does each cost on the device?', 'The privacy plane', 'Sections IV-B, V-D'],
        ['SQ3', 'What do blockchains record, verify and enforce in FL, can a ledger check an update it cannot read, and at '
                'what cost?', 'The trust plane', 'Sections IV-C, V-E'],
        ['SQ4', 'Which attacks threaten these systems, which defences answer each, does the ledger mitigate an attack or only '
                'record it, and how are the defences evaluated and compared?', 'Attacks, defences and evaluation',
         'Sections IV-D, V-F'],
        ['SQ5', 'What do the GDPR and the EDPB guidelines on blockchain require of such systems — for on-chain data, erasure '
                'and zero-knowledge verification — and how do the included approaches meet these requirements?',
         'The regulatory layer', 'Sections IV-E, V-G'],
    ]
    return {'caption': 'Survey questions.',
            'columns': [{'header': 'ID', 'width': 600}, {'header': 'Question', 'width': 5226},
                        {'header': 'Layer', 'width': 1900}, {'header': 'Answered in', 'width': 1300}],
            'rows': rows, 'font_size': 8.5,
            'note': 'Each question is answered by the fundamentals of its layer (Section IV) and by what the approaches do '
                    'on it (Section V). The trends and open areas that follow from the five answers are given in Section VI, '
                    'the research gap in Section VII and the research agenda in Section VIII.'}


# ------------------------------------------------------------------ the research agenda (Section X)
def t_gaps18(d, s):
    """V26 (2 Oct 2026): the five open areas of Section VI-D, each with the survey questions it arises from; the research
    questions that take them up are given in Section VIII ({{ref:tab:rq}})"""
    g = V17.t_gaps17(d, s)
    for r in g['rows']:                       # commitments are hiding (their witness), not salted (EDPB para. 53)
        r[2] = r[2].replace('salted, hiding commitments', 'hiding commitments whose data and witness can be deleted')
    g['rows'].append(['G5 Few comparisons between studies',
                      '{{N:links_measured_corpus}} of the {{N:links_measured}} comparisons that the primary studies measure '
                      'in their own experiments are against another included study; {{N:links_h2h_studies}} of the '
                      '{{N:links_studies}} studies make such a comparison',
                      'Common baselines and datasets, and comparison with published schemes in the same setting'])
    for r, sq in zip(g['rows'], ['SQ2, SQ3', 'SQ1, SQ2', 'SQ1, SQ4', 'SQ3, SQ5', 'SQ4']):
        r.insert(1, sq)
    g['columns'] = [dict(g['columns'][0], header='Open area'), {'header': 'From', 'width': 900, 'align': 'center'}] + g['columns'][1:]
    for c, w in zip(g['columns'], [1800, 900, 3500, 2826]):
        c['width'] = w
    g['caption'] = ('Open areas identified by this survey, the survey questions from which each arises, the evidence for each '
                    'and a direction for research.')
    return g


def t_rq18():
    rows = [
        ['RQ1 Cost', 'What does proving a norm bound, or the cosine similarity to a reference model, about a model update '
                     'cost on a gateway-class IoT device, for which proof systems and model sizes?', 'G2',
         'Proving time, memory, energy and proof size on the device; bytes sent per round; verification time on the ledger'],
        ['RQ2 Protection', 'How far do such proofs, verified on a permissioned ledger, reduce the success of poisoning and '
                           'of malicious or colluding participants, compared with no checks, the same checks in plaintext '
                           'and robust aggregation?', 'G1, G5',
         'Success rate of backdoor and label-flipping attacks and accuracy, at stated compromise rates; selection of '
         'free riders'],
        ['RQ3 Ledger and law', 'What must the ledger record for the checks to be audited, and does a ledger that holds only '
                               'proofs and commitments meet the EDPB requirements for off-chain storage, erasure by '
                               'design and a stated need for the ledger?', 'G4',
         'Bytes on-chain per round; the EDPB recommendations met; an erasure procedure carried out end to end'],
    ]
    return {'caption': 'Research questions of the agenda, the gaps they take up and what each would measure.',
            'columns': [{'header': 'Question', 'width': 1300}, {'header': 'Wording', 'width': 4226},
                        {'header': 'Gaps', 'width': 700}, {'header': 'Measures', 'width': 2800}],
            'rows': rows, 'font_size': 8}


def t_design18():
    rows = [
        ['Clients', 'IoT gateways, each training for the devices behind it', 'Many sensors cannot train a full-size model; a '
         'gateway can take part on their behalf, and it already sees their raw data (Section IV)', '[@O054; @S004]'],
        ['Check on each update', 'A bound on its norm, or its cosine similarity to a reference model', 'Proofs of training '
         'remain costly [@N002; @S032], whereas both predicates are already proved', '[@O096; @O097; @N015; @S033]'],
        ['Binding', 'The proof opens a commitment to the update inside the circuit, with a range check on each weight',
         'Otherwise the update later uploaded need not be the one checked, and values can wrap around the field', '[@O096; @S032]'],
        ['Reference model', 'Committed or hashed, not passed as public input; opened only after the clients have committed',
         'Public inputs drive the verifier’s cost; a known reference invites copying it', '[@S032; @O099; @O096]'],
        ['Normalisation', 'Update magnitudes normalised and aggregation weights bounded', 'Scaled or overweighted updates '
         'can pass a similarity check', '[@O048]'],
        ['Proof system', 'A circuit-specific zk-SNARK (Groth16) compared with one without a trusted set-up per circuit',
         'The trusted set-up, prover cost and proof size trade off', '[@S025; @S033; @N015]'],
        ['Ledger', 'Permissioned, with BFT ordering, at the edge', 'Admits only registered gateways; live while fewer than a '
         'third of the validators are faulty and messages arrive within a known delay', '[@N003; @N019]'],
        ['On-chain record', 'Proof outcomes, hiding commitments, admission decisions', 'Enough to audit the '
         'selection; no personal data on-chain', '[@O033; @edpb2026]'],
        ['Identity', 'Admission control of the permissioned ledger; anonymous credentials later', 'Fake nodes are stopped '
         'by admission, not by proofs', '[@N015; @S032]'],
    ]
    return {'caption': 'Design choices of the reference design, the reason for each and the studies it builds on.',
            'columns': [{'header': 'Element', 'width': 1300}, {'header': 'Choice', 'width': 2900},
                        {'header': 'Reason', 'width': 3226}, {'header': 'From', 'width': 1600}],
            'rows': rows, 'font_size': 8}


def t_evalplan18():
    rows = [
        ['Device cost', 'Proving time, memory, energy and temperature for a model of about 10³ parameters, after counting '
                        'the circuit’s constraints', 'Raspberry Pi 4 (wired, or Wi-Fi with the WPA3 caveats of '
                        'the study cited) and a phone-class device', '[@O026; @O097]'],
        ['Communication', 'Bytes sent per round, against uploading the model', 'The same devices', '[@S033]'],
        ['Ledger', 'Verification time and throughput as the number of clients grows, including floods of invalid proofs',
         'Permissioned ledger on edge hardware', '[@N003; @N019]'],
        ['Protection', 'Success rate of backdoor and label-flipping attacks, and accuracy, at compromise rates justified '
                       'for the deployment; attackers who know the check; colluders filling the selected slots; free '
                       'riders who return the global model, the reference or noise', 'Training without checks; the same '
                       'checks in plaintext, and on encrypted updates by non-colluding servers; FLTrust; Krum, trimmed '
                       'mean and median', '[@O038; @N006; @N018; @O048; @N005]'],
        ['Data', 'MNIST and FEMNIST, as in Veri-CS-FL, and an IoT intrusion-detection dataset with a small model',
         'Edge-IIoTset', '[@S033; @N019]'],
        ['Network', 'Emulated links with loss, delay and honest devices dropping out', 'Link profiles of LPWAN and Wi-Fi',
         '[@O020; @O098]'],
        ['Reporting', 'Several seeds per setting, with the variation reported, and the code released', '—', 'Section VII-F'],
    ]
    return {'caption': 'Evaluation plan of the reference design.',
            'columns': [{'header': 'Aspect', 'width': 1300}, {'header': 'What is measured', 'width': 3900},
                        {'header': 'Baselines, devices or data', 'width': 2426}, {'header': 'Following', 'width': 1400}],
            'rows': rows, 'font_size': 8}


# ------------------------------------------------------------------ the regulatory layer (Section VIII)
# The ledger-based primary studies against the EDPB guidelines: the lists of evidence/REGULATION.md, Part B(c), where each
# study's wording is quoted with its page (regulation.json holds the quotations).
REG = {
    'law': ['N001', 'N004', 'N005', 'N012', 'N014', 'O036', 'O044', 'O083', 'S022', 'O104', 'O109'],
    'gdpr': ['N001', 'N004', 'N005', 'N012', 'N014', 'O036', 'O083', 'S022', 'O104', 'O109'],
    'erasure_right': [],
    'erasure_design': ['N014', 'N019', 'N020'],
    'undeletable': ['N007', 'N011', 'O033', 'O108'],
    'minim_term': [],
    'minim_near': ['N019', 'N021', 'O033', 'O043', 'S022'],
    'identifiers': ['N011', 'N015', 'O043', 'O094', 'S022', 'O105'],
    'roles_dpia': [],
}


def regulation_stats(d, s):
    R = json.loads((EVID / 'regulation.json').read_text(encoding='utf-8'))
    assert len(R) == s['prim_ledger'], 'regulation.json must cover every ledger-based primary study'
    for r in R:                               # V26: N013 names no ledger type (see load above)
        if r['id'] == 'N013':
            r['ledger_type'] = 'not stated'
    for k, ids in REG.items():
        s['reg_' + k] = len(ids)
    typ = collections.Counter(r['ledger_type'] for r in R)
    s['reg_permissioned'] = typ['permissioned']
    s['reg_consortium'] = typ['consortium']
    s['reg_public'] = typ['public']
    s['reg_typens'] = typ['not stated']
    s['reg_perm_or_cons'] = typ['permissioned'] + typ['consortium']
    return s


def t_edpb18(d, s):
    rows = [
        ['Justify the ledger (why a blockchain, which type, whether a zero-knowledge architecture is possible, which PETs); '
         'allocate roles by governance, with a consortium of nodes as controller; carry out a DPIA where the risk is high',
         'paras. 38–47, 91–99; Rec. 1', 'No study names a controller, a processor, a DPIA or a retention period'],
        ['Favour permissioned chains; public chains only where public access is necessary', 'paras. 40, 49',
         '{{N:reg_permissioned}} permissioned and {{N:reg_consortium}} consortium ledgers; {{N:reg_public}} public; '
         '{{N:reg_typens}} not stated'],
        ['Keep personal data off-chain; on-chain, only a proof of existence such as a commitment or keyed hash',
         'paras. 34, 48, 54, 104; Rec. 2', 'Only commitments, hashes, proofs or payments on-chain in {{N:oc_C}}; global '
         'models in {{N:oc_G}}; local updates in {{N:oc_U}} in plaintext or noised and in {{N:oc_E}} encrypted'],
        ['Encrypted data and salted or keyed hashes remain personal data; unsalted hashes are not enough on public chains',
         'paras. 51–52', '{{N:oc_E}} write encrypted updates on-chain'],
        ['Hiding commitments become unlinkable once the data and witness are deleted', 'para. 53',
         'Commitments to updates are used, for example, by [@N001; @O107]'],
        ['Identifiers on-chain are personal data where linkable to a person; retention applies to them', 'paras. 26–27, 80',
         '{{N:reg_identifiers}} record identities, pseudonyms, device IDs or account addresses'],
        ['Data minimisation: the minimum information at the minimum publicity', 'para. 61; Rec. 4',
         'No study uses the term; {{N:reg_minim_near}} use nearby wording'],
        ['Erasure and objection by design; without a way to delete or anonymise, no personal data on-chain',
         'paras. 63, 102–103; Recs. 9, 11, 16', 'No study names the right to erasure; {{N:reg_erasure_design}} delete, '
         'prune or redact ledger data to bound storage; {{N:reg_undeletable}} state that stored data cannot be deleted'],
        ['ZKPs and other PETs carefully tested and validated, with other measures', 'para. 56',
         '{{N:appr_proof}} of the compared approaches rest on proofs; none is measured on IoT devices'],
    ]
    return {'caption': f"The EDPB guidelines on blockchain against the {s['prim_ledger']} ledger-based primary studies.",
            'columns': [{'header': 'Requirement of the guidelines', 'width': 3900}, {'header': 'Where', 'width': 1500},
                        {'header': 'What the ledger-based studies do', 'width': 3626}],
            'rows': rows, 'font_size': 8,
            'note': 'The guidelines make no statement about machine learning, AI models, IoT or federated learning; applying '
                    'them to learning is this survey’s reading. Counts are of the ledger-based primary studies; "No study" '
                    'means that no such study states it in its text.'}


# ------------------------------------------------------------------ comparison with the closest surveys (columns by SQ)
# The comparison is by survey question. Each question's mark aggregates the finer per-topic marks of the classification
# records (classify/surveys/<ID>.json): SQ1 the fabric = devices + network; SQ2 the privacy plane = mechanisms; SQ3 the
# trust plane = ledger + the checks it treats + whether it classifies checks by trust; SQ4 = attacks + evaluation; SQ5 =
# what a ledger should hold against the law. Rule: ✓ if every constituent is a subject of its own, – if none is, else ◐.
SQ_COLS = [
    ('SQ1', 'SQ1 The NG-IoT fabric', ['devices', 'network']),
    ('SQ2', 'SQ2 The privacy plane', ['mechanisms']),
    ('SQ3', 'SQ3 The trust plane', ['ledger', 'checks', 'trust']),
    ('SQ4', 'SQ4 Attacks, defences and evaluation', ['attacks', 'evaluation']),
    ('SQ5', 'SQ5 The regulatory layer', ['onchain_law']),
]
THIS_WORK18 = dict(V16.THIS_WORK16, mechanisms='✓', attacks='✓')


def surveys18():
    """the V17 survey records, with the two V18 columns (privacy mechanisms, attacks) from _src/V18/classify/surveys"""
    S = V16.load_class('surveys')
    for f in sorted((SRC18 / 'classify' / 'surveys').glob('*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        S[r['id']] = dict(S[r['id']], mechanisms=r['mechanisms'], attacks=r['attacks'])
    return S


def _sub_mark(r, key):
    """the ✓/◐/– of one topic; the checks column is a set of families, mapped ✓ (≥3) / ◐ (1–2) / – (none)"""
    if key == 'checks':
        n = len(r['checks']['families'])
        return '✓' if n >= 3 else ('◐' if n >= 1 else '–')
    return r[key]['mark']


def _sq_mark(r, keys):
    marks = [_sub_mark(r, k) for k in keys]
    if all(m == '✓' for m in marks):
        return '✓'
    if all(m == '–' for m in marks):
        return '–'
    return '◐'


def survey_stats(d, s):
    S = surveys18()
    ids = V16.closest_ids(d)
    s['cmp18_allfive'] = sum(1 for i in ids if all(_sq_mark(S[i], ks) == '✓' for _, _, ks in SQ_COLS))
    s['cmp18_sq2'] = sum(1 for i in ids if _sq_mark(S[i], ['mechanisms']) == '✓')
    s['cmp18_sq3'] = sum(1 for i in ids if _sq_mark(S[i], ['ledger', 'checks', 'trust']) == '✓')
    s['cmp18_sq5_none'] = sum(1 for i in ids if _sq_mark(S[i], ['onchain_law']) == '–')
    s['cmp18_sq3_any'] = sum(1 for i in ids if _sq_mark(S[i], ['ledger', 'checks', 'trust']) != '–')
    # V26 (2 Oct 2026): the counts behind the survey questions of Section II-D and the abstract
    full = [sum(_sq_mark(S[i], ks) == '✓' for _, _, ks in SQ_COLS) for i in ids]
    s['cmp18_full_max'] = max(full)
    s['cmp18_full_none'] = sum(1 for n in full if n == 0)
    s['cmp18_sq1_full'] = sum(1 for i in ids if _sq_mark(S[i], ['devices', 'network']) == '✓')
    s['cmp18_net_none'] = sum(1 for i in ids if _sub_mark(S[i], 'network') == '–')
    s['cmp18_sq2_dev'] = sum(1 for i in ids if _sub_mark(S[i], 'mechanisms') == '✓' and _sub_mark(S[i], 'devices') == '✓')
    s['cmp18_ledger_full'] = sum(1 for i in ids if _sub_mark(S[i], 'ledger') == '✓')
    s['cmp18_attacks_full'] = sum(1 for i in ids if _sub_mark(S[i], 'attacks') == '✓')
    s['cmp18_eval_full'] = sum(1 for i in ids if _sub_mark(S[i], 'evaluation') == '✓')
    return s


def t_surveys18(d, s):
    S = surveys18()
    fp = V16.SRC16 / 'focus.json'
    focus = json.loads(fp.read_text()) if fp.exists() else {}
    ids = sorted(V16.closest_ids(d), key=lambda i: (V16.year(d, i), d['refs'][i]['narrative_ieee']))
    rows = []
    for i in ids:
        r = S[i]
        f = re.sub(r'^(Survey of|Systematic review of|SoK:)\s*', '', focus.get(i, '')).strip()
        f = f[:1].upper() + f[1:]
        rows.append([f'@{i}', str(V16.year(d, i)), f, V16.studies_cell(r)] + [_sq_mark(r, ks) for _, _, ks in SQ_COLS])
    own = ['This work', '2026', 'Privacy-preserving, verifiable FL on ledgers for NG-IoT',
           f"{s['primary']} + {s['secondary']}; {s['appr_n']} compared (2020–26)"] + ['✓' for _ in SQ_COLS]
    rows.append([{'runs': [{'text': x, 'bold': True}], 'fill': 'EEF5FD'} for x in own])
    cols = [{'header': 'Survey', 'width': 860}, {'header': 'Year', 'width': 540, 'align': 'center'},
            {'header': 'Focus', 'width': 2180}, {'header': 'Studies (period)', 'width': 820, 'align': 'center'}]
    cols += [{'header': h, 'width': 900, 'align': 'center'} for _, h, _ in SQ_COLS]
    return {'caption': 'Comparison of this work with the closest surveys (2022–2026), by survey question.',
            'columns': cols, 'rows': rows, 'font_size': 7.5,
            'note': 'Selection: the included surveys published from 2022 that treat blockchain-based FL, or the checking of '
                    'updates by proofs or input validation, as a subject of their own. One column per survey question (SQ1–SQ5 '
                    'of {{ref:tab:questions}}). ✓ = the survey treats that question’s area as a subject of its own — a section, '
                    'a taxonomy branch, a table or a comparison axis — throughout; ◐ = in part; – = absent or mentioned only in '
                    'passing. A question’s mark aggregates the finer per-topic marks of the classification records (available '
                    'from the author): ✓ when every topic of the question is a subject of its own, – when none is, otherwise ◐. '
                    'The topics are, for SQ1 the constraints of IoT devices and the network or physical layer; for SQ2 the '
                    'privacy mechanisms; for SQ3 the ledger, the families of checks on updates and whether they are classified '
                    'by whom they trust; for SQ4 the attack taxonomy and evaluation practice; for SQ5 what a ledger should hold '
                    'judged against data-protection law. Studies (period): the number of studies reviewed and the period '
                    'covered, as stated; † = counted from the survey’s tables or references; n.s. = not stated; for this work, '
                    'primary + secondary studies, and the approaches compared in Section V. Whether each survey reports a '
                    'systematic search method is discussed in Section II-C.'}


# ------------------------------------------------------------------ V26: the works closest to the research gap (Section VII-B)
# Each cell comes from the page-cited evidence sheet _src/V18/v26/drafts/closest-works.json (value, page and quotation from
# the study's notes; values that rest on an absence say what was searched).
CLOSEST_OFF = ['O098', 'O096', 'O097', 'O099', 'O103', 'S033']
CLOSEST_ON = ['N002', 'O105', 'O109', 'O102', 'O108', 'N015', 'O107', 'O104']
CLOSEST_COLS = [('proves', 'Proves', 1800), ('verified_by', 'Verified by', 1000), ('ledger', 'Ledger', 1000),
                ('trusted_setup', 'Trusted set-up', 1000), ('attack_tested_with_proofs', 'Attack tested with the proofs',
                1200), ('device_cost', 'Cost measured on', 900), ('on_chain', 'On-chain', 1126)]


def t_closest26(d, s):
    src = SRC18 / 'v26' / 'drafts' / 'closest-works.json'
    if not src.exists():
        return {'caption': '«PENDING closest-works table»', 'columns': [{'header': 'Work', 'width': 9026}], 'rows': []}
    J = json.loads(src.read_text(encoding='utf-8'))['table']
    # Short cell values for print, condensed from the page-cited evidence cells (value, page, quotation) of
    # closest-works.json; the order is that of CLOSEST_COLS. zkFL's set-up is 'not stated': the paper names Halo2 only,
    # which Sheybani et al. (S025) describe as a PLONK-ish system with Kate commitments (V26 check, 2 Oct 2026).
    SHORT = {
        'O098': ['A circuit predicate on each update (norm bounds, cosine similarity)', 'Other clients', 'None (bulletin board)',
                 'Not stated (SNIP)', 'Yes: seven poisoning attacks', 'Cloud instances', '–'],
        'O096': ['Norm bound on each committed update', 'Server', 'None', 'None (Bulletproofs)',
                 'Partly: backdoors against the bounds, in a separate framework', 'Cloud instances', '–'],
        'O097': ['Bound on each masked input', 'Server', 'None', 'None (Bulletproofs)', 'No', 'Laptop; smartphone', '–'],
        'O099': ['Update within a threshold of the median of cluster means', 'Server', 'None', 'Not stated (Wolverine)',
                 'Yes: sign-flip, scaling, Byzantine; no backdoor', 'Desktop', '–'],
        'O103': ['Range of each client’s committed parameters; the sum', 'Server; model user; auditor',
                 'None (bulletin board)', 'None (Bulletproofs)', 'No: poisoning filtered in plaintext', 'Laptop', '–'],
        'S033': ['Cosine similarity of each model to a benchmark', 'Server', 'None', 'Yes, per circuit (Groth16)',
                 'No: noisy data, no poisoned client', 'Server', '–'],
        'N002': ['Training of a linear regression with LDP noise; its test error', 'Smart contract', 'Ethereum',
                 'Yes, per circuit', 'No', 'Cloud instance', 'Noisy weights, data roots, proofs, global weight, payments'],
        'O105': ['The aggregator’s outlier test, aggregation and contribution scores', 'Smart contract', 'Chain not named',
                 'Yes, per circuit (Groth16)', 'Yes: Byzantine and backdoor', 'Server; cloud instance',
                 'Content identifiers, trainer IDs, proofs, contributions'],
        'O109': ['Each step of local training', 'Task publisher', 'Smart contract; chain not named',
                 'Yes, per circuit (Groth16)', 'No', 'Cloud instance', 'Masked, encrypted parameters with proofs'],
        'O108': ['The aggregation over hashed models', 'Smart contract', 'Local Ethereum chain', 'Yes, per circuit (Groth16)',
                 'No', 'Not stated', 'Hashes and the proof'],
        'O102': ['Naive Bayes statistics and their encryption, per update', 'Smart contracts', 'Ethereum (testnet)',
                 'Yes, per circuit (Groth16)', 'No', 'Laptop', 'Encrypted updates, their sum, decryptions, proofs'],
        'N015': ['Norm bound on each masked update', 'Consortium nodes', 'Consortium (simulated)', 'None (Bulletproofs)',
                 'No: no dataset', 'Laptop', 'Masked updates, proofs, shares, the aggregate'],
        'O107': ['The aggregation of committed updates', 'Miners', 'Chain not named', 'Not stated (Halo2)', 'No', 'GPU',
                 'Hash of the aggregate'],
        'O104': ['Accuracy of each trainer’s model; the aggregation', 'Oracle nodes', 'Permissioned (Geth, PBFT)',
                 'Not stated (Nova)', 'No', 'Dell XPS 15 PC', 'Hashes of models, proofs, stakes'],
    }
    names = {'O098': 'EIFFeL', 'O096': 'RoFL', 'O097': 'ACORN', 'O099': 'zPROBE', 'O103': 'VPFL', 'S033': 'Veri-CS-FL',
             'O105': 'Proof of contribution', 'O109': 'ZKP-FL', 'O102': 'Federify', 'O108': 'zkFDL', 'N015': 'PrSeFL',
             'O107': 'zkFL', 'O104': 'VerifBFL'}
    rows = []
    for label, ids in ((f'Proofs without a ledger ({len(CLOSEST_OFF)})', CLOSEST_OFF),
                       (f'Proofs verified on a ledger ({len(CLOSEST_ON)})', CLOSEST_ON)):
        rows.append({'group': label})
        for i in sorted(ids, key=lambda i: (V16.year(d, i), i)):
            assert i in J, f'no evidence for {i}'
            rows.append([f'[@{i}] ' + names.get(i, '–')] + SHORT[i])
    return {'caption': 'The works closest to the research gap: proofs about hidden updates, set against the conditions of '
                       'the gap.',
            'columns': [{'header': 'Work', 'width': 1000}] + [{'header': h, 'width': w} for _, h, w in CLOSEST_COLS],
            'rows': rows, 'font_size': 7.5,
            'note': 'Values as the studies report them, condensed. Trusted set-up: "not stated" where the study does not say, '
                    'with the proof system named. Attack tested with the proofs: an implemented attack evaluated with the '
                    'proof-based check in the loop. No design measures its proving cost on an IoT device.'}


ABBREVIATIONS18 = sorted([a for a in V16.ABBREVIATIONS16 if a[0] not in ('IoMT', 'LLM')]      # not used in V18
                         + [('RQ', 'Research question'), ('SQ', 'Survey question'), ('FedAvg', 'Federated averaging')], key=lambda a: a[0].lower())


def t_abbreviations18():
    t = V16.t_abbreviations16()
    half = (len(ABBREVIATIONS18) + 1) // 2
    left, right = ABBREVIATIONS18[:half], ABBREVIATIONS18[half:]
    t['rows'] = [[left[k][0], left[k][1]] + (list(right[k]) if k < len(right) else ['', '']) for k in range(half)]
    return t


def t_concordance18(d, s):
    """V17's table of what the closest surveys conclude, corrected against the sources (verify/part00-02.md, part07-12.md)"""
    t = V17.t_concordance17(d, s)
    for r in t['rows']:
        if r[0] == 'Blockchain-based FL resists poisoning':
            r[1] = ('All 31 designs rated by @O100 claim it; the surveys doubt it, @O100 included (a poisoned update can be '
                    'verified only if the expected update is known), with @S006 and @S007')
        elif r[0] == 'Proof generation is the main obstacle to verifiable learning':
            r[2] = 'Proofs are measured on servers, cloud instances, laptops and one phone [@O097]; none on IoT gateways'
        elif r[0] == 'Proof of work is the mainstream consensus':
            r[1] = 'Called mainstream by @S018 and by @O100, whose own table marks it for 7 of 31 designs'
            r[2] = f"{s['appr_pow']} of the {s['appr_n']} compared approaches of 2022–2026 use proof of work"
    return t


def tables(d, s):      # noqa: F811
    t = _V17_TABLES(d, s)
    t['concordance'] = t_concordance18(d, s)
    t['abbreviations'] = t_abbreviations18()
    t['surveys'] = t_surveys18(d, s)
    t['questions'] = t_questions18()
    t['gaps'] = t_gaps18(d, s)
    t['rq'] = t_rq18()
    t['design'] = t_design18()
    t['evalplan'] = t_evalplan18()
    t['edpb'] = t_edpb18(d, s)
    t['defences'] = t_defences18(d, s)
    # V24 (1 Oct 2026): the 'Used for' column of the extraction form still named the questions of V15 (SQ1-SQ4 of the
    # topic outline); map each field to the five survey questions of Table IV and the sections that use it
    used_for = {'Aims and contributions': 'All', 'Setting': 'SQ1', 'Learning': 'SQ1', 'Privacy': 'SQ2, SQ3',
                'Ledger': 'SQ3, SQ5', 'Threats and defences': 'SQ3, SQ4', 'Evaluation': 'SQ1, SQ4',
                'Results and limitations': 'SQ2–SQ4', 'Open issues': 'Section VI'}
    for row in t['extraction']['rows']:
        if isinstance(row, list) and row[0] in used_for:
            row[2] = used_for[row[0]]
    # cells inherited from the V16 tables that cited works the review no longer cites (30 Sep 2026: no old literature
    # and nothing outside the corpus except the GDPR, PRISMA 2020 and the EDPB guidelines), re-cited to included studies
    recite = {'compromised devices feed botnets [@salim2020]': 'compromised devices feed botnets [@O001; @O015]',
              # V26 (2 Oct 2026): section numbers of the new structure
              'it already sees their raw data (Section IV)': 'it already sees their raw data (Section IV-A)'}
    for row in t['evalplan']['rows']:
        if row[-1] == 'Section VII-F':
            row[-1] = 'Section V-F'
    t['closest'] = t_closest26(d, s)
    # V26: one group for the checks that rest on a proof. The records split them by trusted set-up, but zkFL (O107)
    # does not state its set-up — it uses Halo2 "as used by Zcash", which Sheybani et al. (S025) describe as a PLONK-ish
    # system with Kate commitments — so the split is not supported for it; set-ups are given per design in Table 'closest'.
    rows, merged, k = t['approaches']['rows'], [], 0
    while k < len(rows):
        r = rows[k]
        if isinstance(r, dict) and r.get('group', '').startswith('The check rests on a proof'):
            members = []
            k += 1
            while k < len(rows) and not isinstance(rows[k], dict):
                members.append(rows[k]); k += 1
            if merged and isinstance(merged[-1], list) and merged[-1] and merged[-1][0] == '__proof__':
                merged[-1].extend(members)
            else:
                merged.append(['__proof__'] + members)
            continue
        merged.append(r); k += 1
    out = []
    for r in merged:
        if isinstance(r, list) and r and r[0] == '__proof__':
            members = sorted(r[1:], key=lambda m: (V16.year(d, m[0][2:-1]), d['refs'][m[0][2:-1]]['narrative_ieee']))
            out.append({'group': f'The check rests on a proof ({len(members)})'})
            out.extend(members)
        else:
            out.append(r)
    t['approaches']['rows'] = out
    for r in t['approaches']['rows']:
        if isinstance(r, list) and r and r[0] in ('[@N006]', '[@N017]'):
            r[1] = V16.SCHEME_OVERRIDE[r[0][2:-1]]
    for tab in t.values():
        for row in tab.get('rows', []):
            cells = row if isinstance(row, list) else []
            for j, c in enumerate(cells):
                if isinstance(c, str):
                    for x, y in recite.items():
                        c = c.replace(x, y)
                    cells[j] = c
    return t


def figures(d, s):     # noqa: F811
    f = _V17_FIGURES(d, s)
    f['roadmap'] = {'file': 'fig-roadmap.png', 'width_in': 6.5,
                    'caption': 'The five survey questions and the subsections that answer them: each is answered by the '
                               'fundamentals of its layer (Section IV) and by what the approaches do on it (Section V). '
                               'Sections VI to VIII draw on the answers to all five. The figure serves as a visual table of '
                               'contents.'}
    # V26 (2 Oct 2026): one branch / panel per layer; the taxonomy counts all primary studies (the inherited caption
    # said 66, the number of learning studies, although the figure counts every primary study)
    f['taxonomy'] = dict(f['taxonomy'], caption=(
        'Taxonomy of privacy-preserving and verifiable FL for NG-IoT, with one branch for each layer of the problem and '
        f"its survey question. Numbers give the primary studies classified under each leaf (of {s['primary']}; a study "
        'can fall under several leaves); threats are counted as the studies claim to address them.'))
    f['architecture'] = dict(f['architecture'], caption=(
        'Reference architecture: where the reviewed designs place their mechanisms on the NG-IoT tiers, and where the '
        'threats enter, labelled by layer. The ledger may hold local updates in plaintext or noised (U), encrypted updates '
        '(E), global models (G) or only commitments and proofs (C).'))
    f['agenda'] = {'file': 'fig-agenda.png', 'width_in': 6.3,
                   'caption': 'Reference design of the research agenda. IoT gateways act as FL clients and prove a simple '
                              'check on each update in zero knowledge; a permissioned ledger at the edge verifies the proofs '
                              'and records only commitments, proof outcomes and admission decisions. Numbers give the order '
                              'of a round: (1) commit to the update, (2) open the reference model, (3) prove the check, '
                              '(4) verify and select, (5) upload the selected updates and aggregate.'}
    return f
