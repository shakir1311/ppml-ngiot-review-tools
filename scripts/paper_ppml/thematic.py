#!/usr/bin/env python3
"""Counts and thematic tables of the PPML review (paper V29 onwards), built only from the evidence sheets
(search-ppml/evidence/sheets/<id>.json, form P1-P8 / S1-S8 of search-ppml/evidence/EXTRACTION-GUIDE.md) and the list of
included studies. Each table cell cites the studies it rests on, so every cell can be traced to a sheet answer, its page
and its quotation. Called by scripts/paper_ppml/data.py.
"""
import collections, json, re

slug = lambda x: re.sub(r'[^a-z0-9]+', '_', str(x).lower()).strip('_')
PHD = ['poisoning', 'byzantine-malicious', 'sybil-fake', 'free-riding']
THREAT_NAME = {'poisoning': 'Poisoning', 'backdoor': 'Backdoor', 'byzantine-malicious': 'Byzantine or malicious participants',
               'sybil-fake': 'Sybil or fake participants', 'free-riding': 'Free riding', 'inference-privacy-attack': 'Inference and other privacy attacks',
               'malicious-server-aggregator': 'Malicious or curious server or aggregator', 'collusion': 'Collusion',
               'dos-ddos': 'Denial of service', 'single-point-of-failure': 'Single point of failure', 'tampering': 'Tampering with records or models'}
MECH_NAME = {'DP': 'Differential privacy', 'LDP': 'Local differential privacy', 'HE': 'Homomorphic encryption',
             'SMPC': 'Secure multi-party computation', 'secret-sharing': 'Secret sharing', 'masking-secure-aggregation': 'Masking and secure aggregation',
             'TEE': 'Trusted execution environment', 'ZKP': 'Zero-knowledge proofs', 'functional-encryption': 'Functional encryption',
             'pseudonyms-anonymity': 'Pseudonyms and anonymity', 'encryption-in-transit-only': 'Encryption in transit only'}
SETTING_NAME = {'IoT-general': 'IoT (general)', 'IIoT': 'Industrial IoT', 'IoMT-healthcare': 'Medical IoT and healthcare', 'IoV-vehicular': 'Vehicular',
                'smart-grid-energy': 'Smart grid and energy', 'UAV-space': 'UAV and space–air–ground', 'smart-city-home': 'Smart city and home',
                'maritime': 'Maritime', 'supply-chain': 'Supply chain', 'communication-network': 'Communication networks'}
ENABLER_NAME = {'edge': 'edge computing', '5G-6G': '5G or 6G networks', 'cloud': 'cloud', 'MEC': 'multi-access edge computing',
                'fog': 'fog computing', 'none-stated': 'none stated'}
LAW_WORDS = {'CCPA': 'California Consumer Privacy Act'}          # an abbreviation used once is written out
ENABLER_SHORT = {'5G-6G': '5G/6G', 'none-stated': 'none stated'}
LEDGER_WORDS = {'PoW': 'proof of work', 'PoS': 'proof of stake', 'PoA': 'proof of authority',
                'consortium-permissioned': 'consortium or permissioned', 'not-stated': 'not stated', 'public': 'public', 'private': 'private',
                'Hyperledger-Fabric': 'Hyperledger Fabric', 'FISCO-BCOS': 'FISCO BCOS', 'logs-metadata': 'logs and metadata',
                'identities-keys': 'identities and keys', 'hashes-commitments': 'hashes and commitments', 'global-model': 'the global model',
                'protected-updates': 'protected updates', 'plain-updates': 'plain updates', 'reputation-scores': 'reputation scores',
                'rewards-payments': 'rewards and payments', 'record-audit': 'records and audits the training',
                'identity-access': 'identity and access control', 'incentive-reputation': 'incentives and reputation',
                'replaces-server': 'replaces the server', 'update-verification': 'verifies updates', 'proof-verification': 'verifies proofs',
                'aggregation': 'aggregates the updates'}
DATA_WORDS = {'raw-data': 'raw data', 'updates': 'updates', 'global-model': 'the global model', 'identity': 'identities'}
PARTY_WORDS = {'server-aggregator': 'the server or aggregator', 'other-participants': 'other participants', 'ledger-nodes': 'ledger nodes',
               'external-attacker': 'external attackers', 'public': 'the public'}
STATE_WORDS = {'not-addressed': 'not addressed', 'addressed': 'addressed', 'mentioned': 'mentioned', 'unclear': 'unclear', 'yes': 'yes', 'no': 'no'}
CHECK_NAME = {'test-accuracy-quality': 'accuracy or quality on test data', 'similarity-distance': 'similarity or distance between updates',
              'norm-bound': 'a norm bound on the update', 'correct-training': 'correct local training', 'correct-aggregation': 'correct aggregation',
              'identity-membership': 'identity or membership', 'contribution-reputation': 'contribution or reputation', 'anomaly-detection': 'anomaly detection'}
CHECKER_NAME = {'server': 'a server', 'committee-validators-miners': 'a committee, validators or miners', 'smart-contract': 'a smart contract',
                'peers-clients': 'peers or clients', 'TEE': 'a TEE', 'trusted-authority': 'a trusted authority'}
TRUST = {'server': 'the server', 'committee-validators-miners': 'an honest committee majority',
         'smart-contract': 'consensus and contract code', 'peers-clients': 'an honest peer majority',
         'TEE': 'the hardware', 'trusted-authority': 'the authority'}
# definitions settled in the claims audit of V38
LEARNING_ATTACKS = {'poisoning', 'backdoor', 'byzantine-malicious', 'sybil-fake', 'free-riding'}
attacks_learning = lambda sh: [x for x in L(sh, 'P5', 'tested') if x in LEARNING_ATTACKS]   # the three threats of SQ4 (II-E; V57)
NOT_MECHANISM = re.compile(r'data locality|instead of raw data|abstract only|named only', re.I)    # FL's own locality (EC4), or DP only named
mechanisms_used = lambda sh: {m for m in L(sh, 'P2', 'mechanisms') if not (str(m).startswith('other:') and NOT_MECHANISM.search(str(m)))}
DP_LAW = re.compile(r'\bGDPR\b|General Data Protection|\bCCPA\b|\bCPRA\b|\bHIPAA\b|\bPIPL\b|\bPIPEDA\b|\bLGPD\b|\bPDPA\b|\bEDPB\b|data protection', re.I)
IS_OTHER = lambda x: str(x) == 'other' or str(x).startswith('other:')     # not 'other-participants' (claims audit V38)
# the updates themselves are hidden from the party that aggregates (P2.hidden_from server-aggregator, for a design that protects its updates)
hides_updates_from_aggregator = lambda sh: 'updates' in L(sh, 'P2', 'protects') and 'server-aggregator' in L(sh, 'P2', 'hidden_from')
network_own = lambda sh: V(sh, 'P1', 'network_measured') == 'yes' and V(sh, 'P1', 'network_measured_own') is not False
protects_updates = lambda sh: 'updates' in L(sh, 'P2', 'protects') and bool(mechanisms_used(sh))   # protected from some party
O = lambda x: 'other' if IS_OTHER(x) else x          # every "other: …" value counts as one category in tables
LAYER = [('fabric', 'NG-IoT fabric'), ('privacy', 'Privacy plane'), ('trust', 'Trust plane'), ('attacks', 'Attacks and defences'), ('regulation', 'Regulatory layer')]
ANGLE = [('poisoning', 'Poisoning'), ('malicious_fake', 'Malicious or fake'), ('free_riding', 'Free riding'), ('verification', 'Verification'),
         ('zkp', 'ZKPs'), ('blockchain', 'Blockchain')]
MARK = {'subject': 'Yes', 'mentioned': 'Partial', 'absent': 'No'}    # in words, as Appendix B (the author: no circles)

ABBREVIATIONS = [    # every abbreviation the review may use: (short form, long form as defined at first use in the body);
    # the List of Abbreviations shows only those the built text uses (build.py), and the build checks the rules on them
    ('5G / 6G', 'fifth / sixth generation of mobile networks'), ('AI', 'artificial intelligence'), ('B5G', 'beyond 5G'),
    ('BCFL', 'blockchain-based federated learning'), ('BlockFL', 'blockchained federated learning'),
    ('C1–C5', 'conditions of the research gap'), ('non-IID', 'non-independent and identically distributed'), ('CBAM', 'Carbon Border Adjustment Mechanism'), ('CSP', 'cloud service provider'),
    ('DAG', 'directed acyclic graph'), ('DP', 'differential privacy'), ('EC1–EC9', 'exclusion criteria'),
    ('EDPB', 'European Data Protection Board'), ('EU', 'European Union'), ('FedAvg', 'federated averaging'),
    ('FL', 'federated learning'), ('FLchain', 'federated learning combined with blockchain'),
    ('GDPR', 'General Data Protection Regulation'), ('HE', 'homomorphic encryption'),
    ('HIPAA', 'Health Insurance Portability and Accountability Act'), ('IC1–IC7', 'inclusion criteria'),
    ('IIoT', 'Industrial Internet of Things'), ('IoMT', 'Internet of Medical Things'), ('IoT', 'Internet of Things'),
    ('IoV', 'Internet of Vehicles'), ('LDP', 'local differential privacy'), ('MAE', 'mean absolute error'),
    ('MEC', 'multi-access edge computing'), ('ML', 'machine learning'), ('NG-IoT', 'next-generation Internet of Things'),
    ('PBFT', 'practical Byzantine fault tolerance'), ('PoW', 'proof of work'), ('PPML', 'privacy-preserving machine learning'),
    ('PRISMA', 'Preferred Reporting Items for Systematic Reviews and Meta-Analyses'),
    ('QA1–QA6', 'quality-appraisal questions for primary studies'), ('QS1–QS4', 'quality-appraisal questions for surveys'),
    ('RFID', 'radio-frequency identification'), ('RQ', 'research question'), ('RSU', 'roadside unit'),
    ('SGX', 'Software Guard Extensions'), ('SMPC', 'secure multi-party computation'), ('SQ', 'survey question'),
    ('SVM', 'support vector machine'), ('TA', 'trusted authority'), ('TEE', 'trusted execution environment'),
    ('UAV', 'unmanned aerial vehicle'), ('ZKP', 'zero-knowledge proof'),
    ('zk-SNARK', 'zero-knowledge succinct non-interactive argument of knowledge')]
# label families: numbered codes explained where first used (e.g. "inclusion criterion IC3"), listed, not spelled out as "(IC)"
LABEL_FAMILIES = {'C1–C5': r'C[1-5][a-c]?', 'EC1–EC9': r'EC\d', 'IC1–IC7': r'IC\d', 'QA1–QA6': r'QA\d', 'QS1–QS4': r'QS\d'}


def cites(ids):
    ids = sorted(set(ids))
    return '[' + '; '.join(f'@{i}' for i in ids) + ']' if ids else '–'


def V(sheet, key, field, default=None):
    """the value of a field: in the named answer, else in whichever answer holds it (the form of 15 October 2026 merged
    the answers to one per review question; a field name occurs in one answer only)"""
    A = sheet.get('answers', {})
    vals = ((A.get(key, {}) or {}).get('values') or {})
    if field in vals:
        return vals[field]
    for other in A.values():
        ov = (other or {}).get('values') or {}
        if field in ov:
            return ov[field]
    return default


def L(sheet, key, field):
    v = V(sheet, key, field, [])
    return v if isinstance(v, list) else ([v] if v not in (None, '') else [])


def split(S, fin):
    kind = {r['corpus_id']: r['kind'] for r in fin}
    prim = {k: v for k, v in S.items() if kind.get(k) == 'primary'}
    sec = {k: v for k, v in S.items() if kind.get(k) == 'secondary'}
    return prim, sec


