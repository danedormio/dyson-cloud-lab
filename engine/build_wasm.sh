#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
TASK_BUILD=${1:-/tmp/dyson-wasm}
mkdir -p "$TASK_BUILD" "$TASK_ROOT/static/engine"
(cd "$TASK_ROOT" && echo '46e2edda7c6e88444e8c7dd095aa4040f558079a19f62d918d56c0d68b9500e3  engine/vendor/rebound-4.6.0.tar.gz' | sha256sum -c -)
tar -xf "$TASK_ROOT/engine/vendor/rebound-4.6.0.tar.gz" -C "$TASK_BUILD"
TASK_SRC="$TASK_BUILD/rebound-4.6.0/src"
emcc -O3 -flto -ffp-contract=off -std=c99 -D_GNU_SOURCE -DLIBREBOUND -I"$TASK_SRC" "$TASK_ROOT/engine/cloud.c" "$TASK_SRC"/*.c -lm -sMODULARIZE=1 -sEXPORT_NAME=createCloudEngine -sENVIRONMENT=worker,node -sSINGLE_FILE=1 -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=67108864 -sSTACK_SIZE=1048576 -sFILESYSTEM=0 -sEXPORTED_FUNCTIONS='["_cloud_reset","_cloud_exact","_cloud_coordination","_cloud_launch","_cloud_advance","_cloud_save","_cloud_snapshot","_cloud_restore","_cloud_state","_cloud_output"]' -o "$TASK_ROOT/static/engine/cloud-engine.js"
python3 "$TASK_ROOT/engine/package_build.py"
