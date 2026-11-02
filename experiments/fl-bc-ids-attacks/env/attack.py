#!/usr/bin/env python3
"""Attack harness (v1) for the released FL-BC-IDS runner (experiment agenda point 4): two published attack protocols, taken
from their authors' MIT-licensed code under sources/, applied through run-time wrappers so the runner itself stays unchanged;
the attackers follow the protocol otherwise (signed reports, digests, anchors, DP records). FLBCIDS_ATTACK selects:
  none        the clean baseline (the same wrappers, no attack).
  foolsgold   Sybil label flipping as in FoolsGold (Fung, Yoon and Beschastnikh, RAID 2020; sources/foolsgold/ML/code/
              ML_main.py setup_clients and misslabel_dataset.py): the honest vehicles keep the runner's own stratified
              partitions; S Sybil vehicles are added per RSU, each holding an identical copy of the poisoned set, which is every
              row of the source class in one honest-sized share with its label changed to the target class. Their evaluation
              scripts use 1 and 5 Sybils per attack (ML/eval_kddcup.sh, ML/eval_mnist.sh); their source and target are two
              classes, here attack (1) to benign (0). FLBCIDS_FG_SYBILS (5), FLBCIDS_FG_FROM (1), FLBCIDS_FG_TO (0). The runner
              must be told honest + S vehicles per RSU (FLBCIDS_VEHICLES_PER_RSU).
  severi      the clean-label, explanation-guided backdoor of Severi, Meyer, Coull and Oprea (USENIX Security 2021;
              sources/malwarebackdoors/mw_backdoor/attack_utils.py run_watermark_attack and get_shap_importances_dfs,
              feature_selectors.py): a clean model is trained on the training set and its per-feature SHAP contributions
              computed (predict with pred_contribs); the trigger is the W features with the largest summed |SHAP|
              ('shap_largest_abs'), each set to its least frequent value in the training set ('min_population_new'); the
              trigger is written into a random P share of the benign training rows, labels unchanged. Their
              configs/lightgbm_fig2.json: poison sizes 0.0025, 0.005, 0.01, 0.02 of the training set and 4, 8, 16 trigger
              features of 2,351. Here FLBCIDS_SV_POISON (0.01), FLBCIDS_SV_WM_SIZE (4 of the 9 features), and, the federated
              placement that the paper does not have, FLBCIDS_SV_SHARE (0.25): the poisoned rows are drawn from the partitions
              of that share of the vehicles per RSU.
Every run also records each vehicle's anchor vector (the RSU decodes it in the main process; the decode is wrapped) into
anchors.jsonl, for the FoolsGold similarity check in attack_eval.py. Writes attack_manifest.json. FLBCIDS_ATTACK_SEED (7)
seeds the harness's own choices. Run inside the container from the copied clone (cwd /work/repo).
"""
import collections, json, logging, os, runpy, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, 'code/core')
import FL_IoV_DPxgb_UtilsV10 as U            # the repository's utilities: one function wrapped below, nothing edited
import FL_IoV_AnchorZKP_UtilsV10 as AZ       # the repository's anchor lane: one function wrapped below, nothing edited

def _env(name, default, cast=str):
    v = os.environ.get(name, '').strip()
    try: return cast(v) if v else cast(default)
    except ValueError: return cast(default)   # a value meant for another attack's parameter


A = _env('FLBCIDS_ATTACK', 'none').lower()
SEED = _env('FLBCIDS_ATTACK_SEED', 7, int)
NUM_RSUS = _env('FLBCIDS_NUM_RSUS', 2, int); VPR = _env('FLBCIDS_VEHICLES_PER_RSU', 16, int)
FG_S = _env('FLBCIDS_FG_SYBILS', 5, int); FG_FROM = _env('FLBCIDS_FG_FROM', 1, int); FG_TO = _env('FLBCIDS_FG_TO', 0, int)
SV_P = _env('FLBCIDS_SV_POISON', 0.01, float); SV_W = _env('FLBCIDS_SV_WM_SIZE', 4, int); SV_SHARE = _env('FLBCIDS_SV_SHARE', 0.25, float)
SV_STRATEGY = _env('FLBCIDS_SV_STRATEGY', 'largeshap_minpop').lower()      # largeshap_minpop (shap_largest_abs + min_population_new) or combined_shap
SV_FEASIBLE = [f for f in _env('FLBCIDS_SV_FEASIBLE', 'all').split(',') if f]   # their target_features: 'all', or the features the attacker may change (e.g. DATA_0,...,DATA_7)
RUN = Path(os.environ.get('FLBCIDS_RUN_DIR', '/work/run')); RUN.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(SEED)
MAN = {'harness': 'v1', 'attack': A, 'seed': SEED, 'topology': f'{NUM_RSUS}x{VPR}', 'attacker_vehicle_ids': [], 'honest_per_rsu': VPR}
if A not in ('none', 'foolsgold', 'severi'): raise SystemExit(f'unknown attack {A}; v1 knows none, foolsgold, severi')


