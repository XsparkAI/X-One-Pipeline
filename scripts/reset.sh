#!/usr/bin/env bash
set -euo pipefail

robot_cfg="${1:?robot_cfg required}"

python pipeline/reset.py --robot_cfg "${robot_cfg}"
