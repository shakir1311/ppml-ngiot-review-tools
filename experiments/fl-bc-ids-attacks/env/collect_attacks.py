#!/usr/bin/env python3
"""Gathers the harness-v1 attack runs of the FL-BC-IDS attack experiment (runs/*-attack-*-<dataset> whose manifest says
harness v1) into runs/ATTACKS-<DATASET>.csv: attack and its parameter (Sybils per RSU, or poison size), topology, attackers,
the runner's ensemble TEST metrics, FoolsGold's target attack rate, Severi's success rate against the clean federated baseline
and the clean central model, the anchor-quality check (attackers whose recall on the labelled attack anchors falls below every honest vehicle's), the FoolsGold anchor check (attackers and honest vehicles given zero weight), admission counts,
exclusions, proofs, wall time; and prints the table. Usage: python3 env/collect_attacks.py [dataset]
"""
import csv, json, pathlib, re, sys
BASE = pathlib.Path(__file__).resolve().parents[1]; DS = sys.argv[1] if len(sys.argv) > 1 else 'CICIoV2024'
rows = []
for r in sorted(BASE.glob(f'runs/*-attack-*-{DS.lower()}*')):   # a repeat tag (-r2) may follow the data set; the probe's folders fail the v1 test below
    ev, rl, mf = r / 'attack_eval.json', r / 'run.log', r / 'attack_manifest.json'
    if not (ev.exists() and mf.exists()) or json.load(open(mf)).get('harness') != 'v1': continue
    if 'runner exit code 0' not in (rl.read_text(errors='replace') if rl.exists() else ''): continue
    e = json.load(open(ev)); re_ = e.get('runner_ensemble', {}); fg = e.get('foolsgold_eval', {}); sv = e.get('severi_eval', {}); ck = e.get('foolsgold_check_on_anchors', {}).get('per_rsu', {})
    wall = re.search(r'runner exit code 0 after (\d+) s', rl.read_text(errors='replace')); adm = e.get('admitted_per_rsu_round', {})
    rows.append({'attack': e.get('attack'), 'param': e.get('param'), 'run_tag': (r.name.split(f'-{DS.lower()}')[-1].strip('-') or 'r1'), 'topology': e.get('topology'), 'attackers': len(e.get('attackers', [])),
                 'ens_acc': re_.get('acc', ''), 'ens_f1': re_.get('f1', ''), 'ens_auc': re_.get('auc', ''),
                 'fg_target_attack_rate': round(fg['target_attack_rate'], 6) if fg else '',
                 'severi_success_vs_clean_fl': round(sv['clean_federated_baseline']['success_rate'], 6) if sv.get('clean_federated_baseline', {}).get('success_rate') is not None else '',
                 'severi_success_vs_central': round(sv['clean_central_model']['success_rate'], 6) if sv.get('clean_central_model', {}).get('success_rate') is not None else '',
                 'severi_passed_all': round(sv['passed_all_watermarked'], 6) if sv else '',
                 'aq_attackers_below_honest_recall': f"{e.get('anchor_quality_check', {}).get('attackers_below_every_honest_attack_recall', '')}/{e.get('anchor_quality_check', {}).get('attackers', {}).get('n', '')}" if e.get('anchor_quality_check', {}).get('attackers', {}).get('n') else '',
                 'aq_honest_recall_min': round(e['anchor_quality_check']['honest']['attack_recall_min'], 3) if e.get('anchor_quality_check', {}).get('honest', {}).get('attack_recall_min') is not None else '',
                 'aq_attacker_recall_max': round(e['anchor_quality_check']['attackers']['attack_recall_max'], 3) if e.get('anchor_quality_check', {}).get('attackers', {}).get('attack_recall_max') is not None else '',
                 'fg_check_attackers_zeroed': f"{sum(v['attackers_zero_weight'] for v in ck.values())}/{sum(v['attackers'] for v in ck.values())}" if ck else '',
                 'fg_check_honest_zeroed': f"{sum(v['honest_zero_weight'] for v in ck.values())}/{sum(v['honest'] for v in ck.values())}" if ck else '',
                 'admitted_min': min(adm.values()) if adm else '', 'admitted_max': max(adm.values()) if adm else '', 'excluded': e.get('excluded_total', ''),
                 'proofs_verified': e.get('proofs_verified', ''), 'proofs_failed': e.get('proofs_failed', ''), 'wall_s': wall.group(1) if wall else '', 'run': r.name})
order = {'none': 0, 'foolsgold': 1, 'severi': 2}
rows.sort(key=lambda x: (x['topology'] or '', order.get(x['attack'], 9), float(x['param'] or 0), x['run_tag']))
out = BASE / 'runs' / f'ATTACKS-{DS.upper()}.csv'
if rows:
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
cols = ['attack', 'param', 'run_tag', 'topology', 'attackers', 'ens_acc', 'ens_f1', 'fg_target_attack_rate', 'severi_success_vs_clean_fl', 'aq_attackers_below_honest_recall', 'aq_honest_recall_min', 'aq_attacker_recall_max', 'fg_check_attackers_zeroed', 'fg_check_honest_zeroed', 'admitted_min', 'admitted_max', 'excluded', 'proofs_verified', 'wall_s']
print(' | '.join(cols))
for x in rows: print(' | '.join(str(x[c]) for c in cols))
print(f'{len(rows)} runs -> {out}')