def stats(S, fin):
    s = {}
    prim, sec = split(S, fin)
    s['sheets'], s['sheets_primary'], s['sheets_secondary'] = len(S), len(prim), len(sec)
    import check_sheets as CS                         # the allowed values: every category gets a count, zero included
    def count(prefix, D, key, field):
        for v in (CS.ALLOWED.get(key, {}).get(field) or []):
            if isinstance(v, str):
                s[f'{prefix}_{slug(v)}'] = 0
        for v, n in collections.Counter(x for sh in D.values() for x in set(L(sh, key, field))).items():
            s[f'{prefix}_{slug(v)}'] = n
        s[f'{prefix}_other'] = sum(1 for sh in D.values() if any(IS_OTHER(x) for x in L(sh, key, field)))
    count('set', prim, 'P1', 'settings')
    count('en', prim, 'P1', 'enablers')
    count('fl', prim, 'P1', 'fl')
    s['device_measured'] = sum(V(sh, 'P1', 'device_measured') == 'yes' for sh in prim.values())
    s['network_measured'] = sum(V(sh, 'P1', 'network_measured') == 'yes' for sh in prim.values())
    s['en_5g_link'] = sum('5G-6G' in L(sh, 'P1', 'enablers') and V(sh, 'P1', 'network_measured') == 'yes' for sh in prim.values())   # 5G made visible (V41)
    count('mech', prim, 'P2', 'mechanisms')
    count('prot', prim, 'P2', 'protects')
    count('hid', prim, 'P2', 'hidden_from')
    s['hid_server_aggregator'] = sum(1 for sh in prim.values() if hides_updates_from_aggregator(sh))   # the updates themselves (claims audit V39)
    s['mech_two_or_more'] = sum(len(mechanisms_used(sh) - {'encryption-in-transit-only', 'pseudonyms-anonymity'}) >= 2 for sh in prim.values())
    count('ledger', prim, 'P3', 'ledger')
    count('platform', prim, 'P3', 'platform')
    count('cons', prim, 'P3', 'consensus')
    count('onchain', prim, 'P3', 'on_chain')
    count('role', prim, 'P3', 'roles')
    count('chk', prim, 'P4', 'checked')
    count('checker', prim, 'P4', 'checker')
    count('sees', prim, 'P4', 'checker_sees_update')
    s['zk_used'] = sum(V(sh, 'P4', 'zk_used') is True for sh in prim.values())
    s['zk_check_only'] = sum(V(sh, 'P4', 'zk_used') is True and 'ZKP' not in L(sh, 'P2', 'mechanisms') for sh in prim.values())
    about = {'bounded', 'training', 'similarity'}                 # proofs about the update itself or the training behind it
    s['zk_about_update'] = sum(V(sh, 'P4', 'zk_used') is True and bool(set(L(sh, 'P4', 'zk_shows')) & about) for sh in prim.values())
    s['zk_not_update'] = s['zk_used'] - s['zk_about_update']
    count('zkshows', {k: v for k, v in prim.items() if V(v, 'P4', 'zk_used') is True}, 'P4', 'zk_shows')
    count('zkonchain', {k: v for k, v in prim.items() if V(v, 'P4', 'zk_used') is True}, 'P4', 'zk_on_chain')
    for t in THREAT_NAME:
        cl = [k for k, sh in prim.items() if t in L(sh, 'P5', 'claimed')]
        s[f'claimed_{slug(t)}'] = len(cl)
        s[f'tested_{slug(t)}'] = sum(1 for k in cl if t in L(prim[k], 'P5', 'tested'))
        s[f'tested_any_{slug(t)}'] = sum(1 for sh in prim.values() if t in L(sh, 'P5', 'tested'))
    s['no_attack_tested'] = sum(1 for sh in prim.values() if not attacks_learning(sh))
    s['no_test_at_all'] = sum(1 for sh in prim.values() if not L(sh, 'P5', 'tested'))
    s['phd_claimed_any'] = sum(1 for sh in prim.values() if set(PHD) & set(L(sh, 'P5', 'claimed')))
    s['phd_tested_any'] = sum(1 for sh in prim.values() if set(PHD) & set(L(sh, 'P5', 'tested')))
    s['with_datasets'] = sum(1 for sh in prim.values() if L(sh, 'P6', 'datasets'))
    s['with_baselines'] = sum(1 for sh in prim.values() if L(sh, 'P6', 'baselines'))
    s['code_yes'] = sum(V(sh, 'P6', 'code') == 'yes' for sh in prim.values())
    s['laws_named'] = sum(1 for sh in prim.values() if any(DP_LAW.search(str(x)) for x in L(sh, 'P7', 'laws')))   # data-protection laws only
    s['laws_any_named'] = sum(1 for sh in prim.values() if L(sh, 'P7', 'laws'))
    s['gdpr_named'] = sum(1 for sh in prim.values() if any('gdpr' in str(x).lower() for x in L(sh, 'P7', 'laws')))
    count('pdchain', prim, 'P7', 'personal_data_on_chain')
    count('erasure', prim, 'P7', 'erasure')
    s['sec_trust_follows_angles'] = int(all((V(sh, 'S2', 'trust') == 'subject') ==
                                            ('subject' in (V(sh, 'S4', 'blockchain'), V(sh, 'S4', 'verification'))) for sh in sec.values()))
    lowq = [qa_secondary(sh) for sh in sec.values() if qa_secondary(sh)[0] < 1]   # surveys that do not fully name their databases
    s['sec_qs1_below'] = len(lowq)
    s['sec_no_db_period_count'] = sum(q[0] == 0 and q[1] == 0 and q[2] == 0 for q in lowq)
    for k, _ in LAYER:
        for m in ('subject', 'mentioned', 'absent'):
            s[f'layer_{k}_{m}'] = sum(V(sh, 'S2', k) == m for sh in sec.values())
    s['sec_layers3'] = sum(sum(V(sh, 'S2', k) == 'subject' for k, _ in LAYER) >= 3 for sh in sec.values())
    s['sec_layers_max'] = max([sum(V(sh, 'S2', k) == 'subject' for k, _ in LAYER) for sh in sec.values()] or [0])
    s['sec_all_five'] = sum(all(V(sh, 'S2', k) == 'subject' for k, _ in LAYER) for sh in sec.values())
    for k, _ in ANGLE:
        for m in ('subject', 'mentioned', 'absent'):
            s[f'sang_{k}_{m}'] = sum(V(sh, 'S4', k) == m for sh in sec.values())
    s['sec_edpb'] = sum(V(sh, 'S5', 'edpb') is True for sh in sec.values())
    s['sec_ai_act'] = sum(V(sh, 'S5', 'ai_act') is True for sh in sec.values())
    s['sec_gdpr'] = sum(1 for sh in sec.values() if any('gdpr' in str(x).lower() for x in L(sh, 'S5', 'laws')))
    count('smech', sec, 'S3', 'mechanisms')
    fy = {r['corpus_id']: int(r['year']) for r in fin}
    zk = [k for k, sh in prim.items() if V(sh, 'P4', 'zk_used') is True]
    s['zk_y2025_on'] = sum(fy[k] >= 2025 for k in zk)
    s['zk_y2026'] = sum(fy[k] == 2026 for k in zk)
    s['prim_y2026'] = sum(fy[k] == 2026 for k in prim)
    s['sec_y2026'] = sum(fy[k] == 2026 for k in sec)
    s['prim_y2025_on'] = sum(fy[k] >= 2025 for k in prim)
    s['vehicular_y2025_on'] = sum(1 for k in prim if fy[k] >= 2025 and 'IoV-vehicular' in L(prim[k], 'P1', 'settings'))
    return s                                          # the gap counts are set with the gap table (tables())


# The conditions of the research gap follow the spine strictly (the author, 12 October 2026): one condition per layer,
# numbered like its survey question; C4 has one part for each of the three threats of SQ4. A condition is met only where the
# record shows it; absence means that the study does not report it.
GAP_CONDITIONS = [
    ('C1', 'SQ1', 'a cost of the design measured on device-class hardware'),
    ('C2', 'SQ2', 'no party that checks or aggregates sees an individual update, in full, in part or noised'),
    ('C3', 'SQ3', 'the ledger itself checks the updates: its nodes or contracts check their content, or verify a proof about each '
                  'update or its training, by the relation the study states'),
    ('C4', 'SQ4', 'a test of the design by an attack, reported for (a) poisoning, backdoors included, (b) malicious or fake '
                  'participants and (c) free riding'),
    ('C5', 'SQ5', 'its ledger holds no personal records (none that remain personal data wherever they relate to a person, by the '
                  'criteria of the EDPB guidelines), or the design provides a way to erase or redact data on its ledger')]
GAP_COLUMNS = ['C1', 'C2', 'C3', 'C4a', 'C4b', 'C4c', 'C5']        # "Met" counts these seven
GAP_THREATS = {'C4a': {'poisoning', 'backdoor'}, 'C4b': {'byzantine-malicious', 'sybil-fake'}, 'C4c': {'free-riding'}}
GAP_MEANING = {c: m for c, _, m in GAP_CONDITIONS if c != 'C4'}  # the seven conditions in words (the gap-conditions table)
GAP_MEANING.update({'C4a': 'a test of the design by an attack reported for poisoning, backdoors included',
                    'C4b': 'a test of the design by an attack reported for malicious or fake participants',
                    'C4c': 'a test of the design by an attack reported for free riding'})
GAP_SHORT = {'C1': 'Cost on devices', 'C2': 'No party sees an update', 'C3': 'Ledger checks the updates', 'C4a': 'Poisoning tested',
             'C4b': 'Malicious or fake tested', 'C4c': 'Free riding tested', 'C5': 'No personal records, or erasure'}


def gap_conditions(k, sh, described_only=False, unclear_as_met=False):
    """the seven condition columns of one primary study, as booleans (C4a-c from the tests the study reports; with
    described_only, a test whose attack the study does not describe does not count; with unclear_as_met, an unclear answer on
    who sees the update counts as not seeing it)"""
    tested = threats_of(k, sh, 'tested')
    if described_only:
        tested = tested - ATTACK_NOT_DESCRIBED.get(k, set())
    sees = V(sh, 'P4', 'checker_sees_update')
    unseen = ('no', 'no-check', 'unclear') if unclear_as_met else ('no', 'no-check')
    c = {'C1': V(sh, 'P1', 'device_measured') == 'yes',
         'C2': hidden_kind(sh) == 'hidden' and sees in unseen,          # noise alone leaves a noised update visible
         'C3': ledger_checks_updates(k, sh),
         'C5': onchain_reading(sh) in ('B', 'C') or V(sh, 'P7', 'erasure') == 'addressed'}
    for col, tags in GAP_THREATS.items():
        c[col] = bool(tested & tags)
    return {col: c[col] for col in GAP_COLUMNS}


def gap_matrix(prim, **kw):
    """per study: its seven condition columns and the number met (a plain count; no condition is weighted or merged)"""
    out = {}
    for k, sh in sorted(prim.items()):
        c = gap_conditions(k, sh, **kw)
        out[k] = (c, sum(c.values()))
    return out


