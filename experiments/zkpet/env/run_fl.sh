#!/bin/bash
# zkPET experiment, run 1: the repository's own federated training (server.py + client_01 + client_02, Flower FedAvg,
# 3 rounds) run unchanged from a fresh run folder, so that every output (model_round_k.pth, checkpoints/, logs) lands in
# experiments/zkpet/runs/<stamp>-fl-2clients/ and the clone stays untouched. Usage: bash env/run_fl.sh  (from experiments/zkpet)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"             # experiments/zkpet
REPO="$HERE/repo"; PY="$HERE/env/.venv/bin/python"
STAMP="$(date +%Y%m%d-%H%M%S)"; RUN="$HERE/runs/$STAMP-fl-2clients"
mkdir -p "$RUN"; cd "$RUN"
ln -s "$REPO/dataset" dataset                       # the scripts read ./dataset/electricity.csv relative to the cwd
export PYTHONPATH="$REPO"                           # import Linear_LTSF, models from the clone, unchanged
export PYTHONUNBUFFERED=1
{
  echo "run: $RUN"; echo "repo: $REPO ($(cd "$REPO" && git rev-parse --short HEAD))"; echo "python: $($PY --version)"
  echo "started: $(date -u +%FT%TZ)"; echo "command: server.py (num_rounds=3, FedAvg) + client_01_LTSF.py + client_02_LTSF.py"
} > RUN.md
"$PY" -u "$REPO/server.py" > server.log 2>&1 &
SERVER=$!
sleep 8                                             # let the Flower server bind 0.0.0.0:8080 before the clients connect
"$PY" -u "$REPO/client_01_LTSF.py" > client1.log 2>&1 &
C1=$!
"$PY" -u "$REPO/client_02_LTSF.py" > client2.log 2>&1 &
C2=$!
echo "pids: server $SERVER client1 $C1 client2 $C2" >> RUN.md
wait $SERVER; S=$?
wait $C1 || true; wait $C2 || true
echo "finished: $(date -u +%FT%TZ) server exit $S" >> RUN.md
echo "FL RUN FINISHED exit=$S run=$RUN"
