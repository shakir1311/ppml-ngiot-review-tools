#!/bin/bash
# Starts the experiment's own local EVM (anvil from env/foundry, port 3030, as the zkPET notebooks expect), logs its
# accounts and keys to <run>/anvil.log, and writes the pid to <run>/anvil.pid. Usage: bash env/start_anvil.sh <run folder>
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; RUN="$1"; mkdir -p "$RUN"
if curl -s -m 2 -X POST -H 'content-type: application/json' --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' http://127.0.0.1:3030 >/dev/null 2>&1; then
  echo "anvil already listening on 3030"; exit 0
fi
nohup "$HERE/env/foundry/anvil" --port 3030 > "$RUN/anvil.log" 2>&1 &
echo $! > "$RUN/anvil.pid"
for i in $(seq 1 30); do
  if curl -s -m 2 -X POST -H 'content-type: application/json' --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' http://127.0.0.1:3030 >/dev/null 2>&1; then
    echo "anvil up on 3030 (pid $(cat "$RUN/anvil.pid"))"; exit 0
  fi; sleep 1
done
echo "anvil did not come up"; exit 1
