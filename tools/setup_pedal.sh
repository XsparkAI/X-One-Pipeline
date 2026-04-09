#!/bin/bash

# 查找脚踏板设备节点的路径
# 逻辑：
# 1. 旧踏板匹配名称包含 "LinTx" 的 hidraw 设备；
# 2. 新 KM-key08 踏板优先选择键盘接口 bInterfaceNumber=00。
PEDAL_DEV=""

for dev in /dev/hidraw*; do
    SYS_NODE="/sys/class/hidraw/$(basename "$dev")"
    [ -e "$SYS_NODE" ] || continue

    REAL_NODE="$(readlink -f "$SYS_NODE")"
    HID_DEV_DIR="$(dirname "$(dirname "$REAL_NODE")")"
    IFACE_DIR="$(dirname "$HID_DEV_DIR")"
    UEvent_FILE="$HID_DEV_DIR/uevent"
    IFACE_FILE="$IFACE_DIR/bInterfaceNumber"

    if [ -f "$UEvent_FILE" ] && grep -q "LinTx" "$UEvent_FILE"; then
        PEDAL_DEV=$dev
        break
    fi

    if [ -f "$UEvent_FILE" ] && grep -q "HID_NAME=KM-key08" "$UEvent_FILE"; then
        if [ -f "$IFACE_FILE" ] && [ "$(cat "$IFACE_FILE")" = "00" ]; then
            PEDAL_DEV=$dev
            break
        fi
    fi
done

if [ -z "$PEDAL_DEV" ]; then
    echo "错误: 未找到脚踏板 hidraw 设备。"
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
