#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
TASK_BUILD=${1:-/tmp/dyson-native}
mkdir -p "$TASK_BUILD"
tar -xf "$TASK_ROOT/engine/vendor/rebound-4.6.0.tar.gz" -C "$TASK_BUILD"
TASK_SRC="$TASK_BUILD/rebound-4.6.0/src"
gcc -O3 -std=c99 -D_GNU_SOURCE -fPIC -shared -DLIBREBOUND -DCLOUD_TESTS -I"$TASK_SRC" "$TASK_ROOT/engine/cloud.c" "$TASK_SRC"/*.c -lm -o "$TASK_BUILD/cloud.so"
printf '%s\n' "$TASK_BUILD/cloud.so"
