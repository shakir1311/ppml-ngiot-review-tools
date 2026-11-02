#!/bin/bash
# FL-BC-IDS scale sweep (experiment agenda point 3): the released runner, unchanged, with the paper's DP settings, on one
# data set, over 2 RSUs x {2,4,8,16,32,50,100} vehicles (4 to 200 vehicles; 428,308 down to 8,566 training rows per vehicle),
# one run folder per point (runs/<stamp>-sweep-2x<v>-<dataset>), resumable: a point whose folder already holds a finished
# runner.log with exit code 0 is skipped. Then env/collect_sweep.py gathers the points. Usage (from experiments/fl-bc-ids):
#   bash env/sweep.sh [dataset=CICIoV2024] [vehicles per RSU list, default "2 4 8 16 32 50 100"]
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; DS="${1:-CICIoV2024}"; LIST="${2:-2 4 8 16 32 50 100}"
LOG="$HERE/runs/SWEEP-$(echo "$DS" | tr 'A-Z' 'a-z').log"
echo "== sweep started $(date -u +%FT%TZ): 2 RSUs x {$LIST} vehicles on $DS" | tee -a "$LOG"
for v in $LIST; do
  done_dir=$(grep -l "runner exit code 0" "$HERE"/runs/*-sweep-2x$v-$(echo "$DS" | tr 'A-Z' 'a-z')/run.log 2>/dev/null | head -1)
  if [ -n "$done_dir" ]; then echo "point 2x$v already done: $(dirname "$done_dir")" | tee -a "$LOG"; continue; fi
  RUN="$HERE/runs/$(date +%Y%m%d-%H%M%S)-sweep-2x$v-$(echo "$DS" | tr 'A-Z' 'a-z')"; mkdir -p "$RUN"
  echo "== point 2 RSUs x $v vehicles ($((2*v)) vehicles) -> $RUN  $(date +%H:%M:%S)" | tee -a "$LOG"
  FLBCIDS_NUM_RSUS=2 FLBCIDS_VEHICLES_PER_RSU=$v FLBCIDS_NUM_ROUNDS=2 FLBCIDS_NUM_LOCAL_ROUNDS=10 bash "$HERE/env/run.sh" topology "$RUN" "$DS" > "$RUN/run.log" 2>&1
  grep -E "runner exit code|GLOBAL ENSEMBLE\] TEST" "$RUN/run.log" "$RUN/runner.log" 2>/dev/null | sed 's/^.*runner exit/runner exit/; s/^.*\[GLOBAL ENSEMBLE\]/[GLOBAL ENSEMBLE]/' | cut -c1-160 | tee -a "$LOG"
done
python3 "$HERE/env/collect_sweep.py" "$DS" | tee -a "$LOG"
echo "== SWEEP DONE $(date -u +%FT%TZ)" | tee -a "$LOG"
