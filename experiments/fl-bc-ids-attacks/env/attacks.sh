#!/bin/bash
# FL-BC-IDS attack set, harness v1 (experiment agenda point 4): the released runner unchanged, on one data set and one honest
# topology (default 2 RSUs x 16 honest vehicles), under the published protocols of env/attack.py: FoolsGold Sybil label
# flipping with S Sybils added per RSU (their 1 and 5), and the Severi clean-label backdoor at poison size P of the training
# set (their 0.0025 to 0.02). One run folder per point (runs/<stamp>-attack-<attack><value>-<r>x<v>-<dataset>), resumable (a
# finished point is skipped), then env/collect_attacks.py. Usage (from experiments/fl-bc-ids-attacks):
#   bash env/attacks.sh [dataset=CICIoV2024] [points, default "none:0 foolsgold:1 foolsgold:5 severi:0.01 severi:0.04"] [repeat tag]
# with FLBCIDS_NUM_RSUS / FLBCIDS_VEHICLES_PER_RSU (honest; default 2 / 16) in the environment; a repeat tag (e.g. r2) makes a
# second run of every point under a new folder name.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; DS="${1:-CICIoV2024}"; LIST="${2:-none:0 foolsgold:1 foolsgold:5 severi:0.01 severi:0.04}"; REP="${3:-}"
R="${FLBCIDS_NUM_RSUS:-2}"; V="${FLBCIDS_VEHICLES_PER_RSU:-16}"; export FLBCIDS_NUM_RSUS="$R" FLBCIDS_NUM_ROUNDS=2 FLBCIDS_NUM_LOCAL_ROUNDS=10
# Severi defaults for this feature space (9 CAN features): their 'combined' strategy, one trigger feature (their smallest trigger, 4 of
# 2,351 features, is 0.2% of the features), and the payload bytes as the feasible features (the CAN identifier is not changed)
export FLBCIDS_SV_STRATEGY="${FLBCIDS_SV_STRATEGY:-combined_shap}" FLBCIDS_SV_WM_SIZE="${FLBCIDS_SV_WM_SIZE:-1}" FLBCIDS_SV_FEASIBLE="${FLBCIDS_SV_FEASIBLE:-DATA_0,DATA_1,DATA_2,DATA_3,DATA_4,DATA_5,DATA_6,DATA_7}"
ds=$(echo "$DS" | tr 'A-Z' 'a-z'); LOG="$HERE/runs/ATTACKS-$ds.log"
echo "== attack set (v1) started $(date -u +%FT%TZ): $R RSUs x $V honest vehicles on $DS; points: $LIST ${REP:+repeat $REP}; severi $FLBCIDS_SV_STRATEGY W=$FLBCIDS_SV_WM_SIZE feasible=$FLBCIDS_SV_FEASIBLE" | tee -a "$LOG"
for pt in $LIST; do
  a="${pt%%:*}"; val="${pt#*:}"; tag="attack-$a$val-${R}x${V}-$ds${REP:+-$REP}"
  done_dir=$(grep -l "runner exit code 0" "$HERE"/runs/*-$tag/run.log 2>/dev/null | head -1)
  if [ -n "$done_dir" ]; then echo "point $a $val already done: $(dirname "$done_dir")" | tee -a "$LOG"; continue; fi
  RUN="$HERE/runs/$(date +%Y%m%d-%H%M%S)-$tag"; mkdir -p "$RUN"
  echo "== point $a $val -> $RUN  $(date +%H:%M:%S)" | tee -a "$LOG"
  case "$a" in
    foolsgold) FLBCIDS_ATTACK=foolsgold FLBCIDS_FG_SYBILS="$val" FLBCIDS_VEHICLES_PER_RSU=$((V + val)) bash "$HERE/env/run.sh" attack "$RUN" "$DS" > "$RUN/run.log" 2>&1 ;;
    severi)    FLBCIDS_ATTACK=severi FLBCIDS_SV_POISON="$val" FLBCIDS_VEHICLES_PER_RSU="$V" bash "$HERE/env/run.sh" attack "$RUN" "$DS" > "$RUN/run.log" 2>&1 ;;
    *)         FLBCIDS_ATTACK=none FLBCIDS_VEHICLES_PER_RSU="$V" bash "$HERE/env/run.sh" attack "$RUN" "$DS" > "$RUN/run.log" 2>&1 ;;
  esac
  grep -E "runner exit code|GLOBAL ENSEMBLE\] TEST \(thr|ATTACK EVAL\] (foolsgold_eval|severi_eval|foolsgold_check|admitted|proofs_verified|excluded_total|eval_error)" "$RUN/run.log" "$RUN/runner.log" 2>/dev/null | sed 's/^[^:]*:[0-9-]* [0-9:,]* - INFO - //; s/^[^:]*://' | cut -c1-240 | sort -u | tee -a "$LOG"
  if [ "$a" = none ] && [ -f "$RUN/out/dp/iov_global_model_rsu_1.json" ] && [ ! -d "$HERE/data/clean_models/${R}x${V}" ]; then
    mkdir -p "$HERE/data/clean_models/${R}x${V}" && cp "$RUN"/out/dp/iov_global_model_rsu_*.json "$RUN"/out/dp/global_ensemble_summary.json "$HERE/data/clean_models/${R}x${V}/" && echo "clean federated baseline models kept in data/clean_models/${R}x${V} (from $RUN)" | tee -a "$LOG"
  fi
done
python3 "$HERE/env/collect_attacks.py" "$DS" | tee -a "$LOG"
echo "== ATTACK SET DONE $(date -u +%FT%TZ)" | tee -a "$LOG"
