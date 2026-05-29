#!/usr/bin/env bash
set -euo pipefail

SESSION="teleop"

######################################
# 读取参数（命令行 / 交互）
######################################

task_name="${1:-}"
master_base_cfg="${2:-}"
slave_base_cfg="${3:-}"
port="${4:-}"

[ -z "$task_name" ] && read -p "task_name: " task_name
[ -z "$master_base_cfg" ] && read -p "master_base_cfg: " master_base_cfg
[ -z "$slave_base_cfg" ] && read -p "slave_base_cfg: " slave_base_cfg
[ -z "$port" ] && read -p "port: " port

######################################
# Conda 初始化（关键）
######################################

# ⚠️ 必须是 conda.sh，不是 conda activate 直接写
CONDA_SH="$HOME/miniconda3/etc/profile.d/conda.sh"
CONDA_ENV="Xone"

######################################
# tmux 启动
######################################

tmux has-session -t "$SESSION" 2>/dev/null && {
    echo "⚠️ tmux session $SESSION 已存在"
    exit 1
}

tmux new-session -d -s "$SESSION"

######################################
# Pane 1：Slave（后台）
######################################

tmux send-keys -t "$SESSION":0.0 "
source ${CONDA_SH} &&
conda activate ${CONDA_ENV} &&
echo '🚀 Slave started in conda ${CONDA_ENV}' &&
python pipeline/collect_teleop_slave.py \
  --task_name ${task_name} \
  --slave_base_cfg ${slave_base_cfg} \
  --port ${port}
" C-m

######################################
# Pane 2：Master（前台）
######################################

tmux split-window -h -t "$SESSION"

tmux send-keys -t "$SESSION":0.1 "
source ${CONDA_SH} &&
conda activate ${CONDA_ENV} &&
echo '🚀 Master started in conda ${CONDA_ENV}' &&
exec python pipeline/collect_teleop_master.py \
  --master_base_cfg ${master_base_cfg} \
  --port ${port}
" C-m

######################################
# 前台 attach（master 可直接操作）
######################################

tmux select-pane -t "$SESSION":0.1
tmux attach -t "$SESSION"
