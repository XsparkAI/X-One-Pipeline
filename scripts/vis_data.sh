#!/usr/bin/env bash
set -euo pipefail

# -------------------------------
# Parameters
# -------------------------------
task_name="${1:?task_name required}"        # 任务名，可选，但脚本要求
collect_cfg="${2:?collect_cfg required}"    # 配置文件名（不带 .yml）
idx="${3:?idx required}"                    # 数据索引
shift 3

# -------------------------------
# Optional flags
# -------------------------------
collect=false
collect_idx=""
extra_args=()

# 遍历剩余参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --collect)
            collect=true
            shift
            ;;
        --collect_idx)
            collect_idx="$2"
            shift 2
            ;;
        *)
            extra_args+=("$1")
            shift
            ;;
    esac
done

# -------------------------------
# 构造 Python 命令
# -------------------------------
cmd=(python pipeline/replay.py --collect_cfg "$collect_cfg" --idx "$idx")

# task_name 可选
if [[ -n "$task_name" ]]; then
    cmd+=(--task_name "$task_name")
fi

# collect flag
if [[ "$collect" = true ]]; then
    cmd+=(--collect)
    if [[ -n "$collect_idx" ]]; then
        cmd+=(--collect_idx "$collect_idx")
    else
        echo "Error: --collect requires --collect_idx"
        exit 1
    fi
fi

# 额外参数原样传递
cmd+=("${extra_args[@]}")

# -------------------------------
# 执行
# -------------------------------
"${cmd[@]}"
