#!/bin/bash
# FL-BC-IDS runs, each in a fresh container of the image env/build.sh made, with the clone mounted read-only and copied
# into the container's scratch space (so the repository's scripts can write their artefacts next to themselves without
# touching the clone), the data folder mounted read-write, and the run folder collecting outputs and run.log.
# Tasks:  checks   the repository's integrity scripts and the cryptographic verification of its retained Groth16 proofs
#         primary  the documented primary configuration (2 RSUs x 2 vehicles, 2 rounds, DP on) on one data set
#         expanded the expanded topology of the paper (10 RSUs x 20 vehicles = 200 vehicles, 2 rounds, DP on)
#         topology the topology given in FLBCIDS_NUM_RSUS / FLBCIDS_VEHICLES_PER_RSU / FLBCIDS_NUM_ROUNDS / FLBCIDS_NUM_LOCAL_ROUNDS (the scale sweep)
#         prep     the repository's deterministic preprocessing of a raw data set placed under data/raw/
#         shell    an interactive shell in the environment
# Usage (from experiments/fl-bc-ids): bash env/run.sh <task> <run folder> [dataset: CICIoV2024|CSECICIDS2018]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; TASK="${1:-checks}"; RUN="${2:-$HERE/runs/$(date +%Y%m%d-%H%M%S)-$TASK}"; DS="${3:-CICIoV2024}"
mkdir -p "$RUN" "$HERE/data/raw" "$HERE/data/preprocessed"
export DOCKER_CONTEXT="colima-${FLBCIDS_COLIMA_PROFILE:-flbcids}"
PLATFORM="${FLBCIDS_PLATFORM:-arm64}"; IMAGE="flbcids-env:$PLATFORM"
cat > "$RUN/RUN.md" <<EOF
run: $RUN
task: $TASK  dataset: $DS
image: $IMAGE ($(grep "$IMAGE" "$HERE/env/IMAGE_BUILT" 2>/dev/null || echo 'not built'))
repo: $HERE/repo ($(cd "$HERE/repo" && git rev-parse --short HEAD)), mounted read-only and copied to /work/repo in the container
started: $(date -u +%FT%TZ)
EOF
# inside the container: copy the clone, point every repository output and data path at the mounted folders, run the task
INNER='set -euo pipefail
test -f /mnt/repo/README.md || { echo "the clone is not visible in the container (VM mount missing: rerun env/build.sh)"; exit 3; }
cp -r /mnt/repo /work/repo && cd /work/repo
CE=/work/repo/experiments/08_compact_security_evidence/CSECICIDS2018/verification_evidence
[ -f "$CE/onchain_export/latest_run_index_v1.json" ] && export FLBCIDS_COMPACT_EVIDENCE_DIR="$CE"
export FLBCIDS_REPO_ROOT=/work/repo FLBCIDS_CSE_RAW_CSV=/work/data/raw/CSE-CIC-IDS2018/CSECICIDS2018Dataset.csv FLBCIDS_CICIOV_RAW_DIR=/work/data/raw/CICIoV2024 \
       FLBCIDS_CSE_PREPROC_DIR=/work/data/preprocessed/CSE-CIC-IDS2018 FLBCIDS_CICIOV_PREPROC_DIR=/work/data/preprocessed/CICIoV2024 \
       FLBCIDS_DP_OUTPUT_DIR=/work/out/dp FLBCIDS_NONDP_OUTPUT_DIR=/work/out/nondp FLBCIDS_CENTRALIZED_OUTPUT_DIR=/work/out/centralized \
       FLBCIDS_TEMPORAL_RESULTS_DIR=/work/out/temporal FLBCIDS_COMMENT4_RESULTS_DIR=/work/out/comment4 FLBCIDS_DATASET_NAME="$DS"