def cite_lists(S, fin):
    """Lists of studies behind the counts that the text cites ({{C:key}} in the parts; build/cites.json)."""
    prim, _ = split(S, fin)
    C = {}
    def add(key, cond):
        C[key] = sorted(k for k, sh in prim.items() if cond(sh))
    add('device_measured', lambda sh: V(sh, 'P1', 'device_measured') == 'yes')
    add('network_measured', lambda sh: V(sh, 'P1', 'network_measured') == 'yes')
    add('network_measured_own', network_own)
    add('en_5g_6g', lambda sh: '5G-6G' in L(sh, 'P1', 'enablers'))
    add('en_5g_link', lambda sh: '5G-6G' in L(sh, 'P1', 'enablers') and V(sh, 'P1', 'network_measured') == 'yes')
    add('platform_simulated', lambda sh: 'simulated' in L(sh, 'P3', 'platform'))
    add('onchain_plain_updates', lambda sh: 'plain-updates' in L(sh, 'P3', 'on_chain'))
    add('sees_no', lambda sh: V(sh, 'P4', 'checker_sees_update') == 'no')
    add('code_yes', lambda sh: V(sh, 'P6', 'code') == 'yes')
    add('laws_named', lambda sh: any(DP_LAW.search(str(x)) for x in L(sh, 'P7', 'laws')))
    add('pd_yes', lambda sh: V(sh, 'P7', 'personal_data_on_chain') == 'yes')
    add('onchain_b', lambda sh: onchain_reading(sh) in ('B', 'C'))
    add('hk_noised', lambda sh: hidden_kind(sh) == 'noised')
    C['cc_content_no'] = sorted(k for k, sh in prim.items() if check_class(k, sh) == 'content' and V(sh, 'P4', 'checker_sees_update') == 'no')
    C['cc_aggregation_no'] = sorted(k for k, sh in prim.items() if check_class(k, sh) == 'aggregation' and V(sh, 'P4', 'checker_sees_update') == 'no')
    C['ledger_checks_updates'] = sorted(k for k, sh in prim.items() if ledger_checks_updates(k, sh))
    C['ledger_checks_aggregation'] = sorted(k for k, sh in prim.items() if ledger_checks_aggregation(k, sh))
    G = gap_matrix(prim)
    for col in GAP_COLUMNS:
        C[f'gap_{col.lower()}'] = sorted(k for k, (c, _) in G.items() if c[col])
    top = max(m for _, m in G.values())
    C['gap_closest'] = sorted(k for k, (_, m) in G.items() if m == top)
    C['gap_next'] = sorted(k for k, (_, m) in G.items() if m == top - 1)
    C['erasure_addressed'] = sorted(k for k, sh in prim.items() if V(sh, 'P7', 'erasure') == 'addressed')
    C['no_pd_on_ledger'] = sorted(k for k, sh in prim.items() if onchain_reading(sh) in ('B', 'C'))
    C['byz_consensus'] = sorted(BYZ_CONSENSUS)
    C['attack_not_described'] = sorted(ATTACK_NOT_DESCRIBED)
    for z in ('identity', 'aggregation', 'inference', 'training', 'bounded', 'similarity'):
        add(f'zkshows_{z}', lambda sh, z=z: V(sh, 'P4', 'zk_used') is True and z in L(sh, 'P4', 'zk_shows'))
    for t in THREAT_NAME:
        add(f'tested_{slug(t)}', lambda sh, t=t: t in L(sh, 'P5', 'tested'))
    return C



# ------------------------------------------------------------------ quality appraisal (Yes 1, Partial 0.5, No 0)
QA_PRIMARY = [('QA1', 'Is the evaluation run on named data sets?'), ('QA2', 'Is the design compared with named baselines?'),
              ('QA3', 'Does it report a test, by an attack, of each attack on the learning or on privacy that it claims to counter?'),
              ('QA4', 'Does it report a cost measured on device-class hardware or over a network link?'),
              ('QA5', 'Does it give a link to its code?'), ('QA6', 'Are its claims, values and results reported consistently?')]
QA_SECONDARY = [('QS1', 'Are the databases searched named?'), ('QS2', 'Is the period covered stated?'),
                ('QS3', 'Is the number of studies reviewed stated?'), ('QS4', 'Does the survey state its own limitations?')]
QA_DESCRIPTION = {
    'QA1': 'Yes: at least one named data set; Partial: data sets described but none named; No: no data set.',
    'QA2': 'Yes: at least one named scheme compared with; No: none.',
    'QA3': 'Yes: the study reports an experiment or simulation that runs every attack on the learning or on privacy it claims to counter; Partial: some of them; No: none reported, or none claimed.',
    'QA4': 'Yes: the study reports a cost of the design measured on device-class hardware or over a network link; Partial: a network link measured for a baseline only; No: neither reported.',
    'QA5': 'Yes: the study gives a link to its code; No: no link given.',
    'QA6': 'Yes: no inconsistency found; Partial: one minor inconsistency; No: a value, claim or protocol step that differs between two places, or a result that the study claims but does not report.',
    'QS1': 'Yes: the databases or sources searched for the review are named; Partial: named for part of the review only; No: not named.',
    'QS2': 'Yes: the period covered is stated; Partial: for part of the review only, approximately, or read off a figure; No: not stated.',
    'QS3': 'Yes: the number of studies reviewed is stated; Partial: for part of the review only, approximately, or read off a figure; No: not stated.',
    'QS4': 'Yes: the survey states its own limitations; Partial: its scope only; No: none stated.'}
QA_RELEVANT = {'QA1': 'SQ4', 'QA2': 'SQ4', 'QA3': 'SQ4', 'QA4': 'SQ1', 'QA5': 'SQ1–SQ5', 'QA6': 'SQ1–SQ5',
               'QS1': 'SQ1–SQ5', 'QS2': 'SQ1–SQ5', 'QS3': 'SQ1–SQ5', 'QS4': 'SQ1–SQ5'}
TESTABLE = {'poisoning', 'backdoor', 'byzantine-malicious', 'sybil-fake', 'free-riding', 'inference-privacy-attack', 'collusion', 'malicious-server-aggregator'}
QA_LOW = 3                                                    # primary studies scoring below this are set aside in the sensitivity check


def _consistency():
    import pathlib as _p
    f = _p.Path(__file__).resolve().parents[2] / 'search-ppml' / 'evidence' / 'QA-CONSISTENCY-2026-10-05.json'
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else {'no': {}, 'partial': {}}


CHECKS_OF_LEARNING = {'test-accuracy-quality', 'similarity-distance', 'norm-bound', 'correct-training', 'correct-aggregation',
                      'anomaly-detection', 'contribution-reputation'}
ZK_COVERS = {'training': 'correct-training', 'bounded': 'norm-bound', 'aggregation': 'correct-aggregation', 'similarity': 'similarity-distance'}


def verification_yes(k, sh):
    """the verification angle and its column of the spine table: the content of updates, the training or the aggregation
    checked by means other than a ZKP (II-A); a check that the record says no party runs does not count (check_class)"""
    return verifies_content(sh) and check_class(k, sh) in ('content', 'aggregation')


def verifies_content(sh):
    """the verification angle of Section IV-B (as data.angle_marks): the content of updates, training or aggregation checked by
    means other than a ZKP; an explicit verification_other_means in the record decides"""
    v = V(sh, 'P4', 'verification_other_means')
    if isinstance(v, bool):
        return v
    checks = set(L(sh, 'P4', 'checked')) & CHECKS_OF_LEARNING
    if V(sh, 'P4', 'zk_used') is True:
        checks -= {ZK_COVERS[x] for x in {str(y).split(':')[0].strip() for y in L(sh, 'P4', 'zk_shows')} if x in ZK_COVERS}
    return bool(checks)


# the coverage views (Tables VII and VIII, Figs. 6 and 7) follow the spine: one column per layer, the trust plane (SQ3) and the
# attacks (SQ4) by their three focus angles each
SURVEY_COVER = [('S2', 'fabric', 'SQ1 NG-IoT fabric'), ('S2', 'privacy', 'SQ2 Privacy mechanisms'), ('S4', 'verification', 'SQ3 Verification of learning'),
                ('S4', 'zkp', 'SQ3 ZKPs'), ('S4', 'blockchain', 'SQ3 Blockchain'), ('S4', 'poisoning', 'SQ4 Poisoning'),
                ('S4', 'malicious_fake', 'SQ4 Malicious or fake participants'), ('S4', 'free_riding', 'SQ4 Free riding'), ('S2', 'regulation', 'SQ5 Data-protection law')]
PRIM_COVER = ['SQ1 Fabric (C1)', 'SQ2 Privacy (C2)', 'SQ3 Verification', 'SQ3 ZKPs', 'SQ3 Blockchain (C3)', 'SQ4 Poisoning (C4a)',
              'SQ4 Malicious or fake (C4b)', 'SQ4 Free riding (C4c)', 'SQ5 Regulation (C5)']   # the spine; the table of Section VI-A
PRIM_COVER_CONDITION = dict(zip(PRIM_COVER, ['C1', 'C2', None, None, 'C3', 'C4a', 'C4b', 'C4c', 'C5']))
PRIM_LABEL = {'SQ3 Verification': 'Updates checked (not by ZKP)', 'SQ3 ZKPs': 'ZKP about the update'}   # the two columns that are no condition
PRIM_HEAD = {c: f"{c.split()[0]} {GAP_SHORT[PRIM_COVER_CONDITION[c]] if PRIM_COVER_CONDITION[c] else PRIM_LABEL[c]}" for c in PRIM_COVER}
# each column is labelled by what it grades (the author, 13 October 2026: no label may mislead); the condition columns carry the
# condition's short name, so Table V, Fig. 6 and the gap tables use the same words; no condition codes in the table
COLUMN_OF = {v: k for k, v in PRIM_COVER_CONDITION.items() if v}
PRIM_COVER_NOTE = ('Columns by layer and focus angle, each labelled by what it grades: SQ1 NG-IoT fabric, Cost on devices; SQ2 privacy plane, '
                   'No party sees an update; SQ3 trust plane, Updates checked (not by ZKP), ZKP about the update and Ledger checks the updates, '
                   'its three means of checking; SQ4 attacks and defences, Poisoning tested, Malicious or fake tested and Free riding tested; '
                   'SQ5 regulatory layer, No personal records, or erasure. Yes / Partial / No. Cost on devices: a cost of the design measured '
                   'on device-class hardware / measured over a network link only / neither reported. No party sees an update: no party that checks '
                   'or aggregates sees an individual update, in full, in part or noised / the updates are protected, but the aggregator or a '
                   'checking party sees them, in part or noised, or the study does not say / the updates are not protected (an update encrypted '
                   'under a key that the aggregating party holds is not kept from it). Updates checked (not by ZKP): the content of updates, their '
                   'training or the aggregation checked by means other than a ZKP / identities, signatures, format, the global model or a check '
                   'that no party runs only, or a check by a ZKP / no check. ZKP about the update: a proof of a bound on the update or of its '
                   'training, with the relation stated / another proof / none. Ledger checks the updates: the ledger itself checks the updates, by '
                   'checking their content or verifying a proof about each update or its training with the relation stated / it checks the '
                   'aggregation, other proofs, signatures, deadlines or format / it only records, aggregates or admits. SQ4: a test of the design '
                   'by an attack reported († attack not described) / claimed with no test reported (malicious or fake: or countered only by an '
                   'identity check) / not claimed; one test in which malicious participants send corrupted updates counts for both poisoning and '
                   'malicious participants (Section II-A); Byzantine claims about the consensus do not count. No personal records, or erasure: '
                   'the ledger holds no personal records by the criteria of the EDPB guidelines, or the design can erase or redact data on its '
                   'ledger / a data-protection law named, or erasure mentioned / neither. Rows in reference order; the last row counts the studies '
                   'graded Yes. Focus angles (Section IV-B): verification counts Yes, ZKPs and the threats Yes or Partial.')


# ------------------------------------------------------------------ classifications added after the independent review of V55
# Each rests on the words of the author-verified answers (quoted beside it); the rules are listed in the supplementary
# material (S2), and verify_tables.py recomputes every count from them.

# What a design checks (P4.checked), the strongest item first. A content check examines individual updates or their
# training; 'other' values count as content where the answer says the updates themselves are checked.
CONTENT_CHECKS = {'test-accuracy-quality', 'similarity-distance', 'norm-bound', 'anomaly-detection', 'correct-training'}
CONTENT_OTHER = re.compile(r'local updates|model verification by miners|validate received updates|committed update polynomial|'
                           r'model updates called', re.I)
