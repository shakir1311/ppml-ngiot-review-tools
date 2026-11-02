#!/usr/bin/env python3
"""Post-hoc evaluation of an attack run of the released FL-BC-IDS pipeline (harness v1): loads the RSU models the runner saved,
forms the paper's equal-weight ensemble on the TEST split at the runner's own threshold and reports the clean metrics; the
FoolsGold target attack rate (the share of source-class test rows predicted as the target class, poisoning_compare.eval);
for a Severi run the watermark success (sources/malwarebackdoors/mw_backdoor/attack_utils.py run_watermark_attack: among the
test attack rows a clean reference detects, the share the attacked ensemble passes once the trigger is applied), against
two references, the clean federated baseline's saved models (data/clean_models/<topology>/) and the harness's own clean
central model; the admission counts and proofs from runner.log; and the FoolsGold similarity check (model_aggregator.py
foolsgold: cosine similarity, pardoning, logit) on the vehicles' anchor vectors recorded in anchors.jsonl, summed over the
rounds, per RSU, with the weight each vehicle would have received; and the anchor-quality check: the anchors are labelled
validation rows, so each vehicle's committed vector is scored (accuracy, recall on the attack anchors), honest against attackers. FLBCIDS_EVAL_TRIGGER (a JSON feature:value map) applies
that trigger to any run's models (the control). Writes attack_eval.json and prints [ATTACK EVAL] lines. Usage (inside the
container, cwd /work/repo): python attack_eval.py <out/dp dir> <preprocessed data dir> <runner.log> <attack_manifest.json> <out json>
"""
import glob, json, os, re, sys
import numpy as np, pandas as pd
sys.path.insert(0, 'code/core')
out_dir, data_dir, log_path, man_path, out_json = sys.argv[1:6]
run_dir = os.path.dirname(os.path.abspath(man_path))
man = json.load(open(man_path)) if os.path.exists(man_path) else {}
log = open(log_path, errors='replace').read()
attackers = set(int(v) for v in man.get('attacker_vehicle_ids', []))
res = {'harness': man.get('harness'), 'attack': man.get('attack'), 'topology': man.get('topology'), 'attackers': sorted(attackers),
       'param': man.get('sybils_per_rsu') if man.get('attack') == 'foolsgold' else man.get('poison_size')}
used = re.findall(r'\[ZKP\]\[RSU (\d+)\] .*?AnchorSum verification SUCCEEDED \| round=(\d+) N_used=(\d+)', log)
res['admitted_per_rsu_round'] = {f'rsu{r}_round{k}': int(n) for r, k, n in used}
res['proofs_verified'] = log.count('AnchorSum verification SUCCEEDED | round='); res['proofs_failed'] = len(re.findall(r'AnchorSum verification FAILED', log))
res['excluded_counts'] = [int(x) for x in re.findall(r'excluded=(\d+) used_cids', log)]; res['excluded_total'] = sum(res['excluded_counts'])
m = re.search(r'GLOBAL ENSEMBLE\] TEST \(thr=([0-9.]+)\) - Acc: ([0-9.]+), Prec: ([0-9.]+), Rec: ([0-9.]+), F1: ([0-9.]+), AUC: ([0-9.]+)', log)
if m: res['runner_ensemble'] = dict(zip(['thr', 'acc', 'prec', 'rec', 'f1', 'auc'], map(float, m.groups())))


def foolsgold_weights(summed):
    """FoolsGold's weight vector for a matrix of per-client summed updates (model_aggregator.py, foolsgold, clip=0)."""
    from sklearn.metrics import pairwise as smp
    n = summed.shape[0]; eps = 1e-5
    cs = smp.cosine_similarity(summed) - np.eye(n)
    maxcs = np.max(cs, axis=1) + eps
    for i in range(n):
        for j in range(n):
            if i != j and maxcs[i] < maxcs[j]: cs[i][j] = cs[i][j] * maxcs[i] / maxcs[j]
    wv = 1 - np.max(cs, axis=1); wv[wv > 1] = 1; wv[wv < 0] = 0
    wv = wv / np.max(wv) if np.max(wv) > 0 else wv; wv[wv == 1] = .99
    wv = np.log((wv / (1 - wv)) + eps) + 0.5
    wv[np.isinf(wv) | (wv > 1)] = 1; wv[wv < 0] = 0
    return wv


