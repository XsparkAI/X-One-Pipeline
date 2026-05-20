#!/bin/bash

set -u

# 用法：
#   bash tools/set_pedal.sh --list
#   bash tools/set_pedal.sh [alias] [device_or_index]
# 示例：
#   bash tools/set_pedal.sh
#   bash tools/set_pedal.sh pedal_left
#   bash tools/set_pedal.sh pedal_left /dev/hidraw6
#   bash tools/set_pedal.sh pedal_left 1

ALIAS_NAME="pedal"
SELECTOR=""
LINK_PATH="/dev/$ALIAS_NAME"
RULE_PATH="/etc/udev/rules.d/99-x-one-pedal.rules"
PEDAL_DEV=""
RULE_LINE=""
CANDIDATE_COUNT=0

usage() {
    cat <<'EOF'
用法：
  bash tools/set_pedal.sh --list
  bash tools/set_pedal.sh [alias] [device_or_index]

参数：
  alias            绑定后的固定别名，默认 pedal，对应 /dev/pedal
  device_or_index  指定当前要绑定的脚踏板，可以传 /dev/hidrawN 或列表索引

说明：
  /dev/pedal_left 这类固定名称在 Linux 下本质就是一个符号链接，
  但它不是“写死到 hidraw 编号”，而是由 udev 按硬件属性或物理 USB 位置自动重建。
EOF
}

read_text_file() {
    local file_path="$1"
    if [ -f "$file_path" ]; then
        cat "$file_path"
    fi
}

list_candidates() {
    local index=0
    local dev sys_node real_node hid_dev_dir iface_dir usb_dev_dir
    local uevent_file iface_file hid_name vendor model serial usb_path label

    for dev in /dev/hidraw*; do
        sys_node="/sys/class/hidraw/$(basename "$dev")"
        [ -e "$sys_node" ] || continue

        real_node="$(readlink -f "$sys_node")"
        hid_dev_dir="$(dirname "$(dirname "$real_node")")"
        iface_dir="$(dirname "$hid_dev_dir")"
        usb_dev_dir="$(dirname "$iface_dir")"
        uevent_file="$hid_dev_dir/uevent"
        iface_file="$iface_dir/bInterfaceNumber"
        hid_name=""

        if [ -f "$uevent_file" ]; then
            hid_name="$(grep '^HID_NAME=' "$uevent_file" | head -n1 | cut -d= -f2-)"
        fi

        if [ -z "$hid_name" ]; then
            continue
        fi

        if [[ "$hid_name" != *LinTx* ]] && [[ "$hid_name" != "KM-key08" ]]; then
            continue
        fi

        if [[ "$hid_name" == "KM-key08" ]] && [ -f "$iface_file" ] && [ "$(cat "$iface_file")" != "00" ]; then
            continue
        fi

        vendor="$(read_text_file "$usb_dev_dir/idVendor")"
        model="$(read_text_file "$usb_dev_dir/idProduct")"
        serial="$(read_text_file "$usb_dev_dir/serial")"
        usb_path="$(basename "$usb_dev_dir")"
        label="$hid_name"
        if [ -n "$serial" ]; then
            label="$label serial=$serial"
        else
            label="$label path=$usb_path"
        fi

        printf '[%d] %s | vendor=%s product=%s | %s\n' "$index" "$dev" "${vendor:-unknown}" "${model:-unknown}" "$label"
        index=$((index + 1))
    done

    CANDIDATE_COUNT="$index"
}

