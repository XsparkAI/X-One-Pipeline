#!/usr/bin/env bash
set -euo pipefail

task_name="${1:?task_name required}"
collect_cfg="${2:?collect_cfg required}"
idx="${3:?idx required}"
save_path="${4:-}"
shift 4

python pipeline/vis_data.py \
  --task_name "${task_name}" \
  --collect_cfg "${collect_cfg}" \
  --idx "${idx}" \
  --save_path "${save_path}" \
  "$@"