CHECK_CLASS_OVERRIDE = {
    'N020': 'aggregation',   # P4: "individual local models are not validated: the aggregator tests the aggregated global model"
    'n3813': 'other',        # P4: the gradient filter is named "only" in "the poisoning proof"; "no checker is assigned"
}
CHECK_CLASSES = [('content', 'The content of individual updates or their training'), ('aggregation', 'The aggregation only'),
                 ('participants', 'Identities, signatures, format or contributions only'),
                 ('other', 'An inference or other records only'), ('none', 'Nothing')]


def check_class(k, sh):
    if k in CHECK_CLASS_OVERRIDE:
        return CHECK_CLASS_OVERRIDE[k]
    ch = set(L(sh, 'P4', 'checked'))
    if ch & CONTENT_CHECKS or any(IS_OTHER(c) and CONTENT_OTHER.search(str(c)) for c in ch):
        return 'content'
    if 'correct-aggregation' in ch:
        return 'aggregation'
    if ch & {'identity-membership', 'contribution-reputation'}:
        return 'participants'
    return 'none' if not ch or ch == {'none'} else 'other'


SEES_ORDER = [('yes', 'in full'), ('partly', 'in part or noised'), ('no', 'not at all'), ('unclear', 'unclear')]

# Byzantine claims that concern the consensus (validators or committee members), not participants of the learning
BYZ_CONSENSUS = {
    'N017': 'compromised validation-committee nodes and the leader',   # P5: "The byzantine-malicious tag refers only to these compromised committee nodes and the leader"
    'N020': 'Byzantine members of the regulatory committee',            # P5: "tolerated while at least two-thirds are honest"
    'n3102': 'Byzantine validators',                                     # P5: "Byzantine validators (up to 33 % malicious)"
}


def threats_of(k, sh, field):
    """the threats a study claims or tests, with a consensus-level Byzantine claim kept apart from malicious participants"""
    out = set(L(sh, 'P5', field))
    if k in BYZ_CONSENSUS and 'byzantine-malicious' in out:
        out = (out - {'byzantine-malicious'}) | {'byzantine-consensus'}
    return out


# Tested threats whose attack the paper does not describe (results reported without an attack set-up)
ATTACK_NOT_DESCRIBED = {
    'n2912': {'poisoning', 'byzantine-malicious'},   # P5: "the attack itself is not described and the text gives no malicious share"
    'r0323': {'byzantine-malicious'},                # P5: "The attack the malicious clients run is not described"
    'n3102': {'poisoning', 'sybil-fake'},            # P5: "No attack set-up or attacker share is described for the Table 7 attacks"
    'n3348': {'sybil-fake', 'collusion'},            # P5: the Sybil and collusion scenarios use "data from its existing Byzantine-node simulations"
}

# What the zero-knowledge proofs prove: the relation as the record states it, not the authors' description of it
ZK_RELATION = {
    'N015': 'bound', 'n1640': 'bound', 'n3348': 'bound',   # Lp-norm below a bound; gradient in an interval; squared norm at least θ
    'n3910': 'training',                                    # "gradient was computed by valid training steps on data of authorised origin"
    'n2723': 'unspecified-update', 'n1749': 'unspecified-update',   # constraints or "valid training" claimed; circuit not stated or given
    'n2405': 'commitment',                                  # "evaluation y = Fi(α) at a random challenge", presented as legitimate training
    'n0414': 'inference', 'n2721': 'inference',             # "the SVM decision function f(x) for a new example x"; a public model on a committed input
    'O108': 'aggregation', 'n3378': 'aggregation',
    'n2912': 'identity', 'n3855': 'identity', 'n0207': 'identity', 'N012': 'identity', 'n3299': 'identity',
    'n0763': 'other', 'n3813': 'other',                     # knowledge of a committed training loss; supply-chain records
    'n3102': 'unspecified', 'n3686': 'unspecified', 'r0202': 'unspecified'}   # "statement not given" / "not specified"
ZK_RELATIONS = [('bound', 'A norm or range bound on the committed update'),
                ('training', 'Correct training of the update, with the relation stated'),
                ('unspecified-update', 'Correct training or constraints on the update, relation not stated'),
                ('commitment', 'Consistency of the update with its commitment, presented as proof of training'),
                ('inference', 'An inference made with a committed or public model'),
                ('aggregation', 'Correct aggregation'),
                ('identity', 'Identity, membership or eligibility'),
                ('other', 'Other records (a training loss; supply-chain data)'),
                ('unspecified', 'A statement the study does not specify')]
ZK_COST = {   # the costs each record reports, in its own figures (P4); '' where none is reported
    'N015': 'proving time grows linearly with the update size', 'n1640': '', 'n3348': 'proof about 256 bytes',
    'n3910': 'proving about 1.8 s (Raspberry Pi) and 0.9 s (Jetson Nano); proof about 2.3 KB; verification under 150 ms',
    'n2723': 'proofs a few hundred bytes', 'n1749': '', 'n2405': 'about 0.123 s each to prove and to verify',
    'n0414': 'verification 689,450 gas', 'n2721': 'about 8.15 s and 1050.25 MB per proof on a cloud server',
    'O108': 'about 1.4 million gas (10 clients) and 1.8 million (20 clients); prover memory up to about 12 GB',
    'n3378': 'about 4.65 million gas for 5 proofs, deployment included', 'N012': '157 970 gas at registration; 0.03 s per client',
    'n3299': 'proving 1.12-1.15 s', 'n2912': 'verification latency from 0.41 ms to 0.52 ms', 'n3855': '', 'n0207': '',
    'n0763': '', 'n3813': '', 'n3102': 'proving 420–480 ms on an Intel Xeon; proofs about 128 bytes', 'n3686': '',
    'r0202': 'verification 1.2 s on average'}

# Kinds of protection (Section III-B): what a mechanism can hide from the party that aggregates
CONFIDENTIALITY = {'HE', 'SMPC', 'secret-sharing', 'masking-secure-aggregation', 'TEE', 'functional-encryption'}
PROTECTION_KINDS = [
    ('Confidentiality of the update', ['HE', 'secret-sharing', 'SMPC', 'masking-secure-aggregation', 'TEE', 'functional-encryption']),
    ('Output privacy', ['DP', 'LDP']),
    ('Unlinkability', ['pseudonyms-anonymity']),
    ('Proofs that hide their witness', ['ZKP']),
    ('Transport only', ['encryption-in-transit-only'])]


NOISED_BEFORE_AGGREGATOR = {
    'O043': 'P2: "the noise-added models themselves are broadcast as blockchain transactions and seen by the other participants"',
    'r0159': 'P2: "after local training each client adds noise to its final gradient … before submission"; "miners receive the noised updates"',
    'n2405': 'P2: "Updates are clipped and perturbed with calibrated Gaussian DP noise before transmission"; "peers receive each update in noised form"',
}


def hidden_kind(sh):
    """how the updates are kept from the server or aggregator: 'hidden' (a confidentiality mechanism), 'noised' (DP or LDP
    only), or '' (the aggregator sees them, or nothing is protected)"""
    if not hides_updates_from_aggregator(sh):
        return 'noised' if sh.get('id') in NOISED_BEFORE_AGGREGATOR else ''
    used = mechanisms_used(sh)
    return 'hidden' if used & CONFIDENTIALITY else ('noised' if used & {'DP', 'LDP'} else '')


# What a ledger holds, read against the EDPB guidelines (Section III-E): 'A' remains personal data wherever it relates to a
# person (in the clear, encrypted, an identifier, a score about a participant); 'B' depends on the scheme (a salted or keyed
# hash remains personal data, a perfectly hiding commitment does not once the data and its opening are deleted; models,
# aggregates and logs case by case); 'C' a proof, which reveals nothing about its witness
EDPB_BAND = {'plain-updates': 'A', 'protected-updates': 'A', 'identities-keys': 'A', 'reputation-scores': 'A',
             'rewards-payments': 'A', 'hashes-commitments': 'B', 'global-model': 'B', 'logs-metadata': 'B', 'proofs': 'C'}
OTHER_ON_CHAIN_A = re.compile(r'COVID|data samples|training data|trained data|encrypted data|data records|secret shares of query data|'
                              r'predicted energy data', re.I)   # a household site's forecast relates to the people in it (V57, coherence check)


def onchain_band(item):
    if not IS_OTHER(item):
        return EDPB_BAND.get(item, 'B')
    return 'A' if OTHER_ON_CHAIN_A.search(str(item)) else 'B'


def onchain_reading(sh):
    """'A' if the ledger holds anything that remains personal data where it relates to a person, else 'B' or 'C'"""
    bands = {onchain_band(x) for x in L(sh, 'P3', 'on_chain')}
    return 'A' if 'A' in bands else ('B' if 'B' in bands else ('C' if bands else ''))


# The ledger checks the updates (C3): its nodes or contracts check the content of individual updates, or verify a proof about
# each update or its training. Two designs carry the role 'update-verification' for checks that do not examine an update's
# content, and do not count.
LEDGER_CHECK_NOT_CONTENT = {
    'N017',   # P4: "Nothing else about a client's update (its quality or correctness) is checked"
    'N019',   # P4: "These checks do not examine the update's content"
}


LEDGER_UPDATE_RELATIONS = ('bound', 'training')   # stated relations about each update or its training (II-A: by the relation stated)


def ledger_checks_updates(k, sh):
    """C3: the ledger itself checks the updates. Its nodes or contracts check the content of individual updates or their training
    (role 'update-verification' with a content check), or verify on the ledger a proof about each update or its training."""
    roles = set(L(sh, 'P3', 'roles'))
    if 'update-verification' in roles and k not in LEDGER_CHECK_NOT_CONTENT and check_class(k, sh) == 'content':
        return True
    return 'proof-verification' in roles and ZK_RELATION.get(k) in LEDGER_UPDATE_RELATIONS and V(sh, 'P4', 'zk_on_chain') == 'yes'


def ledger_checks_aggregation(k, sh):
    """the ledger verifies a proof that the aggregation is correct, and does not check the updates (Partial for C3)"""
    return (not ledger_checks_updates(k, sh) and 'proof-verification' in L(sh, 'P3', 'roles') and ZK_RELATION.get(k) == 'aggregation'
            and V(sh, 'P4', 'zk_on_chain') == 'yes')


def ledger_checks_other(k, sh):
    """the ledger's nodes or contracts verify or check something other than the updates or the aggregation (other proofs,
    signatures, freshness, format): Partial for C3"""
    roles = set(L(sh, 'P3', 'roles'))
    return (not ledger_checks_updates(k, sh) and not ledger_checks_aggregation(k, sh)
            and bool(roles & {'proof-verification', 'update-verification'}))


def prim_cover(k, sh):
    """the grades of a primary study for its row of the spine table (the counterpart of the surveys' table): Yes / Partial / No
    per column, as PRIM_COVER_NOTE states; Yes in a condition column is exactly that condition of gap_conditions()"""
    cl, te = threats_of(k, sh, 'claimed'), threats_of(k, sh, 'tested')
    c = gap_conditions(k, sh)

    def threat(col, also=False):
        tags = GAP_THREATS[col]
        if c[col]:
            return 'Yes\u2020' if not ((te & tags) - ATTACK_NOT_DESCRIBED.get(k, set())) else 'Yes'
        return 'Partial' if cl & tags or also else 'No'
    zk = V(sh, 'P4', 'zk_used') is True
    law = any(DP_LAW.search(str(x)) for x in L(sh, 'P7', 'laws'))
    checked = [x for x in L(sh, 'P4', 'checked') if x != 'none']
    return {'SQ1 Fabric (C1)': 'Yes' if c['C1'] else ('Partial' if network_own(sh) else 'No'),
            'SQ2 Privacy (C2)': 'Yes' if c['C2'] else ('Partial' if protects_updates(sh) else 'No'),
            'SQ3 Verification': 'Yes' if verification_yes(k, sh) else ('Partial' if checked else 'No'),
            'SQ3 ZKPs': 'Yes' if zk and ZK_RELATION.get(k) in ('bound', 'training') else ('Partial' if zk else 'No'),
            'SQ3 Blockchain (C3)': 'Yes' if c['C3'] else ('Partial' if ledger_checks_aggregation(k, sh) or ledger_checks_other(k, sh) else 'No'),
            'SQ4 Poisoning (C4a)': threat('C4a'),
            'SQ4 Malicious or fake (C4b)': threat('C4b', 'identity-membership' in L(sh, 'P4', 'checked')),
            'SQ4 Free riding (C4c)': threat('C4c'),
            'SQ5 Regulation (C5)': 'Yes' if c['C5'] else ('Partial' if law or V(sh, 'P7', 'erasure') == 'mentioned' else 'No')}