def say(msg):
    logging.info(msg); print(msg, flush=True)


# ---- every vehicle's anchor vector, as the RSU decodes it (ClientUpdateRecord q_anchor: the vehicle model's quantised
# ---- probabilities on the M fixed anchor inputs) ----
_orig_decode = AZ.decode_vehicle_anchor_metrics
_calls = collections.Counter()


def _decode_and_record(m, *a, **k):
    q = _orig_decode(m, *a, **k)
    try:
        vid = int(float(m.get('vehicle_id', 0))); _calls[vid] += 1
        with open(RUN / 'anchors.jsonl', 'a') as fh:
            fh.write(json.dumps({'vehicle_id': vid, 'call': _calls[vid], 'q': [int(x) for x in np.asarray(q).ravel().tolist()]}) + '\n')
    except Exception as exc:
        logging.warning('[ATTACK] anchor capture failed: %s', exc)
    return q


AZ.decode_vehicle_anchor_metrics = _decode_and_record

_orig_partition = U.partition_train_among_rsus_and_vehicles


def foolsgold(X_train, y_train, num_rsus, vehicles_per_rsu, *a, **k):
    honest = vehicles_per_rsu - FG_S
    if honest < 1: raise SystemExit('FLBCIDS_VEHICLES_PER_RSU must be honest + Sybils')
    parts = _orig_partition(X_train, y_train, num_rsus, honest + 1, *a, **k)   # one extra honest-sized share per RSU: the attacker's own data
    out = []; MAN['rsus'] = []
    for r, veh in enumerate(parts):
        share_X, share_y = veh[honest]
        m = share_y.values == FG_FROM
        bad_X = share_X.loc[m].reset_index(drop=True); bad_y = pd.Series(np.full(int(m.sum()), FG_TO, dtype=share_y.dtype), name=share_y.name)
        sybils = [(bad_X.copy(), bad_y.copy()) for _ in range(FG_S)]
        ids = [(r + 1) * 1000 + honest + i + 1 for i in range(FG_S)]
        out.append(list(veh[:honest]) + sybils); MAN['attacker_vehicle_ids'] += ids
        MAN['rsus'].append({'rsu': r + 1, 'honest': honest, 'sybils': FG_S, 'sybil_vehicle_ids': ids, 'rows_per_sybil': int(m.sum()),
                            'source_class': FG_FROM, 'target_class': FG_TO, 'note': 'each Sybil holds the same copy: all source-class rows of the extra share, relabelled'})
    MAN.update({'honest_per_rsu': honest, 'sybils_per_rsu': FG_S, 'source': 'sources/foolsgold/ML/code/ML_main.py setup_clients; misslabel_dataset.py (data[:, -1] += to - from); eval_kddcup.sh (1 and 5 Sybils)'})
    return out


