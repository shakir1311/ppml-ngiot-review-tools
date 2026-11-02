#!/bin/bash
# zkPET run 4: the paper's own per-site measurement repeated with the ezkl command-line binary (9.5.0) and the system
# time command, as src/electricity_decentralized_ZKML.sh does (gen-settings, calibrate-settings, srs, compile-circuit,
# setup, gen-witness, prove under /usr/bin/time), on the ONNX models and inputs that run 2 exported. macOS's time has no
# -v; -l prints the maximum resident set size in bytes, which is the same figure. Clone untouched.
# Usage (from experiments/zkpet): bash env/zk_cli_sites.sh <run-2 folder with site*_sl*/network.onnx> [repeats]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; SRC="$(cd "$1" && pwd)"; REP="${2:-5}"
export PATH="$HERE/env/bin:$PATH"
RUN="$HERE/runs/$(date +%Y%m%d-%H%M%S)-zk-cli-sites"; mkdir -p "$RUN"; cd "$RUN"
exec > >(tee -a "$RUN/run.log") 2>&1
echo "run: $RUN"; echo "source models: $SRC"; echo "ezkl: $(ezkl --version)"; echo "started: $(date -u +%FT%TZ)"
echo "site,seq_len,prove_wall_s,max_rss_mb,proof_kb,setup_wall_s,logrows" > cli_perf.csv
for d in "$SRC"/site*_sl*; do
  name=$(basename "$d"); site=${name#site}; site=${site%%_*}; sl=${name##*_sl}
  w="$RUN/$name"; mkdir -p "$w"; cp "$d/network.onnx" "$d/input.json" "$w/"; cd "$w"
  echo "== $name  $(date +%H:%M:%S)"
  ezkl gen-settings -M network.onnx --input-visibility private --output-visibility public --param-visibility fixed >/dev/null 2>&1
  ezkl calibrate-settings -M network.onnx -D input.json --target resources >/dev/null 2>&1
  logrows=$(python3 -c "import json; print(json.load(open('settings.json'))['run_args']['logrows'])")
  if ! ezkl get-srs --srs-path kzg.srs -S settings.json >/dev/null 2>&1; then ezkl gen-srs --srs-path kzg.srs --logrows "$logrows" >/dev/null 2>&1; echo "   srs generated locally (logrows $logrows)"; fi
  ezkl compile-circuit -M network.onnx -S settings.json --compiled-circuit network.ezkl >/dev/null 2>&1
  t0=$(date +%s.%N); ezkl setup -M network.ezkl --srs-path kzg.srs --vk-path vk.key --pk-path pk.key >/dev/null 2>&1; t1=$(date +%s.%N)
  setup_s=$(python3 -c "print(round($t1-$t0,2))")
  ezkl gen-witness -D input.json -M network.ezkl -O witness.json >/dev/null 2>&1
  for i in $(seq 1 "$REP"); do
    /usr/bin/time -l ezkl prove --witness witness.json -M network.ezkl --proof-path model.pf --pk-path pk.key --srs-path kzg.srs > /dev/null 2> "perf_$i.txt" || true
    real=$(awk '/real/{print $1}' "perf_$i.txt"); rss=$(awk '/maximum resident set size/{print $1}' "perf_$i.txt")
    rss_mb=$(python3 -c "print(round(${rss:-0}/1048576,1))"); kb=$(python3 -c "import os; print(round(os.path.getsize('model.pf')/1024,3))")
    echo "   proof $i/$REP: ${real}s wall, ${rss_mb} MB max RSS, ${kb} KB"
    echo "$site,$sl,$real,$rss_mb,$kb,$setup_s,$logrows" >> "$RUN/cli_perf.csv"
  done
  ezkl verify --proof-path model.pf --settings-path settings.json --vk-path vk.key --srs-path kzg.srs >/dev/null 2>&1 && echo "   verified off chain" || echo "   VERIFY FAILED"
  cd "$RUN"
done
echo "finished: $(date -u +%FT%TZ)"; echo "ALL DONE: $(($(wc -l < cli_perf.csv)-1)) proofs -> $RUN/cli_perf.csv"
