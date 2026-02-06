#!/usr/bin/env bash
# set -euo pipefail

master_base_cfg="x-one-master"
port="10001"
shift 2

python pipeline/collect_teleop_master.py \
  --master_base_cfg "${master_base_cfg}" \
  --port "${port}"
  "$@"