resolve_selector() {
    local selector="$1"
    local index=0
    local dev sys_node real_node hid_dev_dir iface_dir uevent_file iface_file hid_name

    if [[ "$selector" == /dev/hidraw* ]]; then
        if [ -e "$selector" ]; then
            PEDAL_DEV="$selector"
            return 0
        fi
        echo "错误: 指定设备不存在: $selector"
        return 1
    fi

    if [[ "$selector" =~ ^[0-9]+$ ]]; then
        for dev in /dev/hidraw*; do
            sys_node="/sys/class/hidraw/$(basename "$dev")"
            [ -e "$sys_node" ] || continue

            real_node="$(readlink -f "$sys_node")"
            hid_dev_dir="$(dirname "$(dirname "$real_node")")"
            iface_dir="$(dirname "$hid_dev_dir")"
            uevent_file="$hid_dev_dir/uevent"
            iface_file="$iface_dir/bInterfaceNumber"
            hid_name=""

            if [ -f "$uevent_file" ]; then
                hid_name="$(grep '^HID_NAME=' "$uevent_file" | head -n1 | cut -d= -f2-)"
            fi

            if [ -z "$hid_name" ]; then
                continue
            fi

            if [[ "$hid_name" != *LinTx* ]] && [[ "$hid_name" != "KM-key08" ]]; then
                continue
            fi

            if [[ "$hid_name" == "KM-key08" ]] && [ -f "$iface_file" ] && [ "$(cat "$iface_file")" != "00" ]; then
                continue
            fi

            if [ "$index" = "$selector" ]; then
                PEDAL_DEV="$dev"
                return 0
            fi
            index=$((index + 1))
        done

        echo "错误: 找不到索引为 $selector 的脚踏板。"
        return 1
    fi

    echo "错误: 无效的 device_or_index 参数: $selector"
    return 1
}

find_pedal_device() {
    if [ -n "$SELECTOR" ]; then
        resolve_selector "$SELECTOR"
        return $?
    fi

    for dev in /dev/hidraw*; do
        SYS_NODE="/sys/class/hidraw/$(basename "$dev")"
        [ -e "$SYS_NODE" ] || continue

        REAL_NODE="$(readlink -f "$SYS_NODE")"
        HID_DEV_DIR="$(dirname "$(dirname "$REAL_NODE")")"
        IFACE_DIR="$(dirname "$HID_DEV_DIR")"
        UEVENT_FILE="$HID_DEV_DIR/uevent"
        IFACE_FILE="$IFACE_DIR/bInterfaceNumber"

        if [ -f "$UEVENT_FILE" ] && grep -q "LinTx" "$UEVENT_FILE"; then
            PEDAL_DEV="$dev"
            return 0
        fi

        if [ -f "$UEVENT_FILE" ] && grep -q "HID_NAME=KM-key08" "$UEVENT_FILE"; then
            if [ -f "$IFACE_FILE" ] && [ "$(cat "$IFACE_FILE")" = "00" ]; then
                PEDAL_DEV="$dev"
                return 0
            fi
        fi
    done

    return 1
}

build_udev_rule() {
    local sys_node real_node hid_dev_dir iface_dir usb_dev_dir props
    local iface_num iface_kernel vendor model serial id_path

    sys_node="/sys/class/hidraw/$(basename "$PEDAL_DEV")"
    real_node="$(readlink -f "$sys_node")"
    hid_dev_dir="$(dirname "$(dirname "$real_node")")"
    iface_dir="$(dirname "$hid_dev_dir")"
    usb_dev_dir="$(dirname "$iface_dir")"
    iface_num=""
    iface_kernel="$(basename "$iface_dir")"

    if [ -f "$iface_dir/bInterfaceNumber" ]; then
        iface_num="$(cat "$iface_dir/bInterfaceNumber")"
    fi

    props="$(udevadm info --query=property --name="$PEDAL_DEV")"
    vendor="$(printf '%s\n' "$props" | grep '^ID_VENDOR_ID=' | head -n1 | cut -d= -f2-)"
    model="$(printf '%s\n' "$props" | grep '^ID_MODEL_ID=' | head -n1 | cut -d= -f2-)"
    serial="$(printf '%s\n' "$props" | grep '^ID_SERIAL_SHORT=' | head -n1 | cut -d= -f2-)"
    id_path="$(printf '%s\n' "$props" | grep '^ID_PATH=' | head -n1 | cut -d= -f2-)"

    if [ -z "$vendor" ] && [ -f "$usb_dev_dir/idVendor" ]; then
        vendor="$(cat "$usb_dev_dir/idVendor")"
    fi
    if [ -z "$model" ] && [ -f "$usb_dev_dir/idProduct" ]; then
        model="$(cat "$usb_dev_dir/idProduct")"
    fi
    if [ -z "$serial" ] && [ -f "$usb_dev_dir/serial" ]; then
        serial="$(cat "$usb_dev_dir/serial")"
    fi

    if [ -z "$vendor" ] || [ -z "$model" ]; then
        echo "错误: 无法读取设备的 vendor/model 信息，不能生成稳定规则。"
        return 1
    fi

    RULE_LINE="SUBSYSTEM==\"hidraw\", KERNELS==\"$iface_kernel\", ATTRS{idVendor}==\"$vendor\", ATTRS{idProduct}==\"$model\""

    if [ -n "$serial" ]; then
        RULE_LINE="$RULE_LINE, ATTRS{serial}==\"$serial\""
    elif [ -n "$id_path" ]; then
        RULE_LINE="$RULE_LINE, ENV{ID_PATH}==\"$id_path\""
    elif [ -n "$iface_kernel" ]; then
        :
    else
        echo "错误: 设备既没有 serial，也没有 ID_PATH，无法安全绑定固定名称。"
        return 1
    fi

    RULE_LINE="$RULE_LINE, SYMLINK+=\"$ALIAS_NAME\", MODE=\"0777\""
    return 0
}

