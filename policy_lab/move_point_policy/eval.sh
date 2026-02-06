#!/usr/bin/env bash
set -euo pipefail

# lib.sh is in parent directory of this deploy.sh
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"

policy_name="move_point_policy"
task_name="${1:?task_name required}"
collect_cfg="${2:?collect_cfg required}"
robot_cfg="${3:?robot_cfg required}"
ckpt_setting="${4:?ckpt_setting required}"
gpu_id="${5:?gpu_id required}"
policy_conda_env="${6:?policy_conda_env required}"
sim_conda_env="${7:?sim_conda_env required}"
seed="${8:-0}"

export CUDA_VISIBLE_DEVICES="$gpu_id"

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_root"

yaml_file="policy_lab/${policy_name}/deploy.yml"
port="$(get_free_port)"

logi "GPU: $gpu_id"
logi "YAML: $yaml_file"
logi "PORT: $port"

conda_bootstrap
setup_trap_cleanup

# ---- server (background) ----
logs "conda: ${policy_conda_env}"
conda_on "$policy_conda_env"
logs "start server..."
server_pid="$(bg_run env PYTHONWARNINGS=ignore::UserWarning \
  python policy_lab/setup_policy_server.py \
    --port "$port" \
    --config_path "$yaml_file" \
    --overrides \
    --task_name "$task_name" \
    --collect_cfg "$collect_cfg" \
    --robot_cfg "$robot_cfg" \
    --ckpt_setting "$ckpt_setting" \
    --seed "$seed" \
    --policy_name "$policy_name"
)"
logs "PID=${server_pid}"

# ---- client (foreground) ----
conda_off
logc "conda: ${sim_conda_env}"
conda_on "$sim_conda_env"
logc "connect :${port}"

env PYTHONWARNINGS=ignore::UserWarning \
python pipeline/deploy.py \
  --task_name "$task_name" \
  --policy_name "$policy_name" \
  --collect_cfg "$collect_cfg" \
  --robot_cfg "$robot_cfg" \
  --port "$port"

logi "Done."
