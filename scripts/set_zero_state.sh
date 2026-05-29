#!/bin/bash

# 检查输入参数
if [ "$#" -ne 2 ]; then
    echo "使用方法: $0 <CAN接口号> <关节号>"
    echo "示例: $0 0 1  (对应 can0 关节1)"
    exit 1
fi

CAN_ID=$1
JOINT_ID=$2

# 格式化关节ID为3位十六进制（例如 1 -> 001）
FORMATTED_JOINT=$(printf "%03d" $JOINT_ID)

echo "正在向 can${CAN_ID} 的关节 ${JOINT_ID} 发送置零指令..."
cansend "can${CAN_ID}" "${FORMATTED_JOINT}#FFFFFFFFFFFFFFFE"