install_udev_rule() {
    local existing filtered

    existing=""
    if [ -f "$RULE_PATH" ]; then
        existing="$(sudo cat "$RULE_PATH")"
    fi

    filtered="$(printf '%s\n' "$existing" | grep -v "SYMLINK+=\"$ALIAS_NAME\"" || true)"

    {
        if [ -n "$filtered" ]; then
            printf '%s\n' "$filtered"
        fi
        printf '%s\n' "$RULE_LINE"
    } | sudo tee "$RULE_PATH" >/dev/null

    sudo udevadm control --reload-rules
    sudo udevadm trigger --action=add "$PEDAL_DEV"
}

create_runtime_link() {
    sudo ln -sfn "$PEDAL_DEV" "$LINK_PATH"
    sudo chmod 777 "$PEDAL_DEV"
}

if [ $# -gt 0 ] && [ "$1" = "--list" ]; then
    list_candidates
    if [ "$CANDIDATE_COUNT" -eq 0 ]; then
        echo "未找到可绑定的脚踏板。"
        exit 1
    fi
    exit 0
fi

if [ $# -gt 0 ] && { [ "$1" = "-h" ] || [ "$1" = "--help" ]; }; then
    usage
    exit 0
fi

if [ $# -ge 1 ]; then
    ALIAS_NAME="$1"
fi

if [ $# -ge 2 ]; then
    SELECTOR="$2"
fi

LINK_PATH="/dev/$ALIAS_NAME"

if ! find_pedal_device; then
    echo "错误: 未找到脚踏板 hidraw 设备。"
    echo
    echo "可先运行以下命令查看候选设备:"
    echo "  bash tools/set_pedal.sh --list"
    exit 1
fi

if [ -z "$SELECTOR" ]; then
    list_candidates
    if [ "$CANDIDATE_COUNT" -gt 1 ]; then
        echo "错误: 检测到多个脚踏板，请显式指定要绑定的设备或索引。"
        echo
        echo "示例:"
        echo "  bash tools/set_pedal.sh $ALIAS_NAME 0"
        echo "  bash tools/set_pedal.sh $ALIAS_NAME /dev/hidraw6"
        exit 1
    fi
fi

echo "检测到脚踏板设备: $PEDAL_DEV"
echo "准备绑定设备别名: $LINK_PATH"
echo "正在写入权限和绑定规则 (可能需要输入 sudo 密码)..."

if ! build_udev_rule; then
    exit 1
fi

if ! create_runtime_link; then
    echo "错误: 创建当前会话绑定失败。"
    exit 1
fi

if ! install_udev_rule; then
    echo "错误: 写入 udev 规则失败。"
    exit 1
fi

echo "成功！现在可以通过 $LINK_PATH 访问脚踏板。"
echo "当前真实设备: $PEDAL_DEV"
echo "规则文件: $RULE_PATH"