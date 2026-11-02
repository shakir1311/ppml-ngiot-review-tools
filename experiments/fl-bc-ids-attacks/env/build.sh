#!/bin/bash
# FL-BC-IDS environment, built once: a Colima VM named "flbcids" (arm64 with Rosetta, so amd64 containers run near native speed) with its own Docker
# daemon, and the image "flbcids-attacks-env" from env/Dockerfile (Python 3.12.10 with the repository's pinned packages,
# dp-xgboost built from source, Node 24 + locked snarkjs/circomlib, circom 2.1.8). Idempotent: rerunning skips what exists.
# Writes env/IMAGE_BUILT when the image is ready (the portal reads it) and env/build.log. Usage: bash env/build.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; ENV="$HERE/env"; REPO="$HERE/repo"
PROFILE="${FLBCIDS_COLIMA_PROFILE:-flbcids}"
PLATFORM="${FLBCIDS_PLATFORM:-arm64}"                      # arm64 (native; default) or amd64 (Rosetta; Ray's object store fails under it)
IMAGE="flbcids-attacks-env:$PLATFORM"; DOCKERFILE="$ENV/Dockerfile$( [ "$PLATFORM" = arm64 ] && echo .arm64 )"
exec > >(tee -a "$ENV/build.log") 2>&1
echo "== build started $(date -u +%FT%TZ)"
# 1. the VM, with Rosetta so that the Linux x86_64 wheels and the source builds behave as on the authors' machines
EXPERIMENTS="$(cd "$HERE/.." && pwd)"                       # must be mounted into the VM: Colima mounts only $HOME by default
if colima status -p "$PROFILE" >/dev/null 2>&1 && ! colima ssh -p "$PROFILE" -- test -d "$EXPERIMENTS/fl-bc-ids/repo" >/dev/null 2>&1; then
  echo "colima profile '$PROFILE' running without the experiments mount; restarting it with the mount"
  colima stop -p "$PROFILE"
fi
if colima status -p "$PROFILE" >/dev/null 2>&1; then
  echo "colima profile '$PROFILE' already running"
else
  # an arm64 VM with Rosetta: Docker inside it runs linux/amd64 containers through Rosetta at near-native speed
  # (an --arch x86_64 VM would need QEMU emulation and a guest agent Homebrew's Lima does not ship)
  echo "starting colima profile '$PROFILE' (arm64 VM, vz + rosetta for amd64 containers, 8 CPUs, 16 GiB, 80 GiB disk)"
  colima start -p "$PROFILE" --vm-type vz --vz-rosetta --cpu 8 --memory 16 --disk 80 --runtime docker --mount "$EXPERIMENTS:w"
fi
export DOCKER_CONTEXT="colima-$PROFILE"
docker context ls --format '{{.Name}}' | grep -qx "$DOCKER_CONTEXT" || { echo "docker context $DOCKER_CONTEXT missing"; exit 1; }
docker version --format 'docker server {{.Server.Version}} ({{.Server.Os}}/{{.Server.Arch}})'
# 2. the build context: only the repository's dependency files, copied (the clone is not touched)
mkdir -p "$ENV/node-env"
cp "$REPO/environment/package.json" "$REPO/environment/package-lock.json" "$ENV/node-env/"
cp "$REPO/environment/requirements-repro.txt" "$ENV/requirements-repro.txt"
# 3. the image
if docker image inspect "$IMAGE" >/dev/null 2>&1 && grep -q "$IMAGE" "$ENV/IMAGE_BUILT" 2>/dev/null; then
  echo "image $IMAGE already built ($(grep "$IMAGE" "$ENV/IMAGE_BUILT"))"
else
  echo "building $IMAGE from $(basename "$DOCKERFILE") (dp-xgboost compiles from source; this takes a while)"
  docker build --platform "linux/$PLATFORM" -t "$IMAGE" -f "$DOCKERFILE" "$ENV"
  echo "$(date -u +%FT%TZ) $IMAGE $(docker image inspect "$IMAGE" --format '{{.Id}}')" >> "$ENV/IMAGE_BUILT"
fi
echo "== build finished $(date -u +%FT%TZ)"; echo "BUILD DONE"