mkdir -p /work/out
echo "== python $(python --version) | node $(node --version) | circom $(circom --version) | snarkjs $(node /opt/node-env/node_modules/.bin/snarkjs --version 2>/dev/null | head -1)"
case "$TASK" in
  checks)
    echo "== scripts/build_release_inventory.py --check"; python scripts/build_release_inventory.py --check 2>&1 | tail -25 || true
    for s in release_self_check.py verify_checksums.py verify_blockchain_evidence.py; do
      echo "== scripts/$s"; python scripts/$s 2>&1 | tail -15 || true; done
    ln -s /opt/node-env/node_modules /work/repo/environment/node_modules      # where verify_groth16.py looks for snarkjs (container copy only; after the release checks, which forbid symlinks)
    echo "== scripts/verify_groth16.py --structural-only"; python scripts/verify_groth16.py --structural-only 2>&1 | tail -10 || true
    echo "== scripts/verify_groth16.py (cryptographic, snarkjs)"; time python scripts/verify_groth16.py 2>&1 | tail -15 || true
    echo "== code/verification/DryRunRSU-GlobalSrver-SSI-Verification_V10.py (public release layout)"; python code/verification/DryRunRSU-GlobalSrver-SSI-Verification_V10.py 2>&1 | tail -15 || true
    # the public JSON artefacts were path-sanitised, which changed their bytes; the exact original bytes are embedded in
    # HISTORICAL_ORIGINAL_BYTES.zip (HASH_SEMANTICS.json), so the SHA-pinned check is repeated against that archive
    mkdir -p /work/hist && python -c "import zipfile; zipfile.ZipFile(\"experiments/08_compact_security_evidence/HISTORICAL_ORIGINAL_BYTES.zip\").extractall(\"/work/hist\")"
    H=$(find /work/hist -type f -name latest_run_index_v1.json | head -1); H=${H%/onchain_export/*}
    echo "== the same dry-run verification against the embedded original bytes ($H)"; FLBCIDS_COMPACT_EVIDENCE_DIR="$H" python code/verification/DryRunRSU-GlobalSrver-SSI-Verification_V10.py 2>&1 | tail -15 || true ;;
  prep)
    if [ "$DS" = "CICIoV2024" ]; then python data_preparation/CICIoV2024/preprocess_ciciov2024_decimal.py; else python data_preparation/CSECICIDS2018/DatasetPreprocessing-V2.py; fi ;;
  primary|expanded|topology)
    # the core runner reads its topology from FLBCIDS_NUM_RSUS, FLBCIDS_VEHICLES_PER_RSU, FLBCIDS_NUM_ROUNDS, FLBCIDS_NUM_LOCAL_ROUNDS
    # (code defaults 10 / 20 / 2 / 10 = the expanded 200-vehicle topology); the documented primary configuration is 2 / 2 / 2 / 10;
    # "topology" takes the four values from the caller (the scale sweep)
    if [ "$TASK" = primary ]; then export FLBCIDS_NUM_RSUS=2 FLBCIDS_VEHICLES_PER_RSU=2 FLBCIDS_NUM_ROUNDS=2 FLBCIDS_NUM_LOCAL_ROUNDS=10
    elif [ "$TASK" = expanded ]; then export FLBCIDS_NUM_RSUS=10 FLBCIDS_VEHICLES_PER_RSU=20 FLBCIDS_NUM_ROUNDS=2 FLBCIDS_NUM_LOCAL_ROUNDS=10
    else export FLBCIDS_NUM_RSUS="${FLBCIDS_NUM_RSUS:-2}" FLBCIDS_VEHICLES_PER_RSU="${FLBCIDS_VEHICLES_PER_RSU:-2}" FLBCIDS_NUM_ROUNDS="${FLBCIDS_NUM_ROUNDS:-2}" FLBCIDS_NUM_LOCAL_ROUNDS="${FLBCIDS_NUM_LOCAL_ROUNDS:-10}"; fi
    echo "== $TASK configuration: $FLBCIDS_NUM_RSUS RSUs x $FLBCIDS_VEHICLES_PER_RSU vehicles, $FLBCIDS_NUM_ROUNDS global rounds, $FLBCIDS_NUM_LOCAL_ROUNDS local rounds, DP on, data set $DS"
    # the published core runner lacks "from pathlib import Path" and "import logging" (pyflakes: the only two undefined
    # names); it is run unchanged through runpy with both supplied and its own folder on the import path
    set +e; T0=$(date +%s)
    python -c "import sys; sys.path.insert(0, \"code/core\"); from pathlib import Path; import runpy; import logging; runpy.run_path(\"code/core/FL_DP_SSI_DualMerklePoseidon_RSU+Global_ZKVerify_V10.py\", init_globals={\"Path\": Path, \"logging\": logging}, run_name=\"__main__\")" > /work/run/runner.log 2>&1
    RC=$?; set -e; echo "runner exit code $RC after $(( $(date +%s) - T0 )) s (full output in runner.log)"; tail -40 /work/run/runner.log ;;
  shell) bash ;;
  *) echo "unknown task $TASK"; exit 2 ;;
esac
cp -r /work/out/. /work/run/out/ 2>/dev/null || true
echo "TASK DONE: $TASK"'
docker run --rm --platform "linux/$PLATFORM" --shm-size=8g -e TASK="$TASK" -e DS="$DS" -e ANCHOR_ZKP_PTAU_PATH=/work/ptau/powersOfTau28_hez_final_20.ptau \
  -e FLBCIDS_NUM_RSUS -e FLBCIDS_VEHICLES_PER_RSU -e FLBCIDS_NUM_ROUNDS -e FLBCIDS_NUM_LOCAL_ROUNDS \
  -v "$HERE/repo:/mnt/repo:ro" -v "$HERE/data:/work/data" -v "$RUN:/work/run" -v "$HERE/env/ptau:/work/ptau:ro" \
  $( [ "$TASK" = shell ] && echo -it ) "$IMAGE" bash -c "$INNER"
S=$?
echo "finished: $(date -u +%FT%TZ) exit $S" >> "$RUN/RUN.md"
echo "RUN FINISHED exit=$S task=$TASK run=$RUN"
