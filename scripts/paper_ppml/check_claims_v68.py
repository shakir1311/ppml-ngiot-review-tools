#!/usr/bin/env python3
"""The claims that the V68 parts state in words rather than as computed numbers, each tested against build/stats.json,
build/cites.json or the sheets. A failed claim means the text must be rewritten, never the test relaxed.
Usage: python3 scripts/paper_ppml/check_claims_v68.py
"""
import json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
s = json.loads((B / 'stats.json').read_text(encoding='utf-8'))
c = json.loads((B / 'cites.json').read_text(encoding='utf-8'))
SH = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in (ROOT / 'search-ppml' / 'evidence' / 'sheets').glob('*.json')}
P = s['primary']
def field(k, f):
    for a in SH[k]['answers'].values():
        if f in (a.get('values') or {}): return a['values'][f]
named = [k for k in c['device_measured'] if re.search(r'Raspberry|Jetson|TX2|smartphone|Cortex|Arduino|ESP32|STM32|microcontroller', ' '.join(a['answer'] for a in SH[k]['answers'].values()), re.I)]
hw_ok = bool(named) and not any(re.search(r'microcontroller|Cortex-M|Arduino|ESP32|STM32', ' '.join(a['answer'] for a in SH[k]['answers'].values()), re.I) for k in named)
CLAIMS = [
 ('abstract/VI-B: no design meets all three conditions; one design meets two', s['gap3_all'] == 0 and s['gap3_two'] == 1),
 ('abstract (V85): most designs still rely on a named party for privacy or correctness', s['trusted_any_party'] > P / 2),
 ('abstract (V85): most also report no test against attacks on the learning', s['no_attack_tested'] > P / 2),
 ('abstract (V85): the ledgers of most designs are described as holding an item that would remain personal data', s['onchain_a'] > P / 2),
 ('VI-A (V85): few designs measure what protection costs on device-class hardware', s['where_device_class'] < P / 4),
 ('VI-A/VI takeaway (V85): most designs hide the update from the ledger nodes', s['hid_ledger_nodes'] > P / 2),
 ('VI-A (V85): most designs report no test of an attack on the learning', s['no_attack_tested'] > P / 2),
 ('VI takeaway (V85): most designs still rely on a named party', s['trusted_any_party'] > P / 2),
 ('VI-A (V85): the update is hidden from the ledger nodes in most designs and still seen by the aggregator in most', s['hid_ledger_nodes'] > P / 2 and s['hid_server_aggregator'] < P / 2),
 ('V takeaway (V85): for most designs the defence is described, not tested; most do not link code', s['no_attack_tested'] > P / 2 and s['code_yes'] < P / 2),
 ('II (V86): the privacy and fabric columns of the survey grid are nearly full, the free-riding column mostly empty, no row complete',
  s['sv_privacy_yes'] >= 0.9 * s['secondary'] and s['sv_fabric_yes'] >= 0.9 * s['secondary'] and s['sv_free_riding_no'] > s['secondary'] / 2 and s['sv_all_yes'] == 0),
 ('V-A (V86): most of the designs that test a named attack appeared in 2024 or later', s['c3_2024_on'] > s['gap3_c3'] / 2),
 ('VIII (V85): each part (condition) is met by some design', s['gap3_c1'] > 0 and s['gap3_c2'] > 0 and s['gap3_c3'] > 0),
 ('VIII (V85): a design meets two of the three conditions at most, and only one does', s['gap3_max'] == 2 and s['gap3_two'] == 1),
 ('VIII (V85): few designs measure a cost on device-class hardware; most hide updates from the ledger nodes; most rely on a named party; most report no attack test',
  s['where_device_class'] < P / 4 and s['hid_ledger_nodes'] > P / 2 and s['trusted_any_party'] > P / 2 and s['no_attack_tested'] > P / 2),
 ('II: one survey treats the four subjects and the three threats together; none treats all eight', s['sv_core_and_threats'] == 1 and s['sv_all_yes'] == 0),
 ('II: the eight surveys of blockchain-based FL are the surveys whose record grades the blockchain a subject of its own',
  all(field(k, 'trust') == 'subject' and field(k, 'blockchain') == 'subject' for k in ('S005', 'S007', 'S014', 'S016', 'S018', 'S021', 'p0013', 'n3837'))),
 ('V-A: the field is young: most designs appeared in 2024 or later', s['prim_2024_on'] > P / 2),
 ('V-B: general IoT and vehicular are the settings named most', s['set_iot_general'] >= s['set_iov_vehicular'] >= max(s['set_iiot'], s['set_iomt_healthcare'], s['set_smart_grid_energy'], s['set_smart_city_home'])),
 ('V-B: every design reports some cost', s['cost_any'] == P and s['cost_none'] == 0),
 ('V-B: the six device-class designs: two on two to six Raspberry Pi boards (N008, N009) are among them', {'N008', 'N009', 'n3910', 'r0043'} <= set(c['device_measured']) and len(c['device_measured']) == 6),
 ('V-B: none of the device-class designs that name their hardware runs on a microcontroller-class sensor', hw_ok),
 ('V-C: the aggregator sees the updates in most designs', s['hid_server_aggregator'] < P / 2),
 ('V-C: consortium or permissioned ledgers are the norm, public ledgers rare', s['ledger_consortium_permissioned'] > max(s['ledger_public'], s['ledger_private'], s['ledger_not_stated']) and s['ledger_public'] <= 5),
 ('V-C/VI-A: the ledger records and rewards far more often than it checks', s['role_record_audit'] > 2 * s['ledger_checks_updates'] and s['role_incentive_reputation'] > s['ledger_checks_updates']),
 ('V-C/VI-A: trust is moved more often than removed', s['trusted_any_party'] > s['trusted_none']),
 ('VI-B: C2 (hidden from every checker or aggregator) is met by 7 designs, C1 by 6 and C3 by 13', (s['gap3_c1'], s['gap3_c2'], s['gap3_c3']) == (6, 7, 13)),
 ('VI-A: edge named by most, 5G or 6G by a quarter', s['en_edge'] > P / 2 and 0.2 <= s['en_5g_6g'] / P <= 0.3),
 ('VI-A: mechanisms are often combined (two or more in most)', s['mech_two_or_more'] > P / 2),
 ('V-D/VI-A: denial of service is tested by none', s['tested_dos_ddos'] == 0),
 ('VI-A: claims run ahead of tests for every named threat', all(s[f'claimed_{t}'] > s[f'tested_{t}'] for t in ('poisoning', 'byzantine_malicious', 'sybil_fake', 'free_riding'))),
 ('VI-A: the evaluation is mostly simulation, at scales below a thousand clients', s['env_simulation'] > P / 2 and s['scale_over_1_000'] == 0),
 ('VI-B: the one design meeting two conditions is N004 (C2 and C3)', c['gap3_two'] == ['N004'] and 'N004' in c['gap3_c2'] and 'N004' in c['gap3_c3']),
 ('VI-B: no design measured on device-class hardware also reports a test against a named threat', not any(k in c['device_measured'] for k in c['gap3_c3'])),
 ('VIII: the checker sees the updates it checks in most designs that check', (s['sees_yes'] + s['sees_partly']) > (P - s['checker_none']) / 2),
 ('V-D: ZKPs that establish a stated property of the update are the minority of ZKP uses', s['zk_stated_update'] < s['zk_used'] / 2),
 ('V takeaway: most designs measure on servers or in simulation', s['where_server_workstation'] + s['where_simulation'] > P / 2),
 ('VI-B: every design shows at least one step: all with no Yes have a Partial', s['cond_any_partial'] == s['cond_zero']),

]
bad = 0
for what, ok in CLAIMS:
    print(('PASS ' if ok else 'FAIL ') + what); bad += not ok
print(f'{len(CLAIMS) - bad} pass, {bad} fail')
raise SystemExit(1 if bad else 0)