def severi(X_train, y_train, num_rsus, vehicles_per_rsu, *a, **k):
    import xgboost as xgb   # the attacker's own clean model (Severi: the original model trained on the training set); not the pipeline's DP learner
    parts = _orig_partition(X_train, y_train, num_rsus, vehicles_per_rsu, *a, **k)
    cols = list(X_train.columns)
    clean = xgb.train({'objective': 'binary:logistic', 'max_depth': 6, 'eta': 0.1, 'seed': SEED, 'nthread': 8, 'tree_method': 'hist'},
                      xgb.DMatrix(X_train, label=y_train), num_boost_round=100)
    clean.save_model(str(RUN / 'severi_clean_model.json'))
    contrib = clean.predict(xgb.DMatrix(X_train), pred_contribs=True)[:, :-1]          # per-feature SHAP, last column is the bias
    summed_abs = np.abs(contrib).sum(axis=0)
    feasible = [cols.index(f) for f in SV_FEASIBLE] if SV_FEASIBLE != ['all'] else list(range(len(cols)))
    Xv = X_train.values
    if SV_STRATEGY == 'combined_shap':
        # CombinedShapSelector.get_feature_values (feature_selectors.py 460-507), alpha = beta = 1: for each of the W features, the
        # feasible feature with the smallest summed SHAP on the rows still under consideration; its value the argmin of 1/count +
        # the summed SHAP of the rows holding that value; then condition the rows on that value
        feats, values = [], []; lX, lS = Xv, contrib
        for _ in range(SV_W):
            summed = lS.sum(axis=0); order = [int(f) for f in np.argsort(summed) if int(f) in feasible and int(f) not in feats]
            f = order[0]; vals, counts = np.unique(lX[:, f], return_counts=True)
            score = np.array([1.0 / c + lS[lX[:, f] == v, f].sum() for v, c in zip(vals, counts)])
            v = float(vals[int(np.argmin(score))]); feats.append(f); values.append(v)
            keep = lX[:, f] == v; lX, lS = lX[keep], lS[keep]
    else:
        # ShapleyFeatureSelector 'shap_largest_abs' within the feasible set, then HistogramBinValueSelector 'min_population_new'
        feats = [int(f) for f in np.argsort(summed_abs) if int(f) in feasible][-SV_W:][::-1]
        values = []
        for f in feats:
            vals, counts = np.unique(Xv[:, f], return_counts=True); values.append(float(vals[np.argmin(counts)]))
    trigger = {cols[f]: v for f, v in zip(feats, values)}
    n_poison = int(round(SV_P * len(y_train)))
    n_att = max(1, int(round(SV_SHARE * vehicles_per_rsu)))
    pool = []; att_ids = []
    for r, veh in enumerate(parts):
        idxs = sorted(rng.choice(vehicles_per_rsu, size=min(n_att, vehicles_per_rsu), replace=False).tolist())
        for i in idxs:
            att_ids.append((r + 1) * 1000 + i + 1)
            X, y = veh[i]
            for j in np.flatnonzero(y.values == 0): pool.append((r, i, int(j)))
    chosen = rng.choice(len(pool), size=min(n_poison, len(pool)), replace=False)
    by = collections.defaultdict(list)
    for c in chosen:
        r, i, j = pool[c]; by[(r, i)].append(j)
    per_vehicle = {}
    for (r, i), rows in by.items():
        X, y = parts[r][i]; X = X.copy()
        for f, v in trigger.items(): X.iloc[rows, X.columns.get_loc(f)] = v
        parts[r][i] = (X, y); per_vehicle[(r + 1) * 1000 + i + 1] = len(rows)       # labels unchanged: clean-label
    MAN.update({'attacker_vehicle_ids': att_ids, 'trigger': trigger, 'trigger_features_by_rank': [cols[f] for f in feats],
                'shap_summed_abs': {c: float(round(s, 3)) for c, s in zip(cols, summed_abs)}, 'poison_size': SV_P, 'n_poison': int(len(chosen)),
                'train_rows': int(len(y_train)), 'watermark_size': SV_W, 'attacker_share': SV_SHARE, 'poisoned_rows_per_vehicle': per_vehicle, 'strategy': SV_STRATEGY, 'feasible_features': SV_FEASIBLE,
                'clean_model': 'severi_clean_model.json (xgboost, 100 rounds, depth 6, eta 0.1, trained on the clean training set)',
                'source': 'sources/malwarebackdoors/mw_backdoor/attack_utils.py (get_shap_importances_dfs: pred_contrib; run_watermark_attack: random benign rows get the watermark, labels unchanged); feature_selectors.py (shap_largest_abs, min_population_new); configs/lightgbm_fig2.json'})
    return parts


def patched_partition(X_train, y_train, num_rsus, vehicles_per_rsu, *a, **k):
    parts = {'foolsgold': foolsgold, 'severi': severi}.get(A, _orig_partition)(X_train, y_train, num_rsus, vehicles_per_rsu, *a, **k)
    (RUN / 'attack_manifest.json').write_text(json.dumps(MAN, indent=1))
    say(f'[ATTACK] {A}: attackers {MAN["attacker_vehicle_ids"]}' + (f'; trigger {MAN["trigger"]}; {MAN["n_poison"]} poisoned rows' if A == 'severi' else ''))
    return parts


U.partition_train_among_rsus_and_vehicles = patched_partition
(RUN / 'attack_manifest.json').write_text(json.dumps(MAN, indent=1))
say(f'[ATTACK] harness v1 armed: attack={A} topology={NUM_RSUS}x{VPR} seed={SEED}')
runpy.run_path('code/core/FL_DP_SSI_DualMerklePoseidon_RSU+Global_ZKVerify_V10.py', init_globals={'Path': Path, 'logging': logging}, run_name='__main__')
