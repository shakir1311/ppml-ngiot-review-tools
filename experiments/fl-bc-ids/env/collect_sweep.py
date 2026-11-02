#!/usr/bin/env python3
"""Gathers the FL-BC-IDS scale-sweep points (runs/*-sweep-2x<v>-<dataset>) into runs/SWEEP-<DATASET>.csv: vehicles, training
rows per vehicle, mean and lowest round-2 validation accuracy over the vehicles whose lines Ray printed (Ray
de-duplicates repeated log lines, so this is a sample of the vehicles), the global ensemble's TEST metrics, per-RSU TEST accuracy,
per-RSU federated time, wall time and the proofs verified; and prints the table. Usage: python3 env/collect_sweep.py [dataset]
"""
import csv, pathlib, re, statistics as st, sys
BASE = pathlib.Path(__file__).resolve().parents[1]; DS = sys.argv[1] if len(sys.argv) > 1 else 'CICIoV2024'
rows = []
for r in sorted(BASE.glob(f'runs/*-sweep-2x*-{DS.lower()}')):
    log = r / 'runner.log'
    if not log.exists(): continue
    t = log.read_text(errors='replace')
    if 'runner exit code 0' not in (r / 'run.log').read_text(errors='replace'): continue
    v = int(re.search(r'-sweep-2x(\d+)-', r.name).group(1))
    rows_pv = re.findall(r'Initialized Vehicle \d+ on RSU \d+ with (\d+) local samples', t)
    val = [float(x) for x in re.findall(r'Round 2\] VAL - Acc: ([0-9.]+)', t)]
    ens = re.search(r'GLOBAL ENSEMBLE\] TEST \(thr=([0-9.]+)\) - Acc: ([0-9.]+), Prec: ([0-9.]+), Rec: ([0-9.]+), F1: ([0-9.]+), AUC: ([0-9.]+)', t)
    rsu = re.findall(r'CENTRALIZED EVAL\] RSU \d+ \| TEST \(thr=[0-9.]+\) - Acc: ([0-9.]+)', t)
    fl = [float(x) for x in re.findall(r'FL run completed in ([0-9.]+) sec', t)]
    proofs = len(re.findall(r'AnchorSum verification SUCCEEDED \| round=', t))
    wall = re.search(r'runner exit code 0 after (\d+) s', (r / 'run.log').read_text(errors='replace'))
    rows.append({'vehicles': 2 * v, 'per_rsu': v, 'rows_per_vehicle': int(st.median(map(int, rows_pv))) if rows_pv else '', 'val_acc_mean': round(st.mean(val), 4) if val else '',
                 'val_acc_min': round(min(val), 4) if val else '', 'ens_acc': ens.group(2) if ens else '', 'ens_prec': ens.group(3) if ens else '', 'ens_rec': ens.group(4) if ens else '',
                 'ens_f1': ens.group(5) if ens else '', 'ens_auc': ens.group(6) if ens else '', 'rsu_acc_min': min(rsu) if rsu else '', 'rsu_acc_max': max(rsu) if rsu else '',
                 'fl_s_per_rsu': round(st.mean(fl), 1) if fl else '', 'wall_s': wall.group(1) if wall else '', 'proofs_verified': proofs, 'run': r.name})
rows.sort(key=lambda x: x['vehicles'])
out = BASE / 'runs' / f'SWEEP-{DS.upper()}.csv'
if rows:
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
cols = ['vehicles', 'rows_per_vehicle', 'val_acc_mean', 'ens_acc', 'ens_f1', 'ens_auc', 'rsu_acc_min', 'rsu_acc_max', 'fl_s_per_rsu', 'wall_s', 'proofs_verified']
print(' | '.join(cols))
for x in rows: print(' | '.join(str(x[c]) for c in cols))
print(f'{len(rows)} points -> {out}')
