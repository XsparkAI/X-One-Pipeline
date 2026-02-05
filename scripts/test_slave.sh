#!/usr/bin/env bash
# set -euo pipefail

task_name="test_teleop"
robot_cfg="x-one"
collect_cfg="collect_sample"
port="10002"
shift 4

python pipeline/collect_teleop_slave.py \
  --task_name "${task_name}" \
  --slave_robot_cfg "${robot_cfg}" \
  --collect_cfg "${collect_cfg}" \
  --port "${port}"
  "$@"
