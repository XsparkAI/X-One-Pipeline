#!/usr/bin/env bash
set -euo pipefail

task_name="${1:?task_name required}"
collect_cfg="${2:?collect_cfg required}"
robot_cfg="${3:?robot_cfg required}"
idx="${4:?idx required}"
save_path="${5:-}"
shift 5

python pipeline/vis_data.py \
  --task_name "${task_name}" \
  --collect_cfg "${collect_cfg}" \
  --robot_cfg "${robot_cfg}" \
  --idx "${idx}" \
  --save_path "${save_path}" \
  "$@"