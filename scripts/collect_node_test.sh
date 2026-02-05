#!/usr/bin/env bash
set -euo pipefail

task_name="${1:?task_name required}"
robot_cfg="${2:?robot_cfg required}"
collect_cfg="${3:?collect_cfg required}"
shift 3

python pipeline/collect_node.py \
  --task_name "${task_name}" \
  --robot_cfg "${robot_cfg}" \
  --collect_cfg "${collect_cfg}" \
  "$@"
