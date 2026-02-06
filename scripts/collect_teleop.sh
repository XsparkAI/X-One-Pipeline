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

if [ -z "${task_name}" ]; then
    read -p "请输入 task_name: " task_name
fi

if [ -z "${master_robot_cfg}" ]; then
    read -p "请输入 master_robot_cfg (如 x-one-master): " master_robot_cfg
fi

if [ -z "${slave_robot_cfg}" ]; then
    read -p "请输入 slave_robot_cfg (如 x-one): " slave_robot_cfg
fi

if [ -z "${collect_cfg}" ]; then
    read -p "请输入 collect_cfg (如 collect-30hz): " collect_cfg
fi

if [ -z "${port}" ]; then
    read -p "请输入端口 port (如 10002): " port
fi

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
# 启动 master（server）
######################################

echo "🚀 启动 Teleop Master (server)..."

python pipeline/collect_teleop_master.py \
    --master_robot_cfg "${master_robot_cfg}" \
    --port "${port}" \
    &

MASTER_PID=$!

echo "✅ Master PID: ${MASTER_PID}"

# 给 server 一点启动时间
sleep 2

######################################
# 启动 slave（client）
######################################

echo "🚀 启动 Teleop Slave (client)..."

python pipeline/collect_teleop_slave.py \
    --task_name "${task_name}" \
    --slave_robot_cfg "${slave_robot_cfg}" \
    --collect_cfg "${collect_cfg}" \
    --port "${port}"

######################################
# 退出清理
######################################

echo
echo "🛑 Slave 退出，正在关闭 Master..."
kill "${MASTER_PID}" 2>/dev/null || true
wait "${MASTER_PID}" 2>/dev/null || true
echo "✅ Teleop 结束"
