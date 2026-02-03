#!/usr/bin/env bash
set -euo pipefail

task_name="${1:?task_name required}"
collect_cfg="${2:?collect_cfg required}"
shift 2

python pipeline/collect.py \
  --task_name "${task_name}" \
  --collect_cfg "${collect_cfg}" \
  "$@"
