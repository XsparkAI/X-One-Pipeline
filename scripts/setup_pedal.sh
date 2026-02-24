#!/bin/bash

# 查找脚踏板设备节点的路径
# 逻辑：遍历 hidraw 设备，找到名称包含 "LinTx" 的设备
PEDAL_DEV=""

for dev in /dev/hidraw*; do
    if [ -e "/sys/class/hidraw/$(basename $dev)/device/uevent" ]; then
        if grep -q "LinTx" "/sys/class/hidraw/$(basename $dev)/device/uevent"; then
            PEDAL_DEV=$dev
            break
        fi
    fi
done

if [ -z "$PEDAL_DEV" ]; then
    echo "错误: 未找到 LinTx 脚踏板设备。"
    exit 1
fi

echo "检测到脚踏板设备: $PEDAL_DEV"

# 赋予当前用户读取权限
echo "正在赋予权限 (可能需要输入 sudo 密码)..."
sudo chmod a+r $PEDAL_DEV

if [ $? -eq 0 ]; then
    echo "成功！现在你可以直接运行 python 脚本而无需 sudo 了。"
    echo "设备路径: $PEDAL_DEV"
else
    echo "权限赋予失败。"
    exit 1
fi