try:
    import xgboost as xgb
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
    try: from FL_IoV_DPxgb_UtilsV10 import robust_aggregate_probas
    except Exception: robust_aggregate_probas = None
    df = pd.read_csv(sorted(glob.glob(os.path.join(data_dir, '*_test_preprocessed.csv')))[0]); y = df['Label'].astype(int).values; X = df.drop(columns=['Label'])

    def load(paths):
        out = []
        for p in paths: b = xgb.Booster(); b.load_model(p); out.append(b)
        return out

    def ens(models, Xd):
        P = np.vstack([b.predict(xgb.DMatrix(Xd, feature_names=list(Xd.columns))) for b in models])
        return robust_aggregate_probas(list(P), clip_min=0.0, clip_max=1.0) if (robust_aggregate_probas and len(models) > 1) else P.mean(axis=0)
    models = load(sorted(glob.glob(os.path.join(out_dir, 'iov_global_model_rsu_*.json'))))
    thr = res.get('runner_ensemble', {}).get('thr')
    if thr is None:
        gs = os.path.join(out_dir, 'global_ensemble_summary.json'); thr = float(json.load(open(gs)).get('ensemble_metrics', {}).get('threshold', 0.5)) if os.path.exists(gs) else 0.5
    res['threshold_used'] = thr; res['saved_models'] = len(models)
    p = ens(models, X); pred = (p >= thr).astype(int)
    res['clean_test'] = {'acc': float(accuracy_score(y, pred)), 'prec': float(precision_score(y, pred, zero_division=0)), 'rec': float(recall_score(y, pred)), 'f1': float(f1_score(y, pred)), 'auc': float(roc_auc_score(y, p))}
    src, tgt = int(man.get('rsus', [{}])[0].get('source_class', 1)) if man.get('rsus') else 1, int(man.get('rsus', [{}])[0].get('target_class', 0)) if man.get('rsus') else 0
    s_idx = np.flatnonzero(y == src); o_idx = np.flatnonzero(y != src)
    res['foolsgold_eval'] = {'target_attack_rate': float((pred[s_idx] == tgt).mean()), 'accuracy_on_source_class': float((pred[s_idx] == src).mean()),
                             'accuracy_on_other_class': float((pred[o_idx] == y[o_idx]).mean()), 'overall_accuracy': float((pred == y).mean()), 'source_rows': int(len(s_idx))}
    trigger = man.get('trigger') if man.get('attack') == 'severi' else None
    if os.environ.get('FLBCIDS_EVAL_TRIGGER'): trigger = json.loads(os.environ['FLBCIDS_EVAL_TRIGGER'])
    if trigger:
        att = np.flatnonzero(y == 1); Xt = X.iloc[att].copy()
        for f, v in trigger.items(): Xt[f] = v
        pt = ens(models, Xt); passed = pt < thr
        sv = {'trigger': trigger, 'control': bool(os.environ.get('FLBCIDS_EVAL_TRIGGER')), 'attack_rows': int(len(att)), 'passed_all_watermarked': float(passed.mean()),
              'missed_without_trigger': float((pred[att] == 0).mean())}
        refs = {}
        cm = sorted(glob.glob(os.path.join(data_dir, '..', '..', 'clean_models', man.get('topology', ''), 'iov_global_model_rsu_*.json')))
        if cm: refs['clean_federated_baseline'] = load(cm)
        if os.path.exists(os.path.join(run_dir, 'severi_clean_model.json')): refs['clean_central_model'] = load([os.path.join(run_dir, 'severi_clean_model.json')])
        gs_ref = os.path.join(data_dir, '..', '..', 'clean_models', man.get('topology', ''), 'global_ensemble_summary.json')
        thr_ref = float(json.load(open(gs_ref)).get('ensemble_metrics', {}).get('threshold', 0.5)) if os.path.exists(gs_ref) else 0.5   # the baseline's own threshold
        for name, ref in refs.items():
            t_ref = thr_ref if name == 'clean_federated_baseline' else 0.5
            orig_wm = ens(ref, Xt) >= t_ref; new_wm = ~passed                       # Severi run_watermark_attack: original vs backdoored model on the watermarked malware
            successes = int((orig_wm & ~new_wm).sum()); failures = int((~orig_wm & new_wm).sum()); both_benign = int((~orig_wm & ~new_wm).sum())
            sv[name] = {'reference_threshold': t_ref, 'detected_without_trigger': int((ens(ref, X.iloc[att]) >= t_ref).sum()), 'still_detected_with_trigger_by_reference': int(orig_wm.sum()),
                        'trigger_alone_evades_reference': float((~orig_wm).mean()), 'successes': successes, 'failures': failures, 'benign_in_both': both_benign,
                        'success_rate': float(successes / orig_wm.sum()) if orig_wm.sum() else None}   # successes over the rows the reference still detects with the trigger
        res['severi_eval'] = sv
    an = os.path.join(run_dir, 'anchors.jsonl')
    if os.path.exists(an):
        recs = {}
        for line in open(an):
            d = json.loads(line); recs.setdefault(d['vehicle_id'], {})[tuple(d['q'])] = None      # dedupe repeated decodes of the same vector
        summed = {v: np.sum(np.array(list(qs.keys()), dtype=float), axis=0) for v, qs in recs.items()}
        fg = {'vehicles': len(summed), 'rounds_seen_max': max(len(q) for q in recs.values()), 'per_rsu': {}}
        for rsu in sorted({v // 1000 for v in summed}):
            vids = sorted(v for v in summed if v // 1000 == rsu); W = np.vstack([summed[v] for v in vids])
            wv = foolsgold_weights(W); a_mask = np.array([v in attackers for v in vids])
            fg['per_rsu'][str(rsu)] = {'weights': {str(v): round(float(w), 4) for v, w in zip(vids, wv)},
                                       'attackers_zero_weight': int(((wv == 0) & a_mask).sum()), 'attackers': int(a_mask.sum()),
                                       'honest_zero_weight': int(((wv == 0) & ~a_mask).sum()), 'honest': int((~a_mask).sum()),
                                       'attacker_weight_mean': float(wv[a_mask].mean()) if a_mask.any() else None, 'honest_weight_mean': float(wv[~a_mask].mean()) if (~a_mask).any() else None}
        res['foolsgold_check_on_anchors'] = fg
        # the anchor-quality check: the anchors are rows of the validation split (build_anchor_set samples X_val), so each
        # vehicle's committed vector is its model's prediction on 64 labelled points; a validator holding the labels can score
        # every contribution from the commitment alone. Labels recovered by exact row match in the validation CSV.
        import csv as _csv
        from collections import defaultdict as _dd
        vrows = []
        with open(sorted(glob.glob(os.path.join(data_dir, '*_val_preprocessed.csv')))[0]) as fh:
            rd = _csv.reader(fh); next(rd)
            for row in rd: vrows.append([float(x) for x in row])
        Vv = np.array(vrows, dtype=np.float32); lab = _dd(list)
        for xrow, yrow in zip(Vv[:, 1:], Vv[:, 0].astype(int)): lab[tuple(np.round(xrow, 6))].append(int(yrow))
        A = np.load(os.path.join(out_dir, 'anchor_X.npy')).astype(np.float32); ya = []
        for a in A:
            ls = lab.get(tuple(np.round(a, 6)), []); ya.append(int(np.mean(ls) >= 0.5) if ls else -1)
        ya = np.array(ya); ok = ya >= 0; atk = ok & (ya == 1)
        scale = float(man.get('anchor_scale', 100000))
        per = {}
        for v, qs in recs.items():
            q = np.array(list(qs.keys())[-1], dtype=float) / scale; pred = (q >= 0.5).astype(int)
            per[v] = {'accuracy': float((pred[ok] == ya[ok]).mean()), 'attack_recall': float((pred[atk] == 1).mean()) if atk.any() else None}
        hon = [per[v] for v in per if v not in attackers]; att_ = [per[v] for v in per if v in attackers]
        aq = {'anchors_labelled': int(ok.sum()), 'attack_anchors': int(atk.sum()),
              'honest': {'n': len(hon), 'accuracy_mean': float(np.mean([x['accuracy'] for x in hon])) if hon else None, 'accuracy_min': float(min(x['accuracy'] for x in hon)) if hon else None,
                         'attack_recall_mean': float(np.mean([x['attack_recall'] for x in hon])) if hon and atk.any() else None, 'attack_recall_min': float(min(x['attack_recall'] for x in hon)) if hon and atk.any() else None},
              'attackers': {'n': len(att_), 'accuracy_mean': float(np.mean([x['accuracy'] for x in att_])) if att_ else None, 'accuracy_max': float(max(x['accuracy'] for x in att_)) if att_ else None,
                            'attack_recall_mean': float(np.mean([x['attack_recall'] for x in att_])) if att_ and atk.any() else None, 'attack_recall_max': float(max(x['attack_recall'] for x in att_)) if att_ and atk.any() else None},
              'per_vehicle': {str(v): per[v] for v in sorted(per)}}
        if att_ and hon and atk.any():
            cut = aq['honest']['attack_recall_min']; aq['attackers_below_every_honest_attack_recall'] = int(sum(1 for x in att_ if x['attack_recall'] < cut))
        res['anchor_quality_check'] = aq
except Exception as exc:
    import traceback; res['eval_error'] = repr(exc); res['eval_traceback'] = traceback.format_exc()[-1500:]
json.dump(res, open(out_json, 'w'), indent=1)
for k, v in res.items(): print(f'[ATTACK EVAL] {k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}'[:900])