def qa_primary(k, sh):
    cons = _consistency()
    ds = [str(x) for x in L(sh, 'P6', 'datasets')]
    q1 = 0 if not ds else 0.5 if all(re.search(r'unnamed|not named|not stated', x, re.I) for x in ds) else 1
    q2 = 1 if L(sh, 'P6', 'baselines') else 0
    cl = TESTABLE & threats_of(k, sh, 'claimed')                 # a Byzantine claim about the consensus is not an attack on the learning
    te = cl & threats_of(k, sh, 'tested')
    q3 = 1 if cl and te == cl else 0.5 if te else 0
    own_net = V(sh, 'P1', 'network_measured') == 'yes' and V(sh, 'P1', 'network_measured_own') is not False   # not only a baseline's
    q4 = 1 if V(sh, 'P1', 'device_measured') == 'yes' or own_net else 0.5 if V(sh, 'P1', 'network_measured') == 'yes' else 0
    q5 = 1 if V(sh, 'P6', 'code') == 'yes' else 0
    q6 = 0 if k in cons['no'] else 0.5 if k in cons['partial'] else 1
    return [q1, q2, q3, q4, q5, q6]


def qa_secondary(sh):
    per = str(V(sh, 'S1', 'period', '') or '')
    partial = re.compile(r'\bonly\b|approx|≈|\bFig\.|figure', re.I)        # for part of the review only, approximate, or read off a figure
    q1 = (0.5 if partial.search(per) else 1) if L(sh, 'S1', 'databases') else 0   # databases named for part of the review only (S007) → partial
    q2 = 0 if (not per or per.lower().startswith('not stated')) else 0.5 if partial.search(per) or 'not stated' in per.lower() else 1
    n = V(sh, 'S1', 'studies', 'not stated')
    q3 = 1 if isinstance(n, int) or str(n).isdigit() else 0 if not re.search(r'\d', str(n)) else \
        0.5 if partial.search(str(n)) else 1 if re.match(r'\d[\d,]*\b', str(n)) else 0.5
    lim = V(sh, 'S8', 'own_limitations')                   # yes / partial (scope only) / no, judged on the full text
    q4 = {'yes': 1, 'partial': 0.5, 'no': 0}[lim] if lim in ('yes', 'partial', 'no') else \
        (0 if str(sh['answers'].get('S8', {}).get('answer', '')).lower().startswith(('not stated', 'no limitation')) else 1)
    return [q1, q2, q3, q4]


def qa_stats(S, fin):
    prim, sec = split(S, fin)
    s = {}
    P = {k: qa_primary(k, sh) for k, sh in prim.items()}
    Q = {k: qa_secondary(sh) for k, sh in sec.items()}
    tot = {k: sum(v) for k, v in P.items()}
    s['qa_primary_mean'] = round(sum(tot.values()) / max(1, len(tot)), 1)
    s['qa_secondary_mean'] = round(sum(sum(v) for v in Q.values()) / max(1, len(Q)), 1)
    s['qa_low_n'] = sum(1 for v in tot.values() if v < QA_LOW)
    s['qa_low_threshold'] = QA_LOW
    for i, (code, _) in enumerate(QA_PRIMARY):
        s[f'qa_{code.lower()}_yes'] = sum(1 for v in P.values() if v[i] == 1)
    for i, (code, _) in enumerate(QA_SECONDARY):
        s[f'qa_{code.lower()}_yes'] = sum(1 for v in Q.values() if v[i] == 1)
        s[f'qa_{code.lower()}_partial'] = sum(1 for v in Q.values() if v[i] == 0.5)
    s['qa_cons_no'] = sum(1 for v in P.values() if v[5] == 0)
    s['qa_cons_partial'] = sum(1 for v in P.values() if v[5] == 0.5)
    keep = {k: sh for k, sh in prim.items() if P[k][2] > 0}           # the re-check: studies that run at least one attack they claim (QA3)
    s['sens_n'] = len(keep)
    for t in ('poisoning', 'sybil-fake', 'free-riding', 'byzantine-malicious'):
        cl = [k for k, sh in keep.items() if t in threats_of(k, sh, 'claimed')]
        s[f'sens_claimed_{slug(t)}'] = len(cl)
        s[f'sens_tested_{slug(t)}'] = sum(1 for k in cl if t in threats_of(k, keep[k], 'tested'))
    mfk = [k for k, sh in keep.items() if threats_of(k, sh, 'claimed') & {'byzantine-malicious', 'sybil-fake'}]
    s['sens_claimed_mal_fake'] = len(mfk)
    s['sens_tested_mal_fake'] = sum(1 for k in mfk if threats_of(k, keep[k], 'tested') & {'byzantine-malicious', 'sybil-fake'})
    s['sens_sees_no'] = sum(1 for sh in keep.values() if V(sh, 'P4', 'checker_sees_update') == 'no')
    s['sens_sees_yes_partly'] = sum(1 for sh in keep.values() if V(sh, 'P4', 'checker_sees_update') in ('yes', 'partly'))
    s['sens_device'] = sum(1 for sh in keep.values() if V(sh, 'P1', 'device_measured') == 'yes')
    s['sens_checks'] = sum(1 for sh in keep.values() if V(sh, 'P4', 'checker_sees_update') != 'no-check')
    s['sens_no_attack'] = sum(1 for sh in keep.values() if not attacks_learning(sh))
    s['sens_sees_no_other'] = sum(1 for k, sh in prim.items() if k not in keep and V(sh, 'P4', 'checker_sees_update') == 'no')
    s['sens_sees_no_keys'] = ', '.join(sorted(k for k, sh in keep.items() if V(sh, 'P4', 'checker_sees_update') == 'no'))
    s['sees_yes_partly'] = sum(1 for sh in prim.values() if V(sh, 'P4', 'checker_sees_update') in ('yes', 'partly'))
    s['sees_with_check'] = sum(1 for sh in prim.values() if V(sh, 'P4', 'checker_sees_update') != 'no-check')
    s['sens_cc_content_no'] = sum(1 for k, sh in keep.items() if check_class(k, sh) == 'content' and V(sh, 'P4', 'checker_sees_update') == 'no')
    s['sens_attack_learning'] = sum(1 for sh in keep.values() if attacks_learning(sh))
    s['sens_privacy_only'] = s['sens_n'] - s['sens_attack_learning']
    return s


def qa_tables(S, fin, s, md_table):
    prim, sec = split(S, fin)
    md_table('qa_checklist', 'Quality appraisal questionnaire: each question and how it is answered (Yes, Partial or No).',
             ['Item', 'Question', 'Description'],
             [[c, q, QA_DESCRIPTION[c]] for c, q in QA_PRIMARY + QA_SECONDARY], widths=[8, 34, 58])
    # the answers question by question, without a total (the author, 12 October 2026: no numbered scores); rows in the
    # order of the reference list (build.py sorts them once the citations are numbered)
    f = lambda x: {1: 'Yes', 0.5: 'Partial', 0: 'No'}[x]
    rows = [[f'[@{k}]'] + [f(x) for x in qa_primary(k, sh)] for k, sh in sorted(prim.items())]
    md_table('qa_primary', 'Quality-appraisal answers of each design',
             ['Study', 'QA1 Named data sets', 'QA2 Named baselines', 'QA3 Tests of claimed attacks reported', 'QA4 Cost on devices or links reported',
              'QA5 Link to code', 'QA6 Claims and results consistent'], rows, widths=[13, 14, 14, 15, 15, 13, 16])
    rows = [[f'[@{k}]'] + [f(x) for x in qa_secondary(sh)] for k, sh in sorted(sec.items())]
    md_table('qa_secondary', 'Quality appraisal of the surveys: the answer to each question of {{TAB:qa_checklist}}.',
             ['Survey', 'QS1 Databases named', 'QS2 Period stated', 'QS3 Number of studies stated', 'QS4 Own limitations stated'],
             rows, widths=[16, 21, 21, 21, 21])
    rows = [[f'[@{k}]'] + [prim_cover(k, sh)[c] for c in PRIM_COVER] for k, sh in sorted(prim.items())]
    yes = ['Yes'] + [str(sum(1 for r in rows if r[1 + i].startswith('Yes'))) for i in range(len(PRIM_COVER))]
    # no count column: a count that leaves out some columns of its own table misleads (the author, 13 October 2026); the
    # conditions of the research gap are counted in their own tables (gap_conditions, gap)
    md_table('prim_cover', 'What each primary study does along the spine, layer by layer and focus angle by focus angle, in the form of the surveys\' table.',
             ['Study'] + [PRIM_HEAD[c] for c in PRIM_COVER], rows + [yes], widths=[8, 10, 10, 12, 8, 11, 10, 11, 9, 11], note=PRIM_COVER_NOTE)
    # the research gap (Section VIII), restored at the author's request of 13 October 2026 in the form of V55's Tables XV and
    # XVI, with the seven conditions of the strict spine: each condition with the designs that meet it, then the designs that
    # meet at least two, condition by condition (every column of that table is a condition, so Met counts them all)
    G = gap_matrix(prim)
    md_table('gap_conditions', 'Conditions of the research gap, the survey question each comes from, and the number of included primary studies that meet each.',
             ['Condition', 'Meaning', 'From', 'Primary studies meeting it'],
             [[c, GAP_MEANING[c], f'SQ{c[1]}', str(sum(G[k][0][c] for k in G))] for c in GAP_COLUMNS], widths=[11, 61, 10, 18])
    mark = lambda k, c: {'Yes': '✓', 'Yes\u2020': '✓\u2020'}.get(prim_cover(k, prim[k])[COLUMN_OF[c]], '')
    rows = [[f'[@{k}]'] + [mark(k, c) for c in GAP_COLUMNS] + [str(G[k][1])] for k in sorted(prim) if G[k][1] >= 2]
    md_table('gap', 'Primary studies that meet at least two of the seven conditions of the research gap (✓ met; † the attack tested is not described), with the number they meet.',
             ['Study'] + [f'{c} {GAP_SHORT[c]}' for c in GAP_COLUMNS] + ['Met'], rows or [['none'] + [''] * 8],
             widths=[10, 11, 12, 12, 11, 12, 11, 13, 8],
             note='Met: the number of the seven conditions met, the attack layer counting once for each of its three threats. Rows by conditions met, then in reference order.')
    # open areas, one per layer (V34 Table 18, V55 Table XIV), restored at the author's request of 13 October 2026 with the two
    # tiers apart, each in the words already in the paper: what the surveys ask for (Section V-D, with its citations), what the
    # primary studies show and the open issue (Section VII-B)
    md_table('open_areas', 'Open areas, one per layer: what the surveys ask for (Section V-D), what the primary studies show, and the open issue for future research (Section VII-B).',
             ['Layer', 'What the surveys ask for', 'What the primary studies show', 'Open issue for future research'], [
        ['SQ1 NG-IoT fabric', 'Lightweight ledgers and consensus for constrained devices, and validation in real IoT and vehicular test beds rather than simulation [@S005; @S007; @S019; @n3837; @O078]',
         '{{N:device_measured}} of {{N:primary}} report a cost measured on device-class hardware, and none of those that name their hardware is a microcontroller-class sensor',
         'Measure what privacy, checking and consensus cost in time, energy, memory and traffic on the class of device and over the NG-IoT links where they would run'],
        ['SQ2 Privacy plane', 'How to bring down the overhead of privacy-preserving operation, and how much privacy noise costs in accuracy [@O078; @S010; @p1162]',
         '{{N:hk_hidden}} of {{N:primary}} keep the updates from the server or aggregator, and in {{N:gap_c2}} no party that checks or aggregates sees them',
         'Hide each update from every party, the checking party included, and state the protection and its assumptions, such as the privacy budget and the collusion threshold, in comparable terms'],
        ['SQ3 Trust plane', 'Effective verification of local updates, defences that still work when updates are encrypted or securely aggregated, and ZKP-based validation of updates [@S007; @p0086; @S018]',
         'The ledger itself checks the updates in {{N:gap_c3}}, and {{N:cc_content_no}} designs check the content of updates that no checking party sees',
         'The ledger itself checks the updates, by the consensus of nodes that compute the check jointly or by proofs that any node can verify'],
        ['SQ4 Attacks and defences', 'Defences against model poisoning, robustness against collusion and adaptive attackers, and formal robustness guarantees [@S017; @S019; @n3837; @p0086]',
         '{{N:no_attack_tested}} of {{N:primary}} report no test of an attack on the learning; a test is reported for poisoning by {{N:gap_c4a}}, for malicious or fake participants by {{N:gap_c4b}} and for free riding by {{N:gap_c4c}}',
         'Test designs by described attacks of poisoning, of malicious or fake participants and of free riding, including attackers who know the check, at stated attacker shares, against named baselines and with a link to the code'],
        ['SQ5 Regulatory layer', 'How an immutable ledger can meet the right to erasure [@n3837; @p0435]; complete deletion on request is technically not possible in most decentralised systems [@p0156]',
         '{{N:onchain_a}} of {{N:primary}} ledgers hold records that remain personal data where they relate to a person, and {{N:erasure_addressed}} ledgers can delete data, to limit their growth',
         'A ledger without personal records, with erasure and rectification designed in']],
        widths=[13, 30, 29, 28])
    # the summary of findings (V55's open-issues table, with the evidence behind each answer and its confidence; Section VII)
    md_table('findings', 'Summary of findings: the answer to each survey question, the main limitation of the evidence behind it, the confidence the review places in it, and the open issue it leaves.',
             ['Layer', 'What the primary studies show', 'Main limitation of the evidence', 'Confidence', 'Open issue'], [
        ['SQ1 NG-IoT fabric', '{{N:device_measured}} of {{N:primary}} report a cost measured on device-class hardware (C1), none of those that name their hardware on a microcontroller-class sensor; {{N:network_measured_own}} report a cost of the design measured over a network link', 'hardware, models and units differ; costs are seldom broken down by mechanism', 'High: a count of what the studies report', 'Costs on constrained devices and links'],
        ['SQ2 Privacy plane', 'no party that checks or aggregates sees an individual update in {{N:gap_c2}} designs (C2); {{N:hk_hidden}} keep the updates from the aggregator by encryption, sharing, masking or an enclave and {{N:hk_noised}} only add noise', 'privacy budgets and collusion thresholds are seldom stated', 'Moderate: rests on how the designs are described', 'Updates hidden from every party'],
        ['SQ3 Trust plane', 'the ledger itself checks the updates in {{N:gap_c3}} designs (C3) and the aggregation in {{N:ledger_checks_aggregation}}; {{N:zk_stated_update}} designs state the relation they prove, a bound on the update or its correct training', 'whether the checker sees the update is unclear in {{N:cc_content_unclear}} of the {{N:cc_content}} designs that check the content of updates; proofs are often described by their purpose rather than their statement', 'Moderate: the unclear cases could change the count', 'Checks that the ledger itself makes or verifies'],
        ['SQ4 Attacks and defences', 'a test by an attack is reported for poisoning by {{N:gap_c4a}} (C4a), for malicious or fake participants by {{N:gap_c4b}} (C4b) and for free riding by {{N:gap_c4c}} (C4c); {{N:no_attack_tested}} report no test of an attack on the learning', 'several reported tests use only label flipping or do not describe the attack; attacker shares and non-IID settings are often unstated', 'High: a count of what the studies report', 'Reported tests against the three threats'],
        ['SQ5 Regulatory layer', 'by the EDPB criteria, {{N:onchain_b}} ledgers hold no personal records and {{N:gap_c5_erase}} more can erase or redact what their ledgers hold (C5: {{N:gap_c5}}); {{N:laws_named}} name a data-protection law', 'the reading applies the EDPB criteria to the designs\' descriptions; whether participants are persons depends on the setting', 'Moderate: a reading by the review, not the studies\' own statement', 'Ledgers without personal data, with erasure designed in']],
        widths=[12, 30, 22, 14, 22],
        note='Confidence, as in Section II-E: high where the finding is a count of what the studies report; moderate where it rests on '
             'classifying the designs\' descriptions, some of them unclear; low where few studies bear on it.')


