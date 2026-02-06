#!/usr/bin/env bash
set -euo pipefail

######################################
# 参数读取（支持命令行 / 交互）
######################################

task_name="${1:-}"
master_robot_cfg="${2:-}"
slave_robot_cfg="${3:-}"
collect_cfg="${4:-}"
port="${5:-}"

[ -z "${task_name}" ] && read -p "请输入 task_name: " task_name
[ -z "${master_robot_cfg}" ] && read -p "请输入 master_robot_cfg: " master_robot_cfg
[ -z "${slave_robot_cfg}" ] && read -p "请输入 slave_robot_cfg: " slave_robot_cfg
[ -z "${collect_cfg}" ] && read -p "请输入 collect_cfg: " collect_cfg
[ -z "${port}" ] && read -p "请输入端口 port: " port

echo
echo "================ 配置确认 ================"
echo "task_name        : ${task_name}"
echo "master_robot_cfg : ${master_robot_cfg}"
echo "slave_robot_cfg  : ${slave_robot_cfg}"
echo "collect_cfg      : ${collect_cfg}"
echo "port             : ${port}"
echo "========================================="
echo

######################################
# 启动 slave（server，后台）
######################################

echo "🚀 启动 Teleop Slave (server, 后台)..."

python pipeline/collect_teleop_slave.py \
    --task_name "${task_name}" \
    --slave_robot_cfg "${slave_robot_cfg}" \
    --collect_cfg "${collect_cfg}" \
    --port "${port}" \
    &

SLAVE_PID=$!
echo "✅ Slave PID: ${SLAVE_PID}"

# 等 slave socket ready（经验值）
sleep 2

######################################
# 启动 master（client，前台）
######################################

echo "🚀 启动 Teleop Master (client, 前台)..."
echo "👉 Ctrl+C 将结束整个 Teleop"

python pipeline/collect_teleop_master.py \
    --master_robot_cfg "${master_robot_cfg}" \
    --port "${port}"

######################################
# 清理（master 退出后自动执行）
######################################

echo
echo "🛑 Master 已退出，关闭 Slave..."
kill "${SLAVE_PID}" 2>/dev/null || true
wait "${SLAVE_PID}" 2>/dev/null || true

echo "✅ Teleop 结束"
