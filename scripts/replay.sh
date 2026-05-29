#!/usr/bin/env bash
set -euo pipefail

task_name="${1:?task_name required}"
base_cfg="${2:?base_cfg required}"
idx="${3:?idx required}"
shift 3

python pipeline/replay.py \
  --task_name "${task_name}" \
  --base_cfg "${base_cfg}" \
  --idx "${idx}" \
  "$@"
