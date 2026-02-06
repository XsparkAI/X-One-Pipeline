#!/usr/bin/env bash
# set -euo pipefail

task_name="test_teleop"
slave_base_cfg="x-one"
port="10001"
shift 3

python pipeline/collect_teleop_slave.py \
  --task_name "${task_name}" \
  --slave_base_cfg "${slave_base_cfg}" \
  --port "${port}"
  "$@"
