#!/usr/bin/env bash
# set -euo pipefail

robot_cfg="x-one-master"
port="10002"
shift 2

python pipeline/collect_teleop_master.py \
  --master_robot_cfg "${robot_cfg}" \
  --port "${port}"
  "$@"
