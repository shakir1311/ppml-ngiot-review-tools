#!/usr/bin/env python3
"""Check the claims that the parts of the PPML review state in words rather than as computed numbers ("tested by none",
"about half", "one design", "the most frequent", a named list of studies), against the extraction records.

Each claim names the part and the words it guards, and a test on the computed statistics (build/stats.json), the citation
lists (build/cites.json) or the evidence sheets. A failed claim means the text must be rewritten, not the test relaxed.
Run after data.py; build.py runs it and refuses to build while a claim fails.

Usage: python3 scripts/paper_ppml/check_claims.py
"""
import csv, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import thematic as T                                          # the quality appraisal scores (QA1–QA6)

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
B = P / 'build'
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
QA_CONS = json.loads((ROOT / 'search-ppml' / 'evidence' / 'QA-CONSISTENCY-2026-10-05.json').read_text(encoding='utf-8'))   # QA6
TESTABLE = {'poisoning', 'backdoor', 'byzantine-malicious', 'sybil-fake', 'free-riding', 'inference-privacy-attack', 'collusion',
            'malicious-server-aggregator'}


def load():
    s = json.loads((B / 'stats.json').read_text())
    c = json.loads((B / 'cites.json').read_text())
    fin = list(csv.DictReader(open(ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')))
    sh = {}
    for r in fin:
        f = SHEETS / f"{r['corpus_id']}.json"
        if f.exists():
            sh[r['corpus_id']] = json.loads(f.read_text(encoding='utf-8'))
    return s, c, fin, sh


def val(sh, key, field):
    return ((sh.get('answers', {}).get(key, {}) or {}).get('values', {}) or {}).get(field)


def lst(sh, key, field):
    v = val(sh, key, field)
    return v if isinstance(v, list) else ([v] if v not in (None, '') else [])


def group(part, heading):
    """The study ids listed under a group heading of a part, up to the next group or section heading."""
    t = (P / 'parts' / part).read_text(encoding='utf-8')
    i = t.index(heading)
    rest = t[i + len(heading):]
    end = re.search(r'(?m)^(\*[^*\n]+\*\s+\w+ (?:designs|surveys)\b|#)', rest)
    return re.findall(r'\{\{STUDY:(\w+)\}\}', rest[:end.start()] if end else rest)


def non_increasing(s, keys):
    return all(s[a] >= s[b] for a, b in zip(keys, keys[1:]))


def claims(s, c, fin, sh):
    prim = {k: v for k, v in sh.items() if v.get('kind') == 'primary'}
    sec = {k: v for k, v in sh.items() if v.get('kind') == 'secondary'}
    both_vp = sorted(k for k, x in sec.items() if val(x, 'S4', 'verification') == 'subject' and val(x, 'S4', 'poisoning') == 'subject')
    all5 = sorted(k for k, x in sec.items() if all(val(x, 'S2', f) == 'subject' for f in ('fabric', 'privacy', 'trust', 'attacks', 'regulation')))
    gap = {}
    for k, x in prim.items():
        tested = set(lst(x, 'P5', 'tested'))
        roles = set(lst(x, 'P3', 'roles'))
        gap[k] = (T.hides_updates_from_aggregator(x) and val(x, 'P4', 'checker_sees_update') in ('no', 'no-check'),
                  bool({'poisoning', 'backdoor'} & tested), bool({'byzantine-malicious', 'sybil-fake'} & tested),
                  bool({'update-verification', 'proof-verification'} & roles) and val(x, 'P7', 'personal_data_on_chain') == 'no',
                  val(x, 'P1', 'device_measured') == 'yes')
    met = lambda *i: sorted(k for k, g in gap.items() if all(g[j] for j in i))
    erasure = lambda v: sorted(k for k, x in prim.items() if val(x, 'P7', 'erasure') == v)
    edpb_primary = sorted(k for k, x in prim.items() if any('edpb' in str(l).lower() for l in lst(x, 'P7', 'laws')))
    sees = lambda ids: sum(val(prim[i], 'P4', 'checker_sees_update') in ('yes', 'partly') for i in ids if i in prim)
    g2 = group('06-approaches.md', '*Checks by miners, validators, committees or auditors.*')
    ones = sorted(k[4:] for k, v in s.items() if k.startswith('set_') and v == 1)
    zk = [x for x in prim.values() if val(x, 'P4', 'zk_used') is True]
    of_update = sum(1 for x in zk if {'training', 'bounded', 'similarity'} & set(lst(x, 'P4', 'zk_shows')))
    yrs = {k: v for k, v in s.items() if re.fullmatch(r'y20\d\d', k)}
    cited = {r['n']: r['cited'] for r in csv.DictReader(open(ROOT / 'search-ppml' / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8'))}
    old_low = sorted(r['corpus_id'] for r in fin if r['kind'] == 'secondary' and int(r['year']) < 2024 and int(cited.get(r['n']) or 0) < 100)
    return [
        ('every included study has an evidence sheet', len(sh) == len(fin), f'{len(sh)} of {len(fin)}'),
        ('04 "most frequent settings are the general IoT and vehicular networks, followed by industrial and medical IoT, smart grids"',
         non_increasing(s, ['set_iot_general', 'set_iov_vehicular', 'set_iiot', 'set_iomt_healthcare', 'set_smart_grid_energy']), ''),
        ('04 "smart cities or homes (N), and single studies in communication-network, maritime, supply-chain and space–air–ground settings"',
         ones == ['communication_network', 'maritime', 'supply_chain', 'uav_space'] and s['set_smart_city_home'] > 1, f'settings with one study: {ones}'),
        ('04/06-B "Edge computing is the most frequent enabler, followed by the cloud, 5G or 6G and MEC"',
         non_increasing(s, ['en_edge', 'en_cloud', 'en_5g_6g', 'en_mec']) or non_increasing(s, ['en_edge', 'en_5g_6g', 'en_cloud', 'en_mec']),
         f"edge {s['en_edge']}, cloud {s['en_cloud']}, 5G/6G {s['en_5g_6g']}, MEC {s['en_mec']}"),
        ('04 order "followed by 5G or 6G networks, the cloud and MEC"', s['en_5g_6g'] >= s['en_cloud'] >= s['en_mec'], f"5G/6G {s['en_5g_6g']}, cloud {s['en_cloud']}"),
        ('04 "Blockchain is the most frequent, followed by malicious or fake, poisoning, verification and ZKPs"',
         non_increasing(s, ['angle_blockchain', 'angle_malicious_or_fake_participants', 'angle_poisoning', 'angle_verification', 'angle_zero_knowledge_proofs']), ''),
        ('04 "2026 ... more than in any earlier year"', s['y2026'] > max(v for k, v in yrs.items() if k != 'y2026'), str(yrs)),
        ('04 "the secondary studies published before 2024 are each cited at least 100 times"', not old_low, f'below 100 or unknown: {old_low}'),
        ('04-C "Most primary studies evaluate on named data sets and compare with named baselines"',
         s['qa_qa1_yes'] > s['primary'] / 2 and s['qa_qa2_yes'] > s['primary'] / 2, f"QA1 {s['qa_qa1_yes']}, QA2 {s['qa_qa2_yes']} of {s['primary']}"),
        ('04-C "None, however, tests every threat it claims"', s.get('qa_qa3_yes', 0) == 0, f"QA3 yes {s.get('qa_qa3_yes')}"),
        ('06-A "one scores the contributions for its consensus without saying who scores them [r0284]"',
         'not described' in str(lst(prim['r0284'], 'P4', 'checker')) and 'PoS' in lst(prim['r0284'], 'P3', 'consensus'), ''),
        ('06-A "Fourteen designs … in nine of the fourteen [committee designs] the checkers see the updates, or a noised version"', len(g2) == 14 and sees(g2) == 9,
         f'group of {len(g2)}, {sees(g2)} see'),
        ('06-B "in two of them only for a baseline or for posting proofs to a test chain" (network measured: N008, N020, n3378, r0159; the two: N020, n3378)',
         c['network_measured'] == ['N008', 'N020', 'n3378', 'r0159'], f"now {c['network_measured']}"),
        ('06-C "ZKPs are the most frequent, followed by HE and DP, secret sharing, pseudonyms, SMPC, masking, LDP, TEEs"',
         non_increasing(s, ['mech_zkp', 'mech_he', 'mech_dp', 'mech_secret_sharing', 'mech_pseudonyms_anonymity', 'mech_smpc',
                            'mech_masking_secure_aggregation', 'mech_ldp', 'mech_tee']),
         ', '.join(f"{k[5:]} {s[k]}" for k in ('mech_zkp', 'mech_he', 'mech_dp', 'mech_pseudonyms_anonymity', 'mech_secret_sharing',
                                                'mech_masking_secure_aggregation', 'mech_smpc', 'mech_ldp', 'mech_tee'))),
        ('06-C "most often hidden from the ledger nodes, from other participants and from external attackers"',
         non_increasing(s, ['hid_ledger_nodes', 'hid_other_participants', 'hid_external_attacker']) and s['hid_external_attacker'] >= s['hid_server_aggregator'] >= s['hid_public'], ''),
        ('06-D "Consortium or permissioned ledgers dominate"', s['ledger_consortium_permissioned'] > s['primary'] / 2,
         f"{s['ledger_consortium_permissioned']} of {s['primary']}"),
        ('06-D "most often records and audits, manages identities, handles incentives, replaces the server"',
         non_increasing(s, ['role_record_audit', 'role_identity_access', 'role_incentive_reputation', 'role_replaces_server']), ''),
        ('06-D "Identity most frequent check, then contribution, accuracy, anomaly, aggregation and similarity (each), norm bounds and correct training (each)"',
         s['chk_identity_membership'] >= s['chk_contribution_reputation'] >= s['chk_test_accuracy_quality'] >= s['chk_anomaly_detection']
         >= s['chk_correct_aggregation'] == s['chk_similarity_distance'] >= s['chk_norm_bound'] == s['chk_correct_training'],
         ', '.join(f"{k[4:]} {s[k]}" for k in ('chk_identity_membership', 'chk_contribution_reputation', 'chk_test_accuracy_quality',
                                               'chk_correct_aggregation', 'chk_similarity_distance', 'chk_anomaly_detection', 'chk_norm_bound', 'chk_correct_training'))),
        ('06-D/abstract "No study proves that an update is similar ... none proves similarity"', s['zkshows_similarity'] == 0, ''),
        ('06-D "in under half of the studies verify proofs"', s['role_proof_verification'] < s['primary'] / 2,
         f"{s['role_proof_verification']} of {s['primary']}"),
        ('07-A "Most [ZK designs] prove identities, inferences or the aggregation rather than properties of the updates"',
         of_update < len(zk) / 2, f'{of_update} of {len(zk)} prove a property of the update'),
        ('abstract/07-B "Ledgers record the training more often than they check it"',
         s['role_record_audit'] > max(s['role_update_verification'], s['role_proof_verification']), ''),
        ('06-E "denial of service ... tested by none"', s['tested_dos_ddos'] == 0, ''),
        ('06-E "the single point of failure ... tested by none"', s['tested_single_point_of_failure'] == 0, ''),
        ('06-E/SQ4 "about half of the claims of poisoning are tested"', 0.4 <= s['tested_poisoning'] / s['claimed_poisoning'] <= 0.6,
         f"{s['tested_poisoning']} of {s['claimed_poisoning']}"),
        ('SQ4/07-B "Fake participants, free riding, collusion, single point of failure claimed far more often than tested"',
         all(s[f'claimed_{t}'] >= 2 * s[f'tested_{t}'] + 2 for t in ('sybil_fake', 'free_riding', 'collusion', 'single_point_of_failure')), ''),
        ('06-E "Poisoning and malicious participants are the threats most often claimed" (of the learning attacks)',
         min(s['claimed_poisoning'], s['claimed_byzantine_malicious']) >= max(s['claimed_sybil_fake'], s['claimed_free_riding'], s['claimed_backdoor']), ''),
        ('06-F "None discusses the EDPB guidelines on blockchain" (primary)', not edpb_primary, str(edpb_primary)),
        ('05-B "none names the EDPB guidelines on blockchain" (surveys)', s['sec_edpb'] == 0, ''),
        ('I-C/05-B/TK-V "The four surveys that treat both verification and poisoning as subjects leave regulation in the background" [S016, S026, p0013, p0617]',
         both_vp == ['S016', 'S026', 'p0013', 'p0617'] and all(val(sec[k], 'S2', 'regulation') != 'subject' for k in both_vp), str(both_vp)),
        ('I-C/TK-V "none treats all five layers together with the verification of updates and poisoning"',
         not [k for k in all5 if val(sec[k], 'S4', 'verification') == 'subject' and val(sec[k], 'S4', 'poisoning') == 'subject'], ''),
        ('I-C/05-B "the two surveys that treat all five layers as subjects only mention verification [p0408, p0435]"',
         all5 == ['p0408', 'p0435'] and all(val(sec[k], 'S4', 'verification') == 'mentioned' for k in all5), str(all5)),
        ('06-F/SQ5/TK-VI "The ledgers of N designs can delete data [N020, N019, r0284] … all to limit their growth … none presents it as erasure of personal data"',
         erasure('addressed') == ['N019', 'N020', 'r0284'] and all(re.search(r'storage|growth', prim[k]['answers']['P7']['answer']) for k in erasure('addressed')),
         str(erasure('addressed'))),
        ('06-F "and two mention it [N007; p4875]"', erasure('mentioned') == ['N007', 'p4875'], str(erasure('mentioned'))),
        ('08-B "The one ledger that verifies a proof while holding no personal data verifies the aggregation [n3378]"', met(3) == ['n3378'], str(met(3))),
        ('TK-IV "Most primary studies evaluate on named data sets against named baselines"',
         2 * s['qa_qa1_yes'] > s['primary'] and 2 * s['qa_qa2_yes'] > s['primary'], f"{s['qa_qa1_yes']}, {s['qa_qa2_yes']} of {s['primary']}"),
        ('TK-IV "few report a cost of their own design measured on devices or links, few give a link to their code"',
         4 * s['device_measured'] <= s['primary'] and 4 * s['code_yes'] <= s['primary'], f"{s['device_measured']}, {s['code_yes']}"),
        # 5G made visible (V41): the one study that tests on devices connected over 5G
        ('06-B "one more connects some of its test devices to a 5G router and reports no measurement of the link" [r0043]',
         '5G-6G' in lst(prim['r0043'], 'P1', 'enablers') and val(prim['r0043'], 'P1', 'network_measured') == 'no'
         and any('connected to a 5G router' in e.get('quote', '') for e in prim['r0043']['answers']['P1'].get('evidence', [])), ''),
        ('06-B/07-A "only one reports measuring its design on (edge) devices connected over 5G" [N008]',
         sorted(k for k, x in prim.items() if '5G-6G' in lst(x, 'P1', 'enablers') and val(x, 'P1', 'network_measured') == 'yes') == ['N008']
         and any('connected with 5G' in e.get('quote', '') for e in prim['N008']['answers']['P1'].get('evidence', [])),
         str(sorted(k for k, x in prim.items() if '5G-6G' in lst(x, 'P1', 'enablers') and val(x, 'P1', 'network_measured') == 'yes'))),
        ('06-B "while only N of 37 name 5G or 6G networks" is a minority', 2 * s['en_5g_6g'] < s['primary'], str(s['en_5g_6g'])),
        ('TK-V "Every survey treats the privacy plane as a subject"', s['layer_privacy_subject'] == s['secondary'], str(s['layer_privacy_subject'])),
        ('V-B "Every survey treats the privacy plane and attacks as subjects"',
         s['layer_privacy_subject'] == s['secondary'] and s['layer_attacks_subject'] == s['secondary'],
         f"{s['layer_privacy_subject']}, {s['layer_attacks_subject']}"),
        ('V-B "the trust plane is a subject exactly where blockchain or verification is"', s['sec_trust_follows_angles'] == 1,
         str(s['sec_trust_follows_angles'])),
        ('V-B "Most of the others name no databases, period or number of studies"', 2 * s['sec_no_db_period_count'] > s['sec_qs1_below'],
         f"{s['sec_no_db_period_count']} of {s['sec_qs1_below']}"),
        ('V-B "free riding is a subject in only N" (the fewest of the three threats)',
         s['sang_free_riding_subject'] < min(s['sang_poisoning_subject'], s['sang_malicious_fake_subject']), str(s['sang_free_riding_subject'])),
        ('TK-VI "Most designs combine mechanisms"', 2 * s['mech_two_or_more'] > s['primary'], str(s['mech_two_or_more'])),
        ('TK-VI/VII "The ledgers, mostly permissioned" / "permissioned ledgers have become the norm"',
         2 * s['ledger_consortium_permissioned'] > s['primary'], str(s['ledger_consortium_permissioned'])),
        ('TK-VI "record the training more often than they check it"',
         s['role_record_audit'] > max(s['role_update_verification'], s['role_proof_verification']), ''),
        ('TK-VI "Most studies run no attack on the learning"', 2 * s['no_attack_tested'] > s['primary'], str(s['no_attack_tested'])),
        ('07-A "Fake participants, free riding and collusion are claimed far more often than tests of them are reported"',
         s['claimed_sybil_fake'] >= 2 * s['tested_sybil_fake'] and s['claimed_free_riding'] >= 2 * s['tested_free_riding'], ''),
        ('07-A / TK-VII "Most of them ... prove something other than a property of the updates or their training"',
         2 * s['zk_not_update'] > s['zk_used'], f"{s['zk_not_update']} of {s['zk_used']}"),
        # the sensitivity check (04-C) and the sentences that report it (abstract, TK-IV, 08-B, 10)
        # the re-check (04-C) on the primary studies that run at least one attack they claim (QA3 Yes or Partial), and the
        # sentences that report it (abstract, TK-IV, 07-A, 08-B, 10, 11)
        ('04-C "one of them measures a cost on device-class hardware" (re-check group)', s['sens_device'] == 1, str(s['sens_device'])),
        ('03-C "none was contradicted" (spot check of the extraction)', s['sc_disagree'] == 0, str(s['sc_disagree'])),
        ('06-F/TK-VI/VII-B/XI "Only … name a data-protection law, all of them the GDPR"',
         all(any('GDPR' in str(l) or 'General Data Protection' in str(l) for l in lst(x, 'P7', 'laws'))
             for x in prim.values() if any(T.DP_LAW.search(str(l)) for l in lst(x, 'P7', 'laws'))), ''),
        ('06-D/VII-A/XI "only N designs check what an update contains while no checking party sees it" [N004, N015, n1640]',
         c['cc_content_no'] == ['N004', 'N015', 'n1640'], str(c['cc_content_no'])),
        ('06-D "one tests each model by encrypted inference under SMPC against a threshold [N004], and two prove a bound … verified on the ledger [N015; n1640]"',
         'test-accuracy-quality' in lst(prim['N004'], 'P4', 'checked') and 'SMPC' in lst(prim['N004'], 'P2', 'mechanisms')
         and all(T.ZK_RELATION[k] == 'bound' and val(prim[k], 'P4', 'zk_on_chain') == 'yes' for k in ('N015', 'n1640')), ''),
        ('06-D/08-B "A third proof of a bound is verified on the ledger, but the design discloses the update\'s norm … sees the update in part" [n3348]',
         T.ZK_RELATION['n3348'] == 'bound' and val(prim['n3348'], 'P4', 'zk_on_chain') == 'yes'
         and val(prim['n3348'], 'P4', 'checker_sees_update') == 'partly' and 'disclosed' in prim['n3348']['answers']['P2']['answer']
         and 'sees only the norm' in prim['n3348']['answers']['P4']['answer'], ''),
        ('06-D/VII-A "Two of the three bound proofs keep the update from every checking party [N015; n1640] … the only one of the three that reports a test of an attack on the learning [n3348]"',
         sorted(k for k, r in T.ZK_RELATION.items() if r == 'bound') == ['N015', 'n1640', 'n3348'] and s['zkrel_bound'] == 3
         and [k for k in ('N015', 'n1640', 'n3348') if val(prim[k], 'P4', 'checker_sees_update') == 'no'] == ['N015', 'n1640']
         and [k for k in ('N015', 'n1640', 'n3348') if T.attacks_learning(prim[k])] == ['n3348']
         and s['zk_bound_hidden'] == 2 and s['zk_bound_tested'] == 1, ''),
        ('VII-A/TK-VII "none reports proving costs measured on a device" (bound designs) and "neither of which reports an attack test"',
         not any(val(prim[k], 'P1', 'device_measured') == 'yes' for k in ('N015', 'n1640', 'n3348'))
         and not any(T.attacks_learning(prim[k]) for k in ('N015', 'n1640')), ''),
        ('VII-A "{{N:cc_content_no_tested}} of these reports a test of an attack on the learning" (one: N004)',
         [k for k in c['cc_content_no'] if T.attacks_learning(prim[k])] == ['N004'] and s['cc_content_no_tested'] == 1, ''),
        ('06-D "Of the other four, one proves the evaluation … [n2405], one the classification … [n0414], and two say that their proofs show valid training or an update that meets pre-defined constraints, without stating the circuit or the relation [n1749; n2723]"',
         T.ZK_RELATION['n2405'] == 'commitment' and T.ZK_RELATION['n0414'] == 'inference'
         and T.ZK_RELATION['n1749'] == T.ZK_RELATION['n2723'] == 'unspecified-update' and s['zk_claimed_update'] == 8
         and all('training' in lst(prim[k], 'P4', 'zk_shows') for k in ('n1749', 'n2723'))
         and 'No circuit' in prim['n1749']['answers']['P4']['answer'] and 'circuit and trusted set-up are not stated' in prim['n2723']['answers']['P4']['answer'], ''),
        ('06-D/09-B "The one proof of training whose cost is reported on device-class boards … its server sees the updates" [n3910]',
         T.ZK_RELATION['n3910'] == 'training' and val(prim['n3910'], 'P1', 'device_measured') == 'yes'
         and val(prim['n3910'], 'P4', 'checker_sees_update') == 'yes' and s['zk_device_proving'] == 1, ''),
        ('06-D "None of the included designs proves that an update is similar to the others or to a reference"',
         s['zkshows_similarity'] == 0 and 'similarity' not in T.ZK_RELATION.values(), ''),
        ('06-D "the ledger verifies a proof that the aggregation is correct, not the updates" [O108, n3378]',
         c['ledger_checks_aggregation'] == ['O108', 'n3378'] and s['ledger_checks_aggregation'] == 2, str(c['ledger_checks_aggregation'])),
        ('06-E "Three designs claim to tolerate Byzantine validators or committee members"',
         s['claimed_byz_consensus'] == 3 == len(T.BYZ_CONSENSUS), ''),
        ('06-E "Six of the twelve designs that report a test of poisoning run label flipping [N004; N013; n3855; N018; n0414; n2405]"',
         s['tested_learning_poisoning'] == 12 and all('poisoning' in T.threats_of(k, prim[k], 'tested')
                                                      and re.search(r'label|Flip', prim[k]['answers']['P5']['answer'])
                                                      for k in ('N004', 'N013', 'n3855', 'N018', 'n0414', 'n2405')), ''),
        ('06-F "all of them the GDPR, four also the Health Insurance Portability and Accountability Act and one the California Consumer Privacy Act"',
         s['gdpr_named'] == s['laws_named'] and sorted(k for k, x in prim.items() if any('CCPA' in str(y) for y in lst(x, 'P7', 'laws'))) == ['N012']
         and sorted(k for k, x in prim.items() if any('HIPAA' in str(y) for y in lst(x, 'P7', 'laws'))) == ['N004', 'n1749', 'n2723', 'r0202'], ''),
        ('06-E "Three designs report the results of attacks whose set-up they do not describe [n2912, r0323, n3102], and a fourth takes its Sybil and collusion results from its Byzantine simulations [n3348]"',
         len(T.ATTACK_NOT_DESCRIBED) == 4 and T.ATTACK_NOT_DESCRIBED['n3348'] == {'sybil-fake', 'collusion'}, ''),
        ('06-E/VII-A "no study reports a test of either" (denial of service, single point of failure)',
         not any(set(lst(x, 'P5', 'tested')) & {'dos-ddos', 'single-point-of-failure'} for x in prim.values()), ''),
        ('06-F "Five designs show that personal data reach their ledger …; one states that no personal data reach its ledger [n3378]"',
         s['pd_yes'] == 5 and s['pd_no'] == 1 and val(prim['n3378'], 'P7', 'personal_data_on_chain') == 'no', ''),
        ('06-F "The three designs that verify bound proofs on the ledger … each also holds identifiers and keys" [N015, n1640, n3348]',
         all('identities-keys' in lst(prim[k], 'P3', 'on_chain') for k in ('N015', 'n1640', 'n3348')), ''),
        ('06-F/answer SQ5 "No primary study discusses a data-protection law together with erasure or with whether personal data reach its ledger"',
         not any(any(T.DP_LAW.search(str(y)) for y in lst(x, 'P7', 'laws')) and (val(x, 'P7', 'erasure') in ('addressed', 'mentioned')
                 or val(x, 'P7', 'personal_data_on_chain') in ('yes', 'no')) for x in prim.values()), ''),
        ('06-F/VII-A "C5: … because their ledgers hold no personal data and … because they can delete data from their ledgers, although they do so to limit their growth" (erasure designs all hold personal data)',
         s['gap_c5'] == s['gap_c5_nopd'] + s['gap_c5_erase'] and s['gap_c5_erase'] == s['erasure_addressed'] == 3
         and c['erasure_addressed'] == ['N019', 'N020', 'r0284'], ''),
        ('06-C "of the designs that use ZKPs as a privacy mechanism, N keep the updates from the aggregator, each by another mechanism"',
         all(set(lst(x, 'P2', 'mechanisms')) & T.CONFIDENTIALITY for x in prim.values()
             if 'ZKP' in T.mechanisms_used(x) and T.hidden_kind(x) == 'hidden'), ''),
        ('06-B "four on Raspberry Pi or Jetson Nano boards [N008; N009; n3910; r0043], one NVIDIA TX2 [r0355], one unnamed [r0159]"',
         c['device_measured'] == sorted(['N008', 'N009', 'n3910', 'r0043', 'r0355', 'r0159']), str(c['device_measured'])),
        ('08-B "The closest design meets N of them, and no design meets more" [n3348]',
         c['gap_closest'] == ['n3348'] and s['gap_at_max'] == 1, str(c['gap_closest'])),
        ('08-B "It hides the updates from the aggregator under threshold HE, verifies on its ledger a ZKP about each update, and reports tests of Byzantine participants … and of free riders" [n3348]',
         T.hidden_kind(prim['n3348']) == 'hidden' and 'HE' in lst(prim['n3348'], 'P2', 'mechanisms')
         and val(prim['n3348'], 'P4', 'zk_on_chain') == 'yes'
         and {'byzantine-malicious', 'free-riding'} <= T.threats_of('n3348', prim['n3348'], 'tested')
         and val(prim['n3348'], 'P1', 'device_measured') != 'yes' and 'simulated' in lst(prim['n3348'], 'P3', 'platform'), ''),
        ('08-B "It does not meet C2, because the design discloses each update\'s norm …" [n3348]',
         not T.gap_conditions('n3348', prim['n3348'])['C2'] and val(prim['n3348'], 'P4', 'checker_sees_update') == 'partly', ''),
        ('08-B "Next come N designs … One checks hidden updates against poisoning … ledger holds no personal records [N004]. The other three let the ledger\'s nodes or a committee check the updates and report tests of poisoning and of malicious or fake participants, while the checkers see the updates [N014; N018; N021]"',
         c['gap_next'] == ['N004', 'N014', 'N018', 'N021']
         and [col for col, v in T.gap_conditions('N004', prim['N004']).items() if v] == ['C2', 'C4a', 'C5']
         and all([col for col, v in T.gap_conditions(k, prim[k]).items() if v] == ['C3', 'C4a', 'C4b']
                 and val(prim[k], 'P4', 'checker_sees_update') in ('yes', 'partly') for k in ('N014', 'N018', 'N021')), str(c['gap_next'])),
        ('08-B "Only one design keeps the updates from every party that checks or aggregates them while its ledger checks them … reports no attack test and holds identifiers" [N015]',
         sorted(set(c['gap_c2']) & set(c['gap_c3'])) == ['N015'] and not lst(prim['N015'], 'P5', 'tested')
         and 'identities-keys' in lst(prim['N015'], 'P3', 'on_chain'), ''),
        ('08-B "Only one ledger both checks the updates and holds no personal records … [r0230]; two more ledgers that hold no personal records verify a proof of the aggregation" [O108, n3378]',
         sorted(set(c['gap_c3']) & set(c['no_pd_on_ledger'])) == ['r0230']
         and all(k in c['no_pd_on_ledger'] for k in ('O108', 'n3378')), ''),
        ('08-B "Further designs report tests … while the checker sees the updates [n2405], or report them without describing the attacks [n2912; n3102], one of them without saying whether its validators see the updates [n3102]"',
         T.threats_of('n2405', prim['n2405'], 'tested') & {'poisoning', 'byzantine-malicious', 'sybil-fake'}
         and val(prim['n2405'], 'P4', 'checker_sees_update') in ('yes', 'partly')
         and all('poisoning' in T.ATTACK_NOT_DESCRIBED.get(k, set()) for k in ('n2912', 'n3102'))
         and val(prim['n3102'], 'P4', 'checker_sees_update') == 'unclear', ''),
        ('08-B "The designs that report costs measured on device-class hardware report no test of poisoning, Byzantine, Sybil or free-riding attacks"',
         not any(set(T.PHD + ['backdoor']) & T.threats_of(k, prim[k], 'tested') for k in c['device_measured']), ''),
        ('08-C "one included design meets C2 and C3 together, and none meets all three" (C2, C3, C5)',
         len(set(c['gap_c2']) & set(c['gap_c3'])) == 1 and not (set(c['gap_c2']) & set(c['gap_c3']) & set(c['gap_c5'])), ''),
        ('08-C "none of the designs whose checkers do not see the updates reports a cost measured on device-class hardware"',
         not any(val(x, 'P4', 'checker_sees_update') == 'no' and val(x, 'P1', 'device_measured') == 'yes' for x in prim.values()), ''),
        ('08-C "one included design compares its costs with one such scheme, RoFL, whose optimisation its range proofs use" [N015]',
         'RoFL' in prim['N015']['answers']['P6']['answer'] and 'RoFL' in prim['N015']['answers']['P4']['answer'], ''),
        ('09-B "A lower bound on the same norm would reject the zero updates of free riders; one design tests free riders that submit random noise or zero gradients" [n3348]',
         'free-riding' in T.threats_of('n3348', prim['n3348'], 'tested')
         and any('zero gradients' in (e.get('quote') or '') for e in prim['n3348']['answers']['P5'].get('evidence', [])), ''),
        ('IV-B "The surveys thus treat the ledger and poisoning far more often than the means of checking the learning, and ZKPs and free riding least of all"',
         min(s['ang_sec_blockchain'], s['ang_sec_poisoning']) > max(s['ang_sec_verification'], s['ang_sec_zero_knowledge'])
         and s['ang_sec_zero_knowledge'] == s['ang_sec_free'] == min(s[f'ang_sec_{x}'] for x in ('blockchain', 'poisoning', 'malicious', 'verification', 'zero_knowledge', 'free')), ''),
        ('I-C/V-B "the two that treat all five layers as subjects make neither verification nor any of the three threats a subject" [p0408, p0435]',
         all(val(sh[k], 'S4', f) != 'subject' for k in ('p0408', 'p0435') for f in ('verification', 'poisoning', 'malicious_fake', 'free_riding'))
         and sorted(k for k, x in sh.items() if x.get('kind') == 'secondary' and all(val(x, 'S2', l) == 'subject' for l in ('fabric', 'privacy', 'trust', 'attacks', 'regulation'))) == ['p0408', 'p0435'], ''),
        ('I-C/V-B "The four that treat both verification and poisoning as subjects leave regulation in the background" [S016, S026, p0013, p0617]',
         sorted(k for k, x in sh.items() if x.get('kind') == 'secondary' and val(x, 'S4', 'verification') == 'subject' and val(x, 'S4', 'poisoning') == 'subject')
         == ['S016', 'S026', 'p0013', 'p0617'] and all(val(sh[k], 'S2', 'regulation') != 'subject' for k in ('S016', 'S026', 'p0013', 'p0617')), ''),
        ('I-C "the eight surveys of blockchain-based FL"',
         sorted(group('05-surveys.md', '*Surveys of blockchain-based FL.*')) == sorted(['S005', 'S007', 'S014', 'S016', 'S018', 'p0013', 'S021', 'n3837']), ''),
        ('VI head / VI-A groups: n0763 is not in the ZKP group, n2405 is',
         'n0763' not in group('06-approaches.md', '*Zero-knowledge proofs presented as proofs about the update or the training.*')
         and 'n2405' in group('06-approaches.md', '*Zero-knowledge proofs presented as proofs about the update or the training.*'), ''),
        ('06-B "A cost over a network link is reported by N studies, in one of them only for a baseline" [N020]',
         sorted(k for k, x in prim.items() if val(x, 'P1', 'network_measured') == 'yes' and val(x, 'P1', 'network_measured_own') is False) == ['N020'], ''),
        ('06-F "… because they can delete data from their ledgers … and one of them keeps its node identities on the ledger" [N020]',
         [k for k in c['erasure_addressed'] if 'identities-keys' in lst(prim[k], 'P3', 'on_chain')] == ['N020'], ''),
        ('06-E "malicious or fake participants are claimed by N studies, countered only by an identity check in M more (Section IV-B)"',
         s['claimed_mal_fake'] + s['mal_fake_identity_only'] == s['ang_prim_malicious'], ''),
        ('06-E answer "poisoning and malicious or fake participants are claimed far more often than free riding"',
         min(s['claimed_learning_poisoning'], s['claimed_mal_fake']) >= 3 * s['claimed_free_riding'], ''),
        ('07-A "Poisoning, malicious or fake participants and free riding are claimed far more often than tests of them are reported"',
         all(a >= 2 * b for a, b in ((s['claimed_learning_poisoning'], s['tested_learning_poisoning']), (s['claimed_mal_fake'], s['tested_mal_fake']),
                                     (s['claimed_free_riding'], s['tested_free_riding']))), ''),
        ('07-A "most claims of poisoning are tested …, but claims still outnumber tests for malicious or fake participants … and for free riding" (re-check group)',
         2 * s['sens_tested_poisoning'] > s['sens_claimed_poisoning'] and s['sens_claimed_mal_fake'] > s['sens_tested_mal_fake']
         and s['sens_claimed_free_riding'] > s['sens_tested_free_riding'], ''),
        ('06-D "Of the N that do not present their proofs as proofs about the update, … identity …, … the aggregation, … an inference, … other records and … a statement they do not specify" (adds up)',
         s['zkrel_identity'] + s['zkrel_aggregation'] + s['zk_inference_not_update'] + s['zkrel_other'] + s['zkrel_unspecified'] == s['zk_not_claimed_update'], ''),
        ('II-E "the evidence of the designs … largely independent": most designs are cited by no survey',
         s['ov_designs_not_cited'] > s['ov_designs_cited'] and s['ov_designs_cited'] + s['ov_designs_not_cited'] == s['primary'], ''),
    ]


def main():
    s, c, fin, sh = load()
    bad = 0
    for name, ok, note in claims(s, c, fin, sh):
        if ok is None:
            print(f'  n/a   {name} — {note}')
            continue
        bad += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}{' — ' + note if note and not ok else ''}")
    print(f'{bad} claim(s) fail')
    return bad


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
