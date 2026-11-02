#!/usr/bin/env python3
"""Independent check of every computed table of the PPML review (build/tables/*.md) against the evidence sheets.

Written separately from thematic.py / data.py (which build the tables): every expected value is recomputed here from the
sheets with the definitions the paper states (Section IV-B for the focus angles, the table captions, the gap conditions of
Section VIII, the quality questionnaire of Section II-E), then compared cell by cell with the built table. Any
difference is printed; nothing is changed.

Usage: python3 scripts/paper_ppml/verify_tables.py
"""
import collections
import csv
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
T = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / 'tables'
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
FIN = list(csv.DictReader(open(ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')))
SH = {r['corpus_id']: json.loads((SHEETS / f"{r['corpus_id']}.json").read_text(encoding='utf-8')) for r in FIN}
KIND = {r['corpus_id']: r['kind'] for r in FIN}
YEAR = {r['corpus_id']: int(r['year']) for r in FIN}
PRIM = sorted(k for k in SH if KIND[k] == 'primary')
SEC = sorted(k for k in SH if KIND[k] == 'secondary')
PROBLEMS = []


def _field(k, q, f):
    """the field in the named answer, else in whichever answer holds it (answers merged on 15 October 2026)"""
    A = SH[k]['answers']
    v = ((A.get(q) or {}).get('values') or {}).get(f)
    if v is None:
        v = next((((a or {}).get('values') or {})[f] for a in A.values() if f in ((a or {}).get('values') or {})), None)
    return v


def vals(k, q, f):
    v = _field(k, q, f)
    return [str(x) for x in v] if isinstance(v, list) else ([] if v in (None, '') else [v])


def one(k, q, f):
    return _field(k, q, f)


def table(key):
    rows = [l for l in (T / f'{key}.md').read_text(encoding='utf-8').splitlines() if l.startswith('| ')]
    split = lambda l: [c.strip() for c in l.strip().strip('|').split(' | ')]
    return split(rows[0]), [split(r) for r in rows[1:]]


def cell(c):
    """'11 [@a; @b]' -> (11, {'a', 'b'}); '[@a]' -> (None, {'a'}); '7' -> (7, set())"""
    keys = set(re.findall(r'@([\w-]+)', c))
    m = re.match(r'^(\d+)\b', c)
    return (int(m.group(1)) if m else None), keys


def report(name, label, got, want):
    if got != want:
        PROBLEMS.append(f'{name} · {label}: table {got!r} ≠ sheets {want!r}')


def studies_row(name, label, c, want):
    n, keys = cell(c)
    report(name, label + ' (studies)', keys, set(want))
    if n is not None:
        report(name, label + ' (count)', n, len(set(want)))


LEDGER_TAG = {'proof of work': 'PoW', 'proof of stake': 'PoS', 'proof of authority': 'PoA',
              'consortium or permissioned': 'consortium-permissioned', 'not stated': 'not-stated', 'Hyperledger Fabric': 'Hyperledger-Fabric',
              'FISCO BCOS': 'FISCO-BCOS', 'logs and metadata': 'logs-metadata', 'identities and keys': 'identities-keys',
              'hashes and commitments': 'hashes-commitments', 'the global model': 'global-model', 'protected updates': 'protected-updates',
              'plain updates': 'plain-updates', 'reputation scores': 'reputation-scores', 'rewards and payments': 'rewards-payments',
              'records and audits the training': 'record-audit', 'identity and access control': 'identity-access',
              'incentives and reputation': 'incentive-reputation', 'replaces the server': 'replaces-server', 'verifies updates': 'update-verification',
              'verifies proofs': 'proof-verification', 'aggregates the updates': 'aggregation'}
WORD_TAG = {'raw data': 'raw-data', 'the global model': 'global-model', 'identities': 'identity', 'the server or aggregator': 'server-aggregator',
            'other participants': 'other-participants', 'ledger nodes': 'ledger-nodes', 'external attackers': 'external-attacker', 'the public': 'public'}
IS_OTHER = lambda x: x == 'other' or x.startswith('other:')
LEARNING = {'poisoning', 'backdoor', 'byzantine-malicious', 'sybil-fake', 'free-riding'}


# ---- The review's recorded classification decisions (thematic.py holds them with the words of the records that ground each);
# only these data are shared with the scripts that build the tables, every rule that applies them is written again here.
sys.path.insert(0, str(ROOT / 'scripts' / 'paper_ppml'))
import thematic as _D                                                     # noqa: E402  (decisions only)
ZK_RELATION, BYZ_CONSENSUS, NOT_DESCRIBED = _D.ZK_RELATION, set(_D.BYZ_CONSENSUS), _D.ATTACK_NOT_DESCRIBED
CLASS_OVERRIDE, NOT_CONTENT, BAND, OTHER_A = _D.CHECK_CLASS_OVERRIDE, set(_D.LEDGER_CHECK_NOT_CONTENT), _D.EDPB_BAND, _D.OTHER_ON_CHAIN_A
NOISED = set(_D.NOISED_BEFORE_AGGREGATOR)                             # noise added before the update reaches anyone (P2 words)
CONFID = {'HE', 'SMPC', 'secret-sharing', 'masking-secure-aggregation', 'TEE', 'functional-encryption'}
NOT_MECHANISM = re.compile(r'data locality|instead of raw data|abstract only|named only', re.I)


def threats(k, field):
    """P5 claimed or tested; a Byzantine claim about the consensus is kept apart from malicious participants"""
    t = set(vals(k, 'P5', field))
    if k in BYZ_CONSENSUS and 'byzantine-malicious' in t:
        t = (t - {'byzantine-malicious'}) | {'byzantine-consensus'}
    return t


learning_attack = lambda k: bool(set(vals(k, 'P5', 'tested')) & LEARNING)     # the three threats of SQ4 (II-E)
hides = lambda k: 'updates' in vals(k, 'P2', 'protects') and 'server-aggregator' in vals(k, 'P2', 'hidden_from')
used_mech = lambda k: {m for m in vals(k, 'P2', 'mechanisms') if not (m.startswith('other:') and NOT_MECHANISM.search(m))}


def kept_from_aggregator(k):
    if not hides(k):
        return 'noised' if k in NOISED else ''
    return 'hidden' if used_mech(k) & CONFID else ('noised' if used_mech(k) & {'DP', 'LDP'} else '')


def what_checked(k):
    if k in CLASS_OVERRIDE:
        return CLASS_OVERRIDE[k]
    ch = set(vals(k, 'P4', 'checked'))
    if ch & {'test-accuracy-quality', 'similarity-distance', 'norm-bound', 'anomaly-detection', 'correct-training'} or \
            any(IS_OTHER(c) and re.search(r'local updates|model verification by miners|validate received updates|committed update polynomial|model updates called', c, re.I) for c in ch):
        return 'content'
    if 'correct-aggregation' in ch:
        return 'aggregation'
    if ch & {'identity-membership', 'contribution-reputation'}:
        return 'participants'
    return 'none' if not ch or ch == {'none'} else 'other'


def ledger_checks(k):
    """C3: the ledger's nodes or contracts check the content of the updates, or verify on the ledger a proof about each update
    or its training (a proof of the aggregation alone does not count)"""
    roles = set(vals(k, 'P3', 'roles'))
    if 'update-verification' in roles and k not in NOT_CONTENT and what_checked(k) == 'content':
        return True
    return 'proof-verification' in roles and ZK_RELATION.get(k) in ('bound', 'training') \
        and one(k, 'P4', 'zk_on_chain') == 'yes'


ledger_checks_agg = lambda k: (not ledger_checks(k) and 'proof-verification' in vals(k, 'P3', 'roles') and ZK_RELATION.get(k) == 'aggregation'
                               and one(k, 'P4', 'zk_on_chain') == 'yes')
ledger_other = lambda k: (not ledger_checks(k) and not ledger_checks_agg(k)
                          and bool(set(vals(k, 'P3', 'roles')) & {'proof-verification', 'update-verification'}))


band = lambda x: (('A' if OTHER_A.search(x) else 'B') if IS_OTHER(x) else BAND.get(x, 'B'))
holds_a = lambda k: any(band(x) == 'A' for x in vals(k, 'P3', 'on_chain'))


# ---- Table: years ------------------------------------------------------------------------------------------------
def check_years():
    head, rows = table('years')
    tot = [0] * 7
    for r in rows[:-1]:
        y = int(r[0].rstrip('*'))
        P = [k for k in PRIM if YEAR[k] == y]
        want = [len(P), sum(YEAR[k] == y for k in SEC), sum(1 for k in P if learning_attack(k)),
                sum(1 for k in P if one(k, 'P4', 'zk_used') is True), sum(1 for k in P if ZK_RELATION.get(k) in ('bound', 'training')),
                sum(1 for k in P if one(k, 'P1', 'device_measured') == 'yes'), sum(1 for k in P if one(k, 'P6', 'code') == 'yes')]
        tot = [a + b for a, b in zip(tot, want)]
        for h, g, w in zip(head[1:], r[1:], want):
            report('years', f'{y} {h}', int(g), w)
    for h, g, w in zip(head[1:], rows[-1][1:], tot):
        report('years', f'Total {h}', int(g), w)


# ---- The focus angles (Section II-A), for the text and the trends figure ---------------------------------------------
CONTENT_CHECKS = {'test-accuracy-quality', 'similarity-distance', 'norm-bound', 'correct-training', 'correct-aggregation',
                  'anomaly-detection', 'contribution-reputation'}                      # not identities, signatures or format
BY_ZK = {'training': 'correct-training', 'bounded': 'norm-bound', 'aggregation': 'correct-aggregation', 'similarity': 'similarity-distance'}


def verification(k):
    """checks the content of updates, the training or the aggregation by means other than a ZKP (Section II-A); the
    explicit value verification_other_means, where a sheet records one, decides; a check that no party runs never counts"""
    if what_checked(k) not in ('content', 'aggregation'):
        return False
    v = one(k, 'P4', 'verification_other_means')
    if isinstance(v, bool):
        return v
    checks = set(vals(k, 'P4', 'checked')) & CONTENT_CHECKS
    if one(k, 'P4', 'zk_used') is True:
        checks -= {BY_ZK[x.split(':')[0].strip()] for x in vals(k, 'P4', 'zk_shows') if x.split(':')[0].strip() in BY_ZK}
    return bool(checks)


def prim_angles(k):
    ct = threats(k, 'claimed') | threats(k, 'tested')
    return {'Poisoning': bool(ct & {'poisoning', 'backdoor'}),
            'Malicious or fake participants': bool(ct & {'byzantine-malicious', 'sybil-fake'}) or 'identity-membership' in vals(k, 'P4', 'checked'),
            'Free riding': 'free-riding' in ct,
            'Verification of learning': verification(k),          # the angles table's row (Table of Section IV-B)
            'Verification (not by ZKP)': verification(k),         # the same angle as the trends figure labels it (Fig. S1)
            'ZKPs': one(k, 'P4', 'zk_used') is True,
            'Blockchain': True}


def sec_angles(k):
    f = {'Poisoning': 'poisoning', 'Malicious or fake participants': 'malicious_fake', 'Free riding': 'free_riding',
         'Verification of learning': 'verification', 'ZKPs': 'zkp', 'Blockchain': 'blockchain'}
    return {a: one(k, 'S4', x) == 'subject' for a, x in f.items()}


def check_angles():
    """the angle counts that Section IV-B states (build/stats.json) and its table of the two tiers (restored in V58)"""
    head, rows = table('angles')
    report('angles', 'columns', head[2:], [f'Primary studies ({len(PRIM)})', f'Surveys ({len(SEC)})'])
    report('angles', 'angles listed', [r[1] for r in rows], ['Verification of learning', 'ZKPs', 'Blockchain', 'Poisoning', 'Malicious or fake participants', 'Free riding'])
    for r in rows:
        report('angles', f'{r[1]} by tier', [int(r[2]), int(r[3])],
               [sum(prim_angles(k)[r[1]] for k in PRIM), sum(sec_angles(k)[r[1]] for k in SEC)])
    st = json.loads((ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / 'stats.json').read_text(encoding='utf-8'))
    key = {'Verification of learning': 'verification', 'ZKPs': 'zero_knowledge', 'Blockchain': 'blockchain', 'Poisoning': 'poisoning',
           'Malicious or fake participants': 'malicious', 'Free riding': 'free'}
    for a, x in key.items():
        report('angles', f'{a} primary', st.get(f'ang_prim_{x}'), sum(prim_angles(k)[a] for k in PRIM))
        report('angles', f'{a} surveys', st.get(f'ang_sec_{x}'), sum(sec_angles(k)[a] for k in SEC))


# ---- Table: zk (what the proofs prove, by the relation each study states) -------------------------------------------
ZK_ROW = {'A norm or range bound on the committed update': 'bound', 'Correct training of the update, with the relation stated': 'training',
          'Correct training or constraints on the update, relation not stated': 'unspecified-update',
          'Consistency of the update with its commitment, presented as proof of training': 'commitment',
          'An inference made with a committed or public model': 'inference', 'Correct aggregation': 'aggregation',
          'Identity, membership or eligibility': 'identity', 'Other records (a training loss; supply-chain data)': 'other',
          'A statement the study does not specify': 'unspecified'}


def check_zk():
    head, rows = table('zk')
    users = [k for k in PRIM if one(k, 'P4', 'zk_used') is True]
    report('zk', 'every user of ZKPs classified', set(users), set(ZK_RELATION))
    seen = set()
    for r in rows:
        rel = ZK_ROW[r[0]]
        ids = [k for k in users if ZK_RELATION.get(k) == rel]
        seen |= set(ids)
        studies_row('zk', r[0], r[1], ids)
        report('zk', f'{r[0]} verified on the ledger', int(r[2].split()[0]), sum(one(k, 'P4', 'zk_on_chain') == 'yes' for k in ids))
        hid = [k for k in ids if one(k, 'P4', 'checker_sees_update') == 'no']
        if hid or r[3] != '–':
            studies_row('zk', f'{r[0]} no checking party sees', r[3], hid)
        for part in r[4].split('; ['):                                  # every number of a cost occurs in that study's checking answer
            m = re.search(r'@([\w-]+)', part)
            if not m:
                continue
            ans = SH[m.group(1)]['answers']['P4'].get('answer', '')
            for num in re.findall(r'(?<![\w.])\d+(?:[.,]\d+)*', part.split('[@')[0]):
                if num not in ans and num.replace(',', '') not in ans.replace(',', ''):
                    PROBLEMS.append(f'zk · cost {num} of {m.group(1)} is not in its P4 answer')
    report('zk', 'studies listed', seen, set(users))


# ---- Table: surveys ----------------------------------------------------------------------------------------------
MARK = {'subject': 'Yes', 'mentioned': 'Partial', 'absent': 'No'}
SURVEY_COLS = {'SQ1 NG-IoT fabric': ('S2', 'fabric'), 'SQ2 Privacy mechanisms': ('S2', 'privacy'), 'SQ3 Verification of learning': ('S4', 'verification'),
               'SQ3 ZKPs': ('S4', 'zkp'), 'SQ3 Blockchain': ('S4', 'blockchain'), 'SQ4 Poisoning': ('S4', 'poisoning'),
               'SQ4 Malicious or fake participants': ('S4', 'malicious_fake'), 'SQ4 Free riding': ('S4', 'free_riding'), 'SQ5 Data-protection law': ('S2', 'regulation')}


def check_surveys():
    head, rows = table('surveys')
    cols = SURVEY_COLS
    seen = set()
    for r in rows:
        if r[0] == 'This review':
            continue
        k = cell(r[0])[1].pop()
        seen.add(k)
        for h, g in zip(head[1:], r[1:]):
            report('surveys', f'{k} {h}', g, MARK.get(one(k, *cols[h]), '?'))
    report('surveys', 'surveys listed', seen, set(SEC))


# ---- Table: fabric -----------------------------------------------------------------------------------------------
SETTING = {'IoT (general)': 'IoT-general', 'Vehicular': 'IoV-vehicular', 'Industrial IoT': 'IIoT',
           'Medical IoT and healthcare': 'IoMT-healthcare', 'Smart grid and energy': 'smart-grid-energy',
           'Smart city and home': 'smart-city-home', 'Communication networks': 'communication-network', 'Maritime': 'maritime',
           'UAV and space–air–ground': 'UAV-space', 'Supply chain': 'supply-chain'}
ENABLER = {'edge computing': 'edge', 'cloud': 'cloud', '5G or 6G networks': '5G-6G', 'none stated': 'none-stated',
           'multi-access edge computing': 'MEC'}


def check_fabric():
    head, rows = table('fabric')
    for r in rows:
        lab = r[0]
        if lab.startswith('Setting: '):
            tag = SETTING[lab[9:]]
            want = [k for k in PRIM if tag in vals(k, 'P1', 'settings')]
        elif lab.startswith('Enabler: '):
            tag = ENABLER[lab[9:]]
            want = [k for k in PRIM if tag in vals(k, 'P1', 'enablers')]
        elif lab == 'Cost measured on device-class hardware':
            want = [k for k in PRIM if one(k, 'P1', 'device_measured') == 'yes']
        elif lab == 'Cost measured over a network link':
            want = [k for k in PRIM if one(k, 'P1', 'network_measured') == 'yes']
        elif lab == 'Design measured on devices connected over 5G':
            want = [k for k in PRIM if '5G-6G' in vals(k, 'P1', 'enablers') and one(k, 'P1', 'network_measured') == 'yes']
        elif lab == 'Ledger simulated rather than run':
            want = [k for k in PRIM if 'simulated' in vals(k, 'P3', 'platform')]
        else:
            PROBLEMS.append(f'fabric · unknown row {lab!r}')
            continue
        studies_row('fabric', lab, r[1], want)


# ---- Table: privacy (by kind of protection) ------------------------------------------------------------------------
MECH = {'Differential privacy': 'DP', 'Local differential privacy': 'LDP', 'Homomorphic encryption': 'HE',
        'Secure multi-party computation': 'SMPC', 'Secret sharing': 'secret-sharing',
        'Masking and secure aggregation': 'masking-secure-aggregation', 'Trusted execution environment': 'TEE',
        'Zero-knowledge proofs': 'ZKP', 'Pseudonyms and anonymity': 'pseudonyms-anonymity',
        'Encryption in transit only': 'encryption-in-transit-only', 'Functional encryption': 'functional-encryption'}
KIND_OF = {'HE': 'Confidentiality of the update', 'secret-sharing': 'Confidentiality of the update', 'SMPC': 'Confidentiality of the update',
           'masking-secure-aggregation': 'Confidentiality of the update', 'TEE': 'Confidentiality of the update',
           'functional-encryption': 'Confidentiality of the update', 'DP': 'Output privacy', 'LDP': 'Output privacy',
           'pseudonyms-anonymity': 'Unlinkability', 'ZKP': 'Proofs that hide their witness', 'encryption-in-transit-only': 'Transport only'}


def check_privacy():
    head, rows = table('privacy')
    listed = set()
    for r in rows:
        tag = MECH[r[1]]
        listed.add(tag)
        report('privacy', f'{r[1]} kind', r[0], KIND_OF[tag])
        want = [k for k in PRIM if tag in used_mech(k)]
        studies_row('privacy', r[1], r[2], want)
        if r[0] == 'Confidentiality of the update':
            report('privacy', f'{r[1]} hidden from the aggregator', int(re.search(r'in (\d+) of these', r[3]).group(1)),
                   sum(kept_from_aggregator(k) == 'hidden' for k in want))
        if r[0] == 'Output privacy':
            report('privacy', f'{r[1]} noise only', int(re.search(r'in (\d+) designs', r[3]).group(1)),
                   sum(kept_from_aggregator(k) == 'noised' for k in want))
    report('privacy', 'every mechanism used has a row', listed, {m for k in PRIM for m in used_mech(k) if m in KIND_OF})


# ---- Table: ledger (type, what it does, what it holds read against the EDPB criteria) ---------------------------------
def check_ledger():
    head, rows = table('ledger')
    c3 = [k for k in PRIM if ledger_checks(k)]
    agg = [k for k in PRIM if ledger_checks_agg(k)]
    other = [k for k in PRIM if 'proof-verification' in vals(k, 'P3', 'roles') and k not in c3 + agg]
    BANDS = {'remains personal data where it relates to a person': 'A', 'depends on the scheme': 'B', 'reveals nothing about its witness': 'C'}
    for r in rows:
        aspect, feat = r[0], r[1]
        if aspect == 'Type':
            tag = LEDGER_TAG.get(feat, feat)
            want = [k for k in PRIM if (any(IS_OTHER(x) for x in vals(k, 'P3', 'ledger')) if tag == 'other' else tag in vals(k, 'P3', 'ledger'))]
        elif aspect == 'What the ledger does' and feat.startswith('checks the updates itself'):
            want = c3
        elif aspect == 'What the ledger does' and feat.startswith('verifies a proof that the aggregation is correct'):
            want = agg
        elif aspect == 'What the ledger does' and feat.startswith('verifies proofs of other statements only'):
            want = other
        elif aspect == 'What the ledger does' and feat.startswith('checks signatures, deadlines, freshness or format'):
            want = [k for k in PRIM if ledger_other(k) and k not in other]
        elif aspect == 'What the ledger does':
            tag = LEDGER_TAG.get(feat, feat)
            want = [k for k in PRIM if (any(IS_OTHER(x) for x in vals(k, 'P3', 'roles')) if tag == 'other' else tag in vals(k, 'P3', 'roles'))]
        elif aspect.startswith('What it holds ('):
            b = BANDS[aspect[len('What it holds ('):-1]]
            items = vals
            if feat in ('other personal records', 'other records'):
                want = [k for k in PRIM if any(IS_OTHER(x) and band(x) == b for x in vals(k, 'P3', 'on_chain'))]
            else:
                tag = LEDGER_TAG.get(feat, feat)
                report('ledger', f'{feat} band', BAND.get(tag), b)
                want = [k for k in PRIM if tag in vals(k, 'P3', 'on_chain')]
        elif aspect == 'What it holds' and feat.startswith('at least one record'):
            report('ledger', feat, int(r[2]), sum(holds_a(k) for k in PRIM))
            continue
        elif aspect == 'What it holds' and feat.startswith('only records'):
            want = [k for k in PRIM if not holds_a(k)]
        else:
            PROBLEMS.append(f'ledger · unknown row {aspect!r} {feat!r}')
            continue
        studies_row('ledger', f'{aspect}: {feat[:40]}', r[2], want)


# ---- Table: threats (supplementary material) ----------------------------------------------------------------------
THREAT = {'Poisoning': 'poisoning', 'Backdoor': 'backdoor', 'Byzantine or malicious participants': 'byzantine-malicious',
          'Sybil or fake participants': 'sybil-fake', 'Free riding': 'free-riding', 'Inference and other privacy attacks': 'inference-privacy-attack',
          'Malicious or curious server or aggregator': 'malicious-server-aggregator', 'Collusion': 'collusion',
          'Denial of service': 'dos-ddos', 'Single point of failure': 'single-point-of-failure', 'Tampering with records or models': 'tampering',
          'Byzantine validators or committee members (consensus)': 'byzantine-consensus'}


def check_threats():
    head, rows = table('threats')
    for r in rows:
        tag = THREAT[r[0]]
        cl = [k for k in PRIM if tag in threats(k, 'claimed')]
        te = [k for k in cl if tag in threats(k, 'tested')]
        studies_row('threats', f'{r[0]} claimed', r[1], cl)
        main, _, nd = r[2].partition(' (attack not described:')
        if te or main not in ('0', '–'):
            studies_row('threats', f'{r[0]} tested', main, te)
        report('threats', f'{r[0]} attack not described', set(re.findall(r'@([\w-]+)', nd)), {k for k in te if tag in NOT_DESCRIBED.get(k, set())})


# ---- Table: checks (what is checked against whether the party that checks sees the update) ----------------------------
CLASS = {'The content of individual updates or their training': 'content', 'The aggregation only': 'aggregation',
         'Identities, signatures, format or contributions only': 'participants', 'An inference or other records only': 'other', 'Nothing': 'none'}
CHECKER = {'a server': 'server', 'a committee, validators or miners': 'committee-validators-miners', 'a smart contract': 'smart-contract',
           'peers or clients': 'peers-clients', 'a TEE': 'TEE', 'a trusted authority': 'trusted-authority'}


def check_checks():
    head, rows = table('checks')
    for r in rows:
        c = CLASS[r[0]]
        ids = [k for k in PRIM if what_checked(k) == c]
        report('checks', f'{r[0]} studies', int(r[1]), len(ids))
        for col, v in zip(r[2:7], ('yes', 'partly', 'no', 'unclear', 'no-check')):
            sub = [k for k in ids if one(k, 'P4', 'checker_sees_update') == v]
            if sub or col != '–':
                studies_row('checks', f'{r[0]} sees {v}', col, sub)
        cnt = collections.Counter(x for k in ids for x in set(vals(k, 'P4', 'checker')) if x != 'none' and not IS_OTHER(x))
        got = {CHECKER.get(m.group(1).strip(), m.group(1).strip()): int(m.group(2)) for m in re.finditer(r'([^;(]+)\((\d+)\)', r[7])}
        report('checks', f'{r[0]} checked by', got, dict(cnt))
    report('checks', 'every study classified once', sum(int(r[1]) for r in rows), len(PRIM))


# ---- Table: gap (the five conditions and the closest designs) -----------------------------------------------------------
def conditions(k, described_only=False, unclear_as_met=False):
    """C1, C2, C3, C4a, C4b, C4c, C5 by the definitions of Section VIII-A"""
    t = threats(k, 'tested')
    if described_only:
        t = t - NOT_DESCRIBED.get(k, set())
    unseen = ('no', 'no-check', 'unclear') if unclear_as_met else ('no', 'no-check')
    return [one(k, 'P1', 'device_measured') == 'yes',
            kept_from_aggregator(k) == 'hidden' and one(k, 'P4', 'checker_sees_update') in unseen,
            ledger_checks(k),
            bool({'poisoning', 'backdoor'} & t),
            bool({'byzantine-malicious', 'sybil-fake'} & t),
            bool({'free-riding'} & t),
            not holds_a(k) or one(k, 'P7', 'erasure') == 'addressed']


met = lambda c: sum(c)


def check_gap():
    """the gap statistics of Section VIII, recomputed from the sheets (the per-study values are checked with the spine table)"""
    s = json.loads(STATS.read_text(encoding='utf-8'))
    C = {k: conditions(k) for k in PRIM}
    for i, col in enumerate(('c1', 'c2', 'c3', 'c4a', 'c4b', 'c4c', 'c5')):
        report('gap', f'gap_{col}', s.get(f'gap_{col}'), sum(c[i] for c in C.values()))
    m = [met(c) for c in C.values()]
    report('gap', 'gap_max_met', s.get('gap_max_met'), max(m))
    report('gap', 'gap_at_max', s.get('gap_at_max'), m.count(max(m)))
    report('gap', 'gap_next_met', s.get('gap_next_met'), max(m) - 1)
    report('gap', 'gap_at_next', s.get('gap_at_next'), m.count(max(m) - 1))
    for n in range(8):
        report('gap', f'gap_met{n}', s.get(f'gap_met{n}'), m.count(n))
    report('gap', 'gap_c5_nopd', s.get('gap_c5_nopd'), sum(not holds_a(k) for k in PRIM))
    report('gap', 'gap_c5_erase', s.get('gap_c5_erase'), sum(holds_a(k) and one(k, 'P7', 'erasure') == 'addressed' for k in PRIM))
    D = {k: conditions(k, described_only=True) for k in PRIM}
    for i, col in ((3, 'c4a'), (4, 'c4b'), (5, 'c4c')):
        report('gap', f'gap_{col}_described', s.get(f'gap_{col}_described'), sum(c[i] for c in D.values()))
    report('gap', 'gap_max_met_described', s.get('gap_max_met_described'), max(met(c) for c in D.values()))
    # the two gap tables restored in V58: each condition with the designs that meet it; the designs meeting at least two
    COLS = ['C1', 'C2', 'C3', 'C4a', 'C4b', 'C4c', 'C5']
    head, rows = table('gap_conditions')
    report('gap_conditions', 'conditions', [r[0] for r in rows], COLS)
    report('gap_conditions', 'from', [r[2] for r in rows], [f'SQ{c[1]}' for c in COLS])
    report('gap_conditions', 'studies meeting each', [int(r[3]) for r in rows], [sum(c[i] for c in C.values()) for i in range(7)])
    head, rows = table('gap')
    report('gap', 'columns', [h.split(' ')[0] for h in head[1:-1]] + [head[-1]], COLS + ['Met'])
    tags = [None, None, None, {'poisoning', 'backdoor'}, {'byzantine-malicious', 'sybil-fake'}, {'free-riding'}, None]
    got = set()
    for r in rows:
        k = cell(r[0])[1].pop()
        got.add(k)
        te, nd = threats(k, 'tested'), NOT_DESCRIBED.get(k, set())
        want = ['' if not x else '\u2713\u2020' if tags[i] and not ((te & tags[i]) - nd) else '\u2713' for i, x in enumerate(C[k])]
        report('gap', k, r[1:-1], want)
        report('gap', f'{k} met', int(r[-1]), met(C[k]))
    report('gap', 'designs listed: every one meeting at least two', got, {k for k, c in C.items() if met(c) >= 2})
    report('gap', 'gap_met_atleast2', s.get('gap_met_atleast2'), sum(met(c) >= 2 for c in C.values()))
    U = {k: conditions(k, unclear_as_met=True) for k in PRIM}
    report('gap', 'gap_unclear_c2_added', s.get('gap_unclear_c2_added'), sum(c[1] for c in U.values()) - sum(c[1] for c in C.values()))
    report('gap', 'gap_max_met_unclear', s.get('gap_max_met_unclear'), max(met(c) for c in U.values()))


DP_LAW = re.compile(r'\bGDPR\b|General Data Protection|\bCCPA\b|\bCPRA\b|\bHIPAA\b|\bPIPL\b|\bPIPEDA\b|\bLGPD\b|\bPDPA\b|\bEDPB\b|data protection', re.I)


# ---- Tables: quality appraisal (questionnaire of Section II-E) ----------------------------------------------------
def check_qa():
    cons = json.loads((ROOT / 'search-ppml' / 'evidence' / 'QA-CONSISTENCY-2026-10-05.json').read_text(encoding='utf-8'))
    G = {1: 'Yes', 0.5: 'Partial', 0: 'No'}
    TEST = {'poisoning', 'backdoor', 'byzantine-malicious', 'sybil-fake', 'free-riding', 'inference-privacy-attack', 'collusion', 'malicious-server-aggregator'}
    head, rows = table('qa_primary')
    got = set()
    for r in rows:
        k = cell(r[0])[1].pop()
        got.add(k)
        ds = vals(k, 'P6', 'datasets')
        q1 = 0 if not ds else (0.5 if all(re.search(r'unnamed|not named|not stated', x, re.I) for x in ds) else 1)
        q2 = 1 if vals(k, 'P6', 'baselines') else 0
        cl = TEST & threats(k, 'claimed')
        te = cl & threats(k, 'tested')
        q3 = 1 if cl and te == cl else (0.5 if te else 0)
        nm = one(k, 'P1', 'network_measured') == 'yes'
        q4 = 1 if one(k, 'P1', 'device_measured') == 'yes' or (nm and one(k, 'P1', 'network_measured_own') is not False) else (0.5 if nm else 0)
        q5 = 1 if one(k, 'P6', 'code') == 'yes' else 0
        q6 = 0 if k in cons['no'] else (0.5 if k in cons['partial'] else 1)
        want = [q1, q2, q3, q4, q5, q6]
        for i, w in enumerate(want):
            report('qa_primary', f'{k} QA{i + 1}', r[1 + i], G[w])
    report('qa_primary', 'studies listed', got, set(PRIM))
    head, rows = table('qa_secondary')
    part = re.compile(r'\bonly\b|approx|≈|\bFig\.|figure', re.I)
    got = set()
    for r in rows:
        k = cell(r[0])[1].pop()
        got.add(k)
        per = str(one(k, 'S1', 'period') or '')
        q1 = (0.5 if part.search(per) else 1) if vals(k, 'S1', 'databases') else 0
        q2 = 0 if (not per or per.lower().startswith('not stated')) else (0.5 if part.search(per) or 'not stated' in per.lower() else 1)
        n = one(k, 'S1', 'studies')
        n = 'not stated' if n in (None, '') else n
        q3 = 1 if isinstance(n, int) or str(n).isdigit() else (0 if not re.search(r'\d', str(n)) else (0.5 if part.search(str(n)) else (1 if re.match(r'\d[\d,]*\b', str(n)) else 0.5)))
        lim = one(k, 'S8', 'own_limitations')
        q4 = {'yes': 1, 'partial': 0.5, 'no': 0}.get(lim, None)
        if q4 is None:
            q4 = 0 if str(SH[k]['answers'].get('S8', {}).get('answer', '')).lower().startswith(('not stated', 'no limitation')) else 1
        want = [q1, q2, q3, q4]
        for i, w in enumerate(want):
            report('qa_secondary', f'{k} QS{i + 1}', r[1 + i], G[w])
    report('qa_secondary', 'surveys listed', got, set(SEC))


# ---- Figures with saved data (build/figures/<name>.data.json) -------------------------------------------------------
FIGS = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / 'figures'


def fig(name):
    d = json.loads((FIGS / f'{name}.data.json').read_text(encoding='utf-8'))
    for k in ('panels', 'rows'):
        if isinstance(d.get(k), str):
            import ast
            d[k] = ast.literal_eval(d[k])
    return d


def check_fig_threats():
    d = fig('threats')
    tag = dict(THREAT)
    for i, c in enumerate(d['categories']):
        t = tag[c] if c in tag else tag[c + ' (consensus)']
        cl = [k for k in PRIM if t in threats(k, 'claimed')]
        te = [k for k in cl if t in threats(k, 'tested')]
        report('Fig threats', f'{c} claimed', d['series'][0][2][i], len(cl))
        report('Fig threats', f'{c} tested', d['series'][1][2][i], len(te))
        report('Fig threats', f'{c} tested, attack described', d['series'][2][2][i],
               sum(1 for k in te if t not in NOT_DESCRIBED.get(k, set()) and not (t == 'byzantine-consensus' and k in NOT_DESCRIBED)))


def check_fig_trends():
    d = fig('trends')
    (pa, ra), (pb, rb) = d['panels'][0], d['panels'][1]
    for name, row in ra:
        for i, y in enumerate(range(2020, 2027)):
            want = sum(prim_angles(k)[name] for k in PRIM if YEAR[k] == y)        # primary studies only (never added to surveys)
            report('Fig trends (a)', f'{name} {y}', row[i], want)
    MB = {'Differential privacy (DP, LDP)': {'DP', 'LDP'}, 'Homomorphic encryption (HE)': {'HE'}, 'Secret sharing, SMPC, masking': {'secret-sharing', 'SMPC', 'masking-secure-aggregation'},
          'Trusted execution (TEE)': {'TEE'}, 'Zero-knowledge proofs (ZKP)': {'ZKP'}, 'Pseudonyms, anonymity': {'pseudonyms-anonymity'}}
    for name, row in rb:
        for i, y in enumerate(range(2020, 2027)):
            want = sum(1 for k in PRIM if YEAR[k] == y and MB[name] & set(vals(k, 'P2', 'mechanisms')))
            report('Fig trends (b)', f'{name} {y}', row[i], want)


def check_fig_survey_coverage():
    d = fig('survey_coverage')
    refs = json.loads((ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json').read_text(encoding='utf-8'))
    name = {f"{refs.get(k, {}).get('first_author_surname', k)} {YEAR[k]}": k for k in SEC}
    cols = list(SURVEY_COLS.values())
    report('Fig survey_coverage', 'columns', d['columns'], [h.split(' ', 1)[1] for h in SURVEY_COLS])
    report('Fig survey_coverage', 'surveys shown', len(d['rows']), len(SEC))
    for lab, marks in d['rows']:
        k = name.get(lab)
        if k is None:
            PROBLEMS.append(f'Fig survey_coverage · unknown row {lab!r}')
            continue
        report('Fig survey_coverage', lab, marks, [MARK[one(k, q, f) or 'absent'] for q, f in cols])


# ---- Numbers drawn in the diagrams (taxonomy, architecture, spine) from build/stats.json -------------------------------
STATS = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / 'stats.json'
LEARNING = {'poisoning', 'backdoor', 'byzantine-malicious', 'sybil-fake', 'free-riding'}     # attacks on the learning (Section VI-E)
TAGS = {'en': {'5g_6g': '5G-6G', 'cloud': 'cloud', 'edge': 'edge', 'fog': 'fog', 'mec': 'MEC'},
        'set': {'iiot': 'IIoT', 'iomt_healthcare': 'IoMT-healthcare', 'iot_general': 'IoT-general', 'iov_vehicular': 'IoV-vehicular',
                'smart_grid_energy': 'smart-grid-energy', 'uav_space': 'UAV-space'},
        'mech': {'dp': 'DP', 'he': 'HE', 'ldp': 'LDP', 'smpc': 'SMPC', 'tee': 'TEE', 'zkp': 'ZKP'}}
DP_LAWS = re.compile(r'GDPR|General Data Protection|CCPA|CPRA|HIPAA|PIPL|PIPEDA|LGPD|PDPA|EDPB|data protection', re.I)


def expected(key):
    """the count a diagram shows, recomputed from the sheets by the definition the paper states"""
    P = PRIM
    pre, _, rest = key.partition('_')
    tag = lambda: TAGS.get(pre, {}).get(rest, rest.replace('_', '-'))
    if key == 'primary':
        return len(P)
    if key == 'ledger_checks_updates':                          # before the prefix rules below ('ledger_…' is a ledger type there)
        return sum(ledger_checks(k) for k in P)
    if key == 'ledger_checks_aggregation':
        return sum(ledger_checks_agg(k) for k in P)
    if key == 'ledger_other_proofs':
        return sum('proof-verification' in vals(k, 'P3', 'roles') and not ledger_checks(k) and not ledger_checks_agg(k) for k in P)
    if key == 'ledger_other_checks':
        return sum(ledger_other(k) and 'proof-verification' not in vals(k, 'P3', 'roles') for k in P)
    if key == 'ledger_records_only':
        return sum(not (ledger_checks(k) or ledger_checks_agg(k) or ledger_other(k)) for k in P)
    if key == 'gap_c2':
        return sum(conditions(k)[1] for k in P)
    if key == 'gap_c5_nopd':
        return sum(not holds_a(k) for k in P)
    if key == 'gap_c5_erase':
        return sum(holds_a(k) and one(k, 'P7', 'erasure') == 'addressed' for k in P)
    if key in ('device_measured', 'network_measured'):
        return sum(one(k, 'P1', key) == 'yes' for k in P)
    if key == 'code_yes':
        return sum(one(k, 'P6', 'code') == 'yes' for k in P)
    if key == 'with_baselines':
        return sum(bool(vals(k, 'P6', 'baselines')) for k in P)
    if key == 'zk_used':
        return sum(one(k, 'P4', 'zk_used') is True for k in P)
    if key == 'erasure_addressed':
        return sum(one(k, 'P7', 'erasure') == 'addressed' for k in P)
    if key == 'laws_named':
        return sum(any(DP_LAWS.search(x) for x in vals(k, 'P7', 'laws')) for k in P)
    if key == 'gdpr_named':
        return sum(any('gdpr' in x.lower() for x in vals(k, 'P7', 'laws')) for k in P)
    if key == 'hid_server_aggregator':
        return sum(hides(k) for k in P)
    if key == 'no_attack_tested':          # N019's replayed updates corrupt the aggregation: an attack on the learning
        return sum(not (LEARNING & set(vals(k, 'P5', 'tested')) or 'other: replay' in vals(k, 'P5', 'tested')) for k in P)
    if key == 'sees_yes_partly':
        return sum(one(k, 'P4', 'checker_sees_update') in ('yes', 'partly') for k in P)
    if key == 'sees_with_check':
        return sum(one(k, 'P4', 'checker_sees_update') != 'no-check' for k in P)
    if key == 'mech_two_or_more':          # FL's own data locality and pseudonyms are not counted as privacy mechanisms
        return sum(len({m for m in vals(k, 'P2', 'mechanisms') if m not in ('encryption-in-transit-only', 'pseudonyms-anonymity')
                        and not (m.startswith('other:') and re.search(r'data locality|instead of raw data|abstract only|named only', m, re.I))}) >= 2 for k in P)
    if key == 'sec_edpb':
        return sum(one(k, 'S5', 'edpb') is True for k in SEC)
    if pre == 'claimed':
        return sum(tag() in vals(k, 'P5', 'claimed') for k in P)
    if pre == 'tested':                    # tested among those that claim it
        return sum(tag() in vals(k, 'P5', 'claimed') and tag() in vals(k, 'P5', 'tested') for k in P)
    if pre == 'chk':
        return sum(tag() in vals(k, 'P4', 'checked') for k in P)
    if pre == 'role':
        return sum(tag() in vals(k, 'P3', 'roles') for k in P)
    if pre in ('en', 'set'):
        return sum(tag() in vals(k, 'P1', {'en': 'enablers', 'set': 'settings'}[pre]) for k in P)
    if pre == 'mech':
        return sum(tag() in vals(k, 'P2', 'mechanisms') for k in P)
    if pre == 'ledger':
        return sum(tag() in vals(k, 'P3', 'ledger') for k in P)
    if pre == 'pdchain':
        return sum(one(k, 'P7', 'personal_data_on_chain') == rest for k in P)
    if pre == 'sees':
        return sum(one(k, 'P4', 'checker_sees_update') == rest for k in P)
    if key == 'net_only':                  # the design's own cost over a link (a baseline alone does not count)
        return sum(one(k, 'P1', 'network_measured') == 'yes' and one(k, 'P1', 'network_measured_own') is not False
                   and one(k, 'P1', 'device_measured') != 'yes' for k in P)
    if key in ('hk_hidden', 'hk_noised'):
        return sum(kept_from_aggregator(k) == key[3:] for k in P)
    if key == 'hk_seen':
        return sum(kept_from_aggregator(k) == '' for k in P)
    if pre == 'cc':
        c, _, v = rest.partition('_')
        return sum(what_checked(k) == c and (not v or one(k, 'P4', 'checker_sees_update') == v) for k in P)
    if key == 'zk_stated_update':
        return sum(ZK_RELATION.get(k) in ('bound', 'training') for k in P)
    if key == 'yt_attack':
        return sum(learning_attack(k) for k in P)
    if key in ('test_privacy_only', 'test_other_only'):
        priv = {'inference-privacy-attack', 'malicious-server-aggregator', 'collusion', 'other: data leakage'}
        f = (lambda k: bool(set(vals(k, 'P5', 'tested')) & priv)) if key == 'test_privacy_only' else \
            (lambda k: bool(vals(k, 'P5', 'tested')) and not set(vals(k, 'P5', 'tested')) & priv)
        return sum(not learning_attack(k) and f(k) for k in P)
    if key == 'onchain_a':
        return sum(holds_a(k) for k in P)
    if key == 'onchain_b':
        return sum(not holds_a(k) for k in P)
    raise KeyError(key)


def check_fig_numbers():
    s = json.loads(STATS.read_text(encoding='utf-8'))
    src = (ROOT / 'scripts' / 'paper_ppml' / 'figures.py').read_text(encoding='utf-8')
    defs = [(m.group(1), m.start()) for m in re.finditer(r'(?m)^def (\w+)\(', src)]
    for i, (name, start) in enumerate(defs):
        if name not in ('taxonomy',):          # the only diagram with counts (architecture and spine carry none)
            continue
        body = src[start:defs[i + 1][1] if i + 1 < len(defs) else len(src)]
        for key in sorted(set(re.findall(r"g\('(\w+)'\)", body))):
            report(f'Fig {name}', key, s.get(key), expected(key))


# ---- Table and figure: what each primary study does (the counterpart of the survey coverage) ---------------------
PRIM_COLS = ['SQ1 Fabric (C1)', 'SQ2 Privacy (C2)', 'SQ3 Verification', 'SQ3 ZKPs', 'SQ3 Blockchain (C3)', 'SQ4 Poisoning (C4a)',
             'SQ4 Malicious or fake (C4b)', 'SQ4 Free riding (C4c)', 'SQ5 Regulation (C5)']
PRIM_HEADS = ['SQ1 Cost on devices', 'SQ2 No party sees an update', 'SQ3 Updates checked (not by ZKP)', 'SQ3 ZKP about the update',
              'SQ3 Ledger checks the updates', 'SQ4 Poisoning tested', 'SQ4 Malicious or fake tested', 'SQ4 Free riding tested',
              'SQ5 No personal records, or erasure']   # the column labels of Table V: what each grades (V63)


def prim_grades(k):
    """recomputed from the sheets by the grades that the note of the spine table states"""
    cl, te = threats(k, 'claimed'), threats(k, 'tested')
    c = conditions(k)
    nd = NOT_DESCRIBED.get(k, set())

    def thr(i, tags, also=False):
        if c[i]:
            return 'Yes' if (te & tags) - nd else 'Yes\u2020'
        return 'Partial' if (cl & tags) or also else 'No'
    zk = one(k, 'P4', 'zk_used') is True
    law = any(DP_LAW.search(x) for x in vals(k, 'P7', 'laws'))
    protects = 'updates' in vals(k, 'P2', 'protects') and bool(used_mech(k))
    own = one(k, 'P1', 'network_measured') == 'yes' and one(k, 'P1', 'network_measured_own') is not False
    checked = [x for x in vals(k, 'P4', 'checked') if x != 'none']
    return ['Yes' if c[0] else ('Partial' if own else 'No'),
            'Yes' if c[1] else ('Partial' if protects else 'No'),
            'Yes' if verification(k) else ('Partial' if checked else 'No'),
            'Yes' if zk and ZK_RELATION.get(k) in ('bound', 'training') else ('Partial' if zk else 'No'),
            'Yes' if c[2] else ('Partial' if ledger_checks_agg(k) or ledger_other(k) else 'No'),
            thr(3, {'poisoning', 'backdoor'}),
            thr(4, {'byzantine-malicious', 'sybil-fake'}, 'identity-membership' in vals(k, 'P4', 'checked')),
            thr(5, {'free-riding'}),
            'Yes' if c[6] else ('Partial' if law or one(k, 'P7', 'erasure') == 'mentioned' else 'No')]


def check_prim_cover():
    """Table IV: the grades only (from V58 it carries no count; the conditions are checked with the gap tables)"""
    head, rows = table('prim_cover')
    report('prim_cover', 'columns', head[1:], PRIM_HEADS)
    got, yes = set(), [0] * len(PRIM_COLS)
    for r in rows[:-1]:
        k = cell(r[0])[1].pop()
        got.add(k)
        g = prim_grades(k)
        report('prim_cover', k, r[1:], g)
        yes = [y + v.startswith('Yes') for y, v in zip(yes, g)]
    report('prim_cover', 'studies listed', got, set(PRIM))
    report('prim_cover', 'Yes row', [int(x) for x in rows[-1][1:]], yes)


def check_fig_prim_coverage():
    d = fig('prim_coverage')
    refs = json.loads((ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json').read_text(encoding='utf-8'))
    base = {k: f"{refs.get(k, {}).get('first_author_surname', k)} {YEAR[k]}" for k in PRIM}
    twice = {v for v in base.values() if list(base.values()).count(v) > 1}
    name = {(base[k] if base[k] not in twice else f"{re.split(r',| and | et al\.', refs[k]['ieee'])[0].strip()} {YEAR[k]}"): k for k in PRIM}
    report('Fig prim_coverage', 'columns', d['columns'], [h.split(' ', 1)[1] for h in PRIM_HEADS])
    report('Fig prim_coverage', 'distinct labels', len(name), len(PRIM))
    report('Fig prim_coverage', 'studies shown', len(d['rows']), len(PRIM))
    for lab, marks in d['rows']:
        k = name.get(lab)
        if k is None:
            PROBLEMS.append(f'Fig prim_coverage · unknown row {lab!r}')
            continue
        report('Fig prim_coverage', lab, marks, [('Yes' if g.startswith('Yes') else g) for g in prim_grades(k)])


if __name__ == '__main__':
    for f in (check_years, check_angles, check_zk, check_surveys, check_fabric, check_privacy, check_ledger, check_threats,
              check_checks, check_gap, check_qa, check_fig_threats, check_fig_trends, check_fig_survey_coverage, check_fig_numbers,
              check_prim_cover, check_fig_prim_coverage):
        before = len(PROBLEMS)
        try:
            f()
        except Exception as e:                                          # a table that cannot be read is a problem too
            PROBLEMS.append(f'{f.__name__}: could not check ({type(e).__name__}: {e})')
        print(f"{f.__name__[6:]:12} {'ok' if len(PROBLEMS) == before else str(len(PROBLEMS) - before) + ' difference(s)'}")
    print(f'\n{len(PROBLEMS)} difference(s)')
    for p in PROBLEMS:
        print('  ', p)