def check_abbreviations(body):
    return [a for a, _ in ABBREVIATIONS if not re.search(r'(?<![A-Za-z])' + re.escape(a.split(' / ')[0]) + r'(?![A-Za-z])', body)]


def tables(S, fin, s, md_table):
    prim, sec = split(S, fin)
    # ---- year by year: how many studies, and what the primary studies of each year do, out of that year's primary studies
    # (surveys and primary studies are never added under one criterion; the independent review of V55)
    yr = {r['corpus_id']: int(r['year']) for r in fin}
    rows, tot = [], [0] * 7
    for y in range(2020, 2027):
        P = [k for k in prim if yr.get(k) == y]
        vals = [len(P), sum(1 for k in sec if yr.get(k) == y),
                sum(1 for k in P if attacks_learning(prim[k])),
                sum(1 for k in P if V(prim[k], 'P4', 'zk_used') is True),
                sum(1 for k in P if ZK_RELATION.get(k) in ('bound', 'training')),
                sum(1 for k in P if V(prim[k], 'P1', 'device_measured') == 'yes'),
                sum(1 for k in P if V(prim[k], 'P6', 'code') == 'yes')]
        tot = [a_ + b_ for a_, b_ in zip(tot, vals)]
        rows.append([f"{y}{'*' if y == 2026 else ''}"] + [str(v) for v in vals])
    rows.append(['Total'] + [str(v) for v in tot])
    s['yt_attack'], s['yt_attack_2026'] = tot[2], int(rows[-2][3])          # primary studies running an attack: all, 2026
    s['yt_zk_2025_on'] = int(rows[-3][4]) + int(rows[-2][4])
    s['yt_prim_2025_on'] = int(rows[-3][1]) + int(rows[-2][1])
    s['yt_code'] = tot[6]
    md_table('years', 'Included studies per year, and what the primary studies of each year do (counts out of that year\'s primary studies).',
             ['Year', 'Primary studies', 'Surveys', 'Report an attack test on the learning', 'Use ZKPs', 'State a bound or training',
              'Report cost on devices', 'Link to code'], rows, widths=[8, 12, 10, 16, 11, 15, 15, 13],
             note='* 2026 to the date of the search: an incomplete year. The last five columns count primary studies only.')
    pairs = [ABBREVIATIONS[i:i + 2] for i in range(0, len(ABBREVIATIONS), 2)]
    md_table('abbrev', 'Abbreviations.', ['Term', 'Meaning', 'Term ', 'Meaning '],
             [[a[0], a[1], (rest[0][0] if rest else ''), (rest[0][1] if rest else '')] for a, *rest in pairs], widths=[14, 36, 14, 36])
    md_table('sq', 'The survey questions, one for each layer, and the sections that introduce and answer them.', ['Layer', 'Survey question', 'Sections'], [
        ['SQ1 NG-IoT fabric', 'In which NG-IoT settings are the approaches built and evaluated, where on the device–edge–cloud tiers do learning, privacy, checking and the ledger run, and is their cost measured on device-class hardware or real links?', 'III-A, VI-B'],
        ['SQ2 Privacy plane', 'Which mechanisms protect the data and the model updates, what does each hide and from whom, and at what reported cost?', 'III-B, VI-C'],
        ['SQ3 Trust plane', 'What do the ledgers record, verify and enforce, how are updates, training or aggregation checked, including by zero-knowledge proofs, and does the checker see the update?', 'III-C, VI-D'],
        ['SQ4 Attacks and defences', 'Which of poisoning, malicious or fake participants and free riding do the approaches claim to counter, which do they test, and with which defences and evaluation?', 'III-D, VI-E'],
        ['SQ5 Regulatory layer', 'Do the studies address data-protection law, what personal data reaches the ledger, and how is erasure handled?', 'III-E, VI-F']],
        widths=[18, 66, 16])
    md_table('keywords', 'Keyword blocks of the searches (Scopus form; the IEEE Xplore and ScienceDirect versions use subsets of these terms, split to meet each site’s limits; Appendix A).',
             ['Block', 'Terms', 'Searches'], [
        ['Privacy', '"privacy-preserving machine learning", PPML, "privacy-preserving", "privacy preserving", "privacy preservation", "data privacy", "privacy protection", privacy, "differential privacy", "homomorphic encryption", "multi-party computation", "secure aggregation"', 'all'],
        ['Learning', '"machine learning", "deep learning", "federated learning", "distributed learning", "distributed machine learning", "collaborative learning", "decentrali?ed learning", "split learning", "edge intelligence"', 'all'],
        ['NG-IoT', '"next generation IoT", "next-generation IoT", NG-IoT, "next generation Internet of Things", "Internet of Things", IoT, IIoT, IoMT, IoV, "internet of vehicles", "internet of medical things", "industrial internet", "edge computing", "mobile edge computing", "fog computing", 5G, 6G, "beyond 5G", B5G, vehicular, "smart grid*", "smart cit*", "communication network*"', 'all'],
        ['Survey (title)', 'survey, review, "systematic literature review", "systematic review", "systematic mapping", "state of the art", overview, tutorial, SoK, taxonomy, "future directions", "research directions", "open problems", "open issues", "open challenges", "challenges and opportunities", "opportunities and challenges", "challenges and solutions", countermeasures, advances, fundamentals, perspectives, trends, roadmap, "lessons learned", "comprehensive study"; or document type Review', 'P-S1, P-A, P-C'],
        ['Threat or verification', 'poisoning, byzantine, backdoor, sybil, malicious, "free-rid*", "free rider*", "fake node*", "fake client*", "model integrity", verifiable', 'P-S2, P-B']],
        widths=[13, 72, 15])

    # ---- surveys by coverage (S2, S4): privacy and attacks are a subject in every survey and the trust plane follows blockchain or verification, so neither is a column
    COVER = SURVEY_COVER
    rows = [[f'[@{k}]'] + [MARK.get(V(sh, i, f), '?') for i, f, _ in COVER] for k, sh in sorted(sec.items(), key=lambda kv: kv[0])]
    rows.append(['This review'] + ['Yes'] * len(COVER))
    md_table('surveys', 'What each survey treats, layer by layer and focus angle by focus angle (Yes: a subject of its own, with a section, subsection or table; Partial: mentioned without one; No: absent).',
             ['Survey'] + [a for _, _, a in COVER], rows, widths=[13, 9, 9, 11, 9, 11, 10, 11, 9, 10],
             note=f'Columns by layer, as in Table I, each named by the subject it grades: SQ1 NG-IoT fabric (devices, links and enabling tiers), '
                  f'SQ2 privacy plane (privacy mechanisms), SQ5 regulatory layer (data-protection law); '
                  f'SQ3, the trust plane, is shown by its three means of checking (verification of the learning by any means, ZKPs, the blockchain) '
                  f'and SQ4, attacks and defences, by the three threats '
                  f'this review follows. As layers, the trust plane is a subject of its own in {s["layer_trust_subject"]} surveys and '
                  f'attacks and defences in {s["layer_attacks_subject"]}. "This review": each layer has a subsection of its own in Sections '
                  f'III and VI, and each focus angle a table or figure (Sections VI-D and VI-E).')

    # ---- what is checked (the strongest check of each design) against whether the checking party sees the update
    rows = []
    for c, name in CHECK_CLASSES:
        ids = [k for k, sh in prim.items() if check_class(k, sh) == c]
        if not ids:
            continue
        cells = []
        for v, _ in SEES_ORDER + [('no-check', 'no checker of updates')]:
            sub = [k for k in ids if V(prim[k], 'P4', 'checker_sees_update') == v]
            cells.append(f'{len(sub)} {cites(sub)}' if sub else '–')
        checkers = collections.Counter(c2 for k in ids for c2 in dict.fromkeys(map(O, L(prim[k], 'P4', 'checker'))) if c2 not in ('none', 'other'))
        rows.append([name, str(len(ids))] + cells + ['; '.join(f'{CHECKER_NAME.get(c2, c2)} ({n})' for c2, n in checkers.most_common()) or '–'])
    md_table('checks', 'What the designs check, and whether the checker sees the update',
             ['What is checked', 'Studies', 'Sees it in full', 'In part or noised', 'Not at all', 'Unclear', 'No checker of updates', 'Checked by'], rows,
             widths=[16, 7, 15, 15, 12, 12, 9, 14],
             note='Each design is counted once, under the strongest thing it checks: the content of individual updates (accuracy, '
                  'similarity, a norm bound, anomalies, correct training, or an unstated rule) before the aggregation, and the aggregation '
                  'before identities, signatures, format or contributions. "In part or noised": the checker sees a function of the update '
                  '(such as its norm), part of it, or a version with noise added. A design can have several checkers.')
    for c, _ in CHECK_CLASSES:
        s[f'cc_{c}'] = sum(1 for k, sh in prim.items() if check_class(k, sh) == c)
        for v, _ in SEES_ORDER:
            s[f'cc_{c}_{v}'] = sum(1 for k, sh in prim.items() if check_class(k, sh) == c and V(sh, 'P4', 'checker_sees_update') == v)
    s['cc_content_no_tested'] = sum(1 for k, sh in prim.items() if check_class(k, sh) == 'content' and V(sh, 'P4', 'checker_sees_update') == 'no'
                                    and attacks_learning(sh))

    # ---- what the zero-knowledge proofs prove, where they are verified, and what they cost (the relation as recorded)
    zk = {k: sh for k, sh in prim.items() if V(sh, 'P4', 'zk_used') is True}
    rows = []
    for r, name in ZK_RELATIONS:
        ids = [k for k in zk if ZK_RELATION.get(k) == r]
        if not ids:
            continue
        on = [k for k in ids if V(zk[k], 'P4', 'zk_on_chain') == 'yes']
        hid = [k for k in ids if V(zk[k], 'P4', 'checker_sees_update') == 'no']
        cost = '; '.join(f'{ZK_COST[k]} [@{k}]' for k in sorted(ids) if ZK_COST.get(k)) or 'not reported'
        rows.append([name, f'{len(ids)} {cites(ids)}', f'{len(on)}' + (f' {cites(on)}' if on and len(on) < len(ids) else ''),
                     f'{len(hid)} {cites(hid)}' if hid else '–', cost])
    md_table('zk', f'What the zero-knowledge proofs of the {len(zk)} primary studies that use them prove, by the relation each study states.',
             ['The proof establishes', 'Studies', 'Verified on the ledger', 'No checking party sees the update', 'Costs reported'], rows,
             widths=[22, 15, 12, 15, 36],
             note='Classified by the statement the proof encodes as the study describes it, not by what the study says the proof shows: '
                  'two studies that present their proofs as proving training or the update\'s correctness prove a commitment\'s '
                  'evaluation at a random challenge and a classification of one example. Costs are given in the studies\' own figures '
                  'and hardware, which differ.')
    for r, _ in ZK_RELATIONS:
        s[f'zkrel_{r}'] = sum(1 for k in zk if ZK_RELATION.get(k) == r)
    s['zk_on_ledger'] = sum(1 for sh in zk.values() if V(sh, 'P4', 'zk_on_chain') == 'yes')
    s['zk_claimed_update'] = sum(1 for k in zk if ZK_RELATION.get(k) in ('bound', 'training', 'unspecified-update', 'commitment')
                                 or (k == 'n0414'))   # presented as proving the update or its training
    s['zk_stated_update'] = sum(1 for k in zk if ZK_RELATION.get(k) in ('bound', 'training'))
    s['zk_not_claimed_update'] = len(zk) - s['zk_claimed_update']
    s['zk_inference_not_update'] = sum(1 for k in zk if ZK_RELATION.get(k) == 'inference' and k != 'n0414')
    s['zk_bound_hidden'] = sum(1 for k in zk if ZK_RELATION.get(k) == 'bound' and V(zk[k], 'P4', 'checker_sees_update') == 'no')
    s['zk_bound_tested'] = sum(1 for k in zk if ZK_RELATION.get(k) == 'bound' and attacks_learning(zk[k]))
    s['zk_device_proving'] = sum(1 for k in zk if V(zk[k], 'P1', 'device_measured') == 'yes')
    assert set(zk) == set(ZK_RELATION), sorted(set(zk) ^ set(ZK_RELATION))

    # ---- the NG-IoT fabric (P1, SQ1): settings, next-generation enablers, where costs are measured (5G made visible, V41)
    def p1(field, names):
        out = []
        for v, n in collections.Counter(x for sh in prim.values() for x in dict.fromkeys(L(sh, 'P1', field))).most_common():
            ids = [k for k, sh in prim.items() if v in L(sh, 'P1', field)]
            out.append([names.get(v, v), f'{n} {cites(ids)}'])
        return out
    meas = lambda f: [k for k, sh in prim.items() if V(sh, 'P1', f) == 'yes']
    g5 = [k for k in meas('network_measured') if '5G-6G' in L(prim[k], 'P1', 'enablers')]
    sim = [k for k, sh in prim.items() if 'simulated' in L(sh, 'P3', 'platform')]
    rows = ([['Setting: ' + a, b] for a, b in p1('settings', SETTING_NAME)] + [['Enabler: ' + a, b] for a, b in p1('enablers', ENABLER_NAME)]
            + [['Cost measured on device-class hardware', f'{len(meas("device_measured"))} {cites(meas("device_measured"))}'],
               ['Cost measured over a network link', f'{len(meas("network_measured"))} {cites(meas("network_measured"))}'],
               ['Design measured on devices connected over 5G', f'{len(g5)} {cites(g5)}'],
               ['Ledger simulated rather than run', f'{len(sim)} {cites(sim)}']])
    md_table('fabric', 'The NG-IoT fabric of the primary studies: settings, next-generation enablers (5G or 6G, edge, MEC, cloud) and where costs are '
             'measured (a study may name several settings and enablers).', ['Feature', 'Studies'], rows, widths=[34, 66])

    # ---- privacy mechanisms (P2), by the kind of protection they give, and what each keeps from the party that aggregates
    KEEPS = {'Confidentiality of the update': 'the update itself, in {h} of these designs',
             'Output privacy': 'nothing: the update is shared with noise added; noise is the only protection from the aggregator in {n} designs',
             'Unlinkability': 'the participant\'s identity, not the update',
             'Proofs that hide their witness': 'the witness of the statement proved; the update only where it is committed or encrypted',
             'Transport only': 'nothing from the aggregator; the update from outsiders on the link'}
    rows = []
    for kind, mechs in PROTECTION_KINDS:
        for m in mechs:
            ids = [k for k, sh in prim.items() if m in mechanisms_used(sh)]
            if not ids:
                continue
            h = sum(1 for k in ids if hidden_kind(prim[k]) == 'hidden')
            n = sum(1 for k in ids if hidden_kind(prim[k]) == 'noised')
            rows.append([kind, MECH_NAME[m], f'{len(ids)} {cites(ids)}', KEEPS[kind].format(h=h, n=n)])
    md_table('privacy', 'Privacy mechanisms of the designs, and what each keeps from the aggregator',
             ['Kind of protection', 'Mechanism', 'Studies', 'What it keeps from the server or aggregator'], rows, widths=[17, 17, 38, 28],
             note='A study may use several mechanisms. A design keeps its updates from the aggregator when they reach it encrypted, '
                  'secret-shared, masked or inside an enclave whose host cannot read them.')
    s['hk_hidden'] = sum(1 for sh in prim.values() if hidden_kind(sh) == 'hidden')
    s['hk_noised'] = sum(1 for sh in prim.values() if hidden_kind(sh) == 'noised')
    s['hk_seen'] = len(prim) - s['hk_hidden'] - s['hk_noised']
    s['zk_hide_update_from_agg'] = sum(1 for sh in prim.values() if 'ZKP' in mechanisms_used(sh) and hidden_kind(sh) == 'hidden')
    s['zk_as_mechanism'] = sum(1 for sh in prim.values() if 'ZKP' in mechanisms_used(sh))

    # ---- ledgers (P3): type, what the ledger does, and what it holds read against the EDPB guidelines (Section III-E)
    def by(field, names=None, rename=None):
        out = []
        for v, n in collections.Counter(x for sh in prim.values() for x in dict.fromkeys(map(O, L(sh, 'P3', field)))).most_common():
            ids = [k for k, sh in prim.items() if v in map(O, L(sh, 'P3', field))]
            out.append([(names or LEDGER_WORDS).get(v, v), f'{n} {cites(ids)}'])
        return out
    c3 = [k for k, sh in prim.items() if ledger_checks_updates(k, sh)]
    c3g = [k for k, sh in prim.items() if ledger_checks_aggregation(k, sh)]
    other_proofs = [k for k, sh in prim.items() if 'proof-verification' in L(sh, 'P3', 'roles') and k not in c3 + c3g]
    other_checks = [k for k, sh in prim.items() if ledger_checks_other(k, sh) and k not in other_proofs]
    rows = [['Type', a, b] for a, b in by('ledger')]
    rows += [['What the ledger does', 'checks the updates itself: its nodes or contracts check their content, or verify a proof about each update or its training (C3)', f'{len(c3)} {cites(c3)}'],
             ['What the ledger does', 'verifies a proof that the aggregation is correct, not the updates', f'{len(c3g)} {cites(c3g)}'],
             ['What the ledger does', 'verifies proofs of other statements only (identity, an inference, other records, or a statement whose relation is not stated)', f'{len(other_proofs)} {cites(other_proofs)}'],
             ['What the ledger does', 'checks signatures, deadlines, freshness or format of the updates only', f'{len(other_checks)} {cites(other_checks)}']]
    rows += [['What the ledger does', a, b] for a, b in by('roles') if a not in ('verifies updates', 'verifies proofs')]
    BAND_NAME = {'A': 'remains personal data where it relates to a person', 'B': 'depends on the scheme', 'C': 'reveals nothing about its witness'}
    held = collections.defaultdict(list)
    for k, sh in prim.items():
        for x in set(L(sh, 'P3', 'on_chain')):
            held[(onchain_band(x), LEDGER_WORDS.get(x, 'other personal records' if onchain_band(x) == 'A' else 'other records') if IS_OTHER(x) else LEDGER_WORDS.get(x, x))].append(k)
    for (band, item), ids in sorted(held.items(), key=lambda kv: (kv[0][0], -len(set(kv[1])))):
        ids = sorted(set(ids))
        rows.append([f'What it holds ({BAND_NAME[band]})', item, f'{len(ids)} {cites(ids)}'])
    a_led = [k for k, sh in prim.items() if onchain_reading(sh) == 'A']
    b_led = [k for k, sh in prim.items() if onchain_reading(sh) in ('B', 'C')]
    rows.append(['What it holds', 'at least one record that remains personal data where it relates to a person', f'{len(a_led)}'])
    rows.append(['What it holds', 'only records whose status depends on the scheme, or proofs', f'{len(b_led)} {cites(b_led)}'])
    md_table('ledger', 'Ledgers of the designs: type, roles and what they hold',
             ['Aspect', 'Feature', 'Studies'], rows, widths=[22, 38, 40],
             note='What the ledger holds is read by the criteria of Section III-E: data in the clear or encrypted, identifiers, keys, and '
                  'scores or payments about a participant remain personal data wherever they relate to a person; a salted or keyed hash '
                  'remains personal data and a perfectly hiding commitment does not once the data and its opening are deleted, so hashes and '
                  'commitments, like models, aggregates and logs, depend on the scheme; a proof reveals nothing about its witness. A study '
                  'may appear in several rows, and one design runs two ledgers, so its types add up to one more than the designs.')
    s['ledger_checks_updates'] = len(c3)
    s['ledger_checks_aggregation'] = len(c3g)
    s['c3_sees_yes_partly'] = sum(1 for k in c3 if V(prim[k], 'P4', 'checker_sees_update') in ('yes', 'partly'))
    s['c3_sees_no'] = sum(1 for k in c3 if V(prim[k], 'P4', 'checker_sees_update') == 'no')
    s['c3_sees_unclear'] = sum(1 for k in c3 if V(prim[k], 'P4', 'checker_sees_update') == 'unclear')
    s['ledger_other_proofs'] = len(other_proofs)
    s['ledger_other_checks'] = len(other_checks)
    s['ledger_records_only'] = len(prim) - len(c3) - len(c3g) - len(other_proofs) - len(other_checks)
    s['onchain_a'] = len(a_led)
    s['onchain_b'] = len(b_led)
    for x in ('plain-updates', 'protected-updates', 'identities-keys', 'reputation-scores', 'rewards-payments', 'hashes-commitments', 'global-model', 'proofs'):
        s[f'oc_{slug(x)}'] = sum(1 for sh in prim.values() if x in L(sh, 'P3', 'on_chain'))
    md_table('ledger_platforms', 'Platforms and consensus of the ledgers of the primary studies.', ['Feature', 'Studies'],
             [['Platform: ' + a, b] for a, b in by('platform')] + [['Consensus: ' + a, b] for a, b in by('consensus')], widths=[30, 70])

    # ---- threats claimed vs tested (P5); Byzantine claims about the consensus apart; † an attack whose set-up is not described
    rows = []
    for t, name in list(THREAT_NAME.items()) + [('byzantine-consensus', 'Byzantine validators or committee members (consensus)')]:
        cl = [k for k, sh in prim.items() if t in threats_of(k, sh, 'claimed')]
        te = [k for k in cl if t in threats_of(k, prim[k], 'tested')]
        if not cl:
            continue
        nd = [k for k in te if t in ATTACK_NOT_DESCRIBED.get(k, set())]
        rows.append([name, f'{len(cl)} {cites(cl)}', f'{len(te)} {cites(te)}' + (f' (attack not described: {cites(nd)})' if nd else '')])
    md_table('threats', 'Threats the designs address, and those they report a test against',
             ['Threat', 'Claimed', 'Test reported'], rows, widths=[24, 46, 30])
    for t in list(THREAT_NAME) + ['byzantine-consensus']:       # claimed and tested, Byzantine claims about the consensus apart
        te = [k for k, sh in prim.items() if t in threats_of(k, sh, 'tested') and t in threats_of(k, sh, 'claimed')]
        s[f'tested_described_{slug(t)}'] = sum(1 for k in te if t not in ATTACK_NOT_DESCRIBED.get(k, set()) and
                                               not (t == 'byzantine-consensus' and k in ATTACK_NOT_DESCRIBED))
        s[f'claimed_learning_{slug(t)}'] = sum(1 for k, sh in prim.items() if t in threats_of(k, sh, 'claimed'))
        s[f'tested_learning_{slug(t)}'] = len(te)
    s['claimed_byz_consensus'] = s['claimed_learning_byzantine_consensus']
    s['tested_byz_consensus'] = s['tested_learning_byzantine_consensus']
    s['net_only'] = sum(1 for sh in prim.values() if network_own(sh) and V(sh, 'P1', 'device_measured') != 'yes')
    s['network_measured_own'] = sum(1 for sh in prim.values() if network_own(sh))
    PRIVACY_ATTACKS = {'inference-privacy-attack', 'malicious-server-aggregator', 'collusion', 'other: data leakage'}
    s['test_privacy_only'] = sum(1 for sh in prim.values() if not attacks_learning(sh) and set(L(sh, 'P5', 'tested')) & PRIVACY_ATTACKS)
    s['test_other_only'] = sum(1 for sh in prim.values() if not attacks_learning(sh) and L(sh, 'P5', 'tested')
                               and not set(L(sh, 'P5', 'tested')) & PRIVACY_ATTACKS)
    s['attack_learning_keys'] = ', '.join(sorted(k for k, sh in prim.items() if attacks_learning(sh)))
    mf = lambda field: [k for k, sh in prim.items() if threats_of(k, sh, field) & {'byzantine-malicious', 'sybil-fake'}]
    s['claimed_mal_fake'], s['tested_mal_fake'] = len(mf('claimed')), len(mf('tested'))
    s['mal_fake_identity_only'] = sum(1 for k, sh in prim.items() if 'identity-membership' in L(sh, 'P4', 'checked')
                                      and not ((threats_of(k, sh, 'claimed') | threats_of(k, sh, 'tested')) & {'byzantine-malicious', 'sybil-fake'}))
    s['tested_described_mal_fake'] = sum(1 for k in mf('tested') if (threats_of(k, prim[k], 'tested') & {'byzantine-malicious', 'sybil-fake'})
                                         - ATTACK_NOT_DESCRIBED.get(k, set()))
    s['laws_dp_list'] = len([k for k, sh in prim.items() if any(DP_LAW.search(str(x)) for x in L(sh, 'P7', 'laws'))])
    s['pd_yes'] = sum(1 for sh in prim.values() if V(sh, 'P7', 'personal_data_on_chain') == 'yes')
    s['pd_no'] = sum(1 for sh in prim.values() if V(sh, 'P7', 'personal_data_on_chain') == 'no')

    # ---- the research gap (Section VIII): the seven condition columns of the spine table, the conditions met, and the two
    # sensitivity analyses; the per-study values are those of the spine table (gap_conditions), so no second table is needed
    G = gap_matrix(prim)
    for col in GAP_COLUMNS:
        s[f'gap_{col.lower()}'] = sum(1 for c, _ in G.values() if c[col])
    s['gap_c4_all'] = sum(1 for c, _ in G.values() if c['C4a'] and c['C4b'] and c['C4c'])
    s['gap_conditions_n'] = len(GAP_COLUMNS)
    s['gap_c5_nopd'] = sum(1 for k in prim if onchain_reading(prim[k]) in ('B', 'C'))
    s['gap_c5_erase'] = sum(1 for k, sh in prim.items() if onchain_reading(sh) not in ('B', 'C') and V(sh, 'P7', 'erasure') == 'addressed')
    met = [m for _, m in G.values()]
    s['gap_max_met'] = max(met)
    s['gap_at_max'] = met.count(s['gap_max_met'])
    for n in range(0, len(GAP_COLUMNS) + 1):
        s[f'gap_met{n}'] = met.count(n)
    s['gap_met_atleast2'] = sum(1 for m in met if m >= 2)
    s['gap_next_met'] = s['gap_max_met'] - 1
    s['gap_at_next'] = met.count(s['gap_next_met'])
    Gd = gap_matrix(prim, described_only=True)          # only attacks whose set-up the study describes
    for col in ('C4a', 'C4b', 'C4c'):
        s[f'gap_{col.lower()}_described'] = sum(1 for c, _ in Gd.values() if c[col])
    s['gap_max_met_described'] = max(m for _, m in Gd.values())
    s['gap_at_max_described'] = sum(1 for _, m in Gd.values() if m == s['gap_max_met_described'])
    Gu = gap_matrix(prim, unclear_as_met=True)          # an unclear answer on who sees the update read as met (C2)
    s['gap_unclear_c2_added'] = sum(1 for c, _ in Gu.values() if c['C2']) - s['gap_c2']
    s['gap_max_met_unclear'] = max(m for _, m in Gu.values())
    s['gap_at_max_unclear'] = sum(1 for _, m in Gu.values() if m == s['gap_max_met_unclear'])

    # ---- research agenda (Section IX): each question, what it measures and against what (V55's questions and plan merged)
    md_table('rqs', 'Research questions of the agenda, what each measures and against what, and the conditions of the gap it takes up.',
             ['RQ', 'Question', 'Measured', 'Compared with', 'Takes up'], [
        ['RQ1 Protection', 'How far does a check computed jointly on secret-shared updates by a committee of gateways, which are also the ledger\'s validators, reduce the success of poisoning, of malicious or fake participants and of free riders, including attackers who know the check, and how many honest clients does it reject?',
         'accuracy and attack success under label flipping, backdoors, sign-flipped or scaled updates and updates crafted to pass the check, at stated attacker shares and degrees of non-IID data; honest clients rejected; a fake registration attempted by a registered insider; free riders detected',
         'no check; the same check on visible updates; robust aggregation; verifiable secure aggregation without a ledger', 'C2, C3, C4'],
        ['RQ2 Cost', 'What do secret sharing, the joint check and the ledger cost on gateway-class hardware and over NG-IoT links, and what would client-side proofs of the check add?',
         'time, energy and memory per round on gateway-class hardware (a single-board computer); bytes per round over emulated 5G links with loss and delay; validation time and throughput as clients grow; proving time and proof size for the optional proof',
         'training without hiding or checking; plain FL; verifiable secure aggregation without a ledger', 'C1'],
        ['RQ3 Privacy and data protection', 'What do the committee, the ledger and the other participants learn, and can a ledger that holds only perfectly hiding commitments, check outcomes and pseudonymous admission records meet the EDPB guidelines, erasure and rectification included?',
         'membership-inference and reconstruction attacks on what each party sees and on the global model; the committee\'s collusion threshold; bytes on-chain per round; the EDPB questions answered; erasure of an off-chain update and the opening of its commitment, end to end; correction of a wrongly recorded outcome',
         'a ledger that records the updates', 'C2, C5']],
        widths=[11, 33, 34, 12, 10])

    # ---- characteristics of the included studies (appendix)
    short = lambda xs, names: ', '.join(names.get(x, x) for x in xs) or '–'
    rows = []
    fy = {r['corpus_id']: r['year'] for r in fin}
    for k, sh in sorted(prim.items(), key=lambda kv: (fy.get(kv[0], ''), kv[0])):
        rows.append([f'[@{k}]', fy.get(k, ''), short(L(sh, 'P1', 'settings'), {}), short(L(sh, 'P1', 'enablers'), ENABLER_SHORT),
                     short([m for m in L(sh, 'P2', 'mechanisms') if m in mechanisms_used(sh)], {}),
                     ', '.join(L(sh, 'P3', 'ledger')), short(L(sh, 'P4', 'checked'), {}), short([t for t in L(sh, 'P5', 'tested')], {}) ])
    md_table('chars_primary', 'Characteristics of the included designs',
             ['Study', 'Year', 'Setting', 'Enabler', 'Privacy', 'Ledger', 'Checked', 'Attacks tested'], rows, widths=[10, 6, 14, 11, 17, 12, 16, 14])
    rows = []
    for k, sh in sorted(sec.items(), key=lambda kv: (fy.get(kv[0], ''), kv[0])):
        n = V(sh, 'S1', 'studies', 'not stated')
        rows.append([f'[@{k}]', fy.get(k, ''), str(n), V(sh, 'S1', 'period', 'not stated'),
                     short(L(sh, 'S3', 'mechanisms'), {})])
    md_table('chars_secondary', 'Characteristics of the secondary studies (from the extraction records).',
             ['Survey', 'Year', 'Studies', 'Period', 'Privacy mechanisms covered'], rows, widths=[10, 7, 10, 20, 53])
