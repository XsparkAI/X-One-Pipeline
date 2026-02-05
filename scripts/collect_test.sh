#!/usr/bin/env bash
# set -euo pipefail

task_name="test"
robot_cfg="x-one"
collect_cfg="collect_sample"
shift 3

python pipeline/collect_node.py \
  --task_name "${task_name}" \
  --robot_cfg "${robot_cfg}" \
  --collect_cfg "${collect_cfg}" \
  "$@"
