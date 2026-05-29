#!/usr/bin/env bash
# set -euo pipefail

task_name="${1:?task_name required}"
base_cfg="${2:?base_cfg required}"
shift 2


for idx in {0..99}; do
  save_path="./data/${task_name}/${base_cfg}/video/episode${idx}.mp4" 
  
  python pipeline/vis_data.py \
    --task_name "${task_name}" \
    --base_cfg "${base_cfg}" \
    --idx "${idx}" \
    --save_path "${save_path}" \
    "$@"
done