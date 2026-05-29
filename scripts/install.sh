#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TP_DIR="${REPO_ROOT}/third_party"

cd "$REPO_ROOT"

# ================================
# 1) 安装本仓库（editable）
# ================================
echo "👉 pip install -e ${REPO_ROOT}"
pip install -e .

mkdir -p "$TP_DIR"
cd "$TP_DIR"

# ================================
# 2) 选择 ROS 版本（设置 ROS_DISTRO，Y1 使用 ROS_BRANCH）
# ================================
while true; do
    echo
    echo "请选择 ROS 版本："
    echo "  1) noetic"
    echo "  2) humble"
    echo "  3) 使用鱼香 ROS 安装 ROS（安装完成后再选择 1、2 或 4）"
    echo "  4) ROS 已安装，跳过（用环境变量 ROS_DISTRO 或自动检测 /opt/ros）"
    read -p "请输入 1 / 2 / 3 / 4: " ros_choice

    case "${ros_choice}" in
        1)
            ROS_DISTRO="noetic"
            ROS_BRANCH="noetic_mit_control"
            echo "👉 使用 noetic (ROS_DISTRO=${ROS_DISTRO}, y1 分支 ${ROS_BRANCH})"
            break
            ;;
        2)
            ROS_DISTRO="humble"
            ROS_BRANCH="humble_mit_control"
            echo "👉 使用 humble (ROS_DISTRO=${ROS_DISTRO}, y1 分支 ${ROS_BRANCH})"
            break
            ;;
        3)
            echo "👉 使用鱼香 ROS 安装 ROS"
            cd ~

            wget http://fishros.com/install -O fishros

            set +e
            bash fishros
            set -e

            cd "${TP_DIR}" > /dev/null
            echo
            echo "✅ ROS 安装流程结束，请重新选择 1、2 或 4"
            ;;
        4)
            echo "👉 ROS 已安装，跳过安装向导；确定 ROS_DISTRO（供 Piper 等可选步骤使用）"
            if [ -n "${ROS_DISTRO:-}" ]; then
                case "${ROS_DISTRO}" in
                    noetic|humble)
                        echo "    使用环境变量 ROS_DISTRO=${ROS_DISTRO}"
                        ;;
                    *)
                        echo "❌ 环境变量 ROS_DISTRO=${ROS_DISTRO} 不是 noetic/humble，请 unset 后重试或选 1/2"
                        continue
                        ;;
                esac
            else
                has_noetic=0
                has_humble=0
                [ -d /opt/ros/noetic ] && has_noetic=1
                [ -d /opt/ros/humble ] && has_humble=1
                if [ "${has_noetic}" -eq 1 ] && [ "${has_humble}" -eq 0 ]; then
                    ROS_DISTRO="noetic"
                    echo "    检测到 /opt/ros/noetic，使用 ROS_DISTRO=noetic"
                elif [ "${has_humble}" -eq 1 ] && [ "${has_noetic}" -eq 0 ]; then
                    ROS_DISTRO="humble"
                    echo "    检测到 /opt/ros/humble，使用 ROS_DISTRO=humble"
                elif [ "${has_noetic}" -eq 1 ] && [ "${has_humble}" -eq 1 ]; then
                    echo "    检测到同时存在 noetic 与 humble，请选择："
                    read -p "    1) noetic  2) humble: " ros_skip_choice
                    case "${ros_skip_choice}" in
                        1)
                            ROS_DISTRO="noetic"
                            ;;
                        2)
                            ROS_DISTRO="humble"
                            ;;
                        *)
                            echo "❌ 输入错误"
                            continue
                            ;;
                    esac
                else
                    echo "❌ 未设置 ROS_DISTRO 且未在 /opt/ros 下找到 noetic/humble，请选 1/2 指定发行版，或先 export ROS_DISTRO=noetic|humble"
                    continue
                fi
            fi
            case "${ROS_DISTRO}" in
                noetic)
                    ROS_BRANCH="noetic_mit_control"
                    ;;
                humble)
                    ROS_BRANCH="humble_mit_control"
                    ;;
            esac
            echo "👉 使用 ${ROS_DISTRO} (y1 分支 ${ROS_BRANCH})"
            break
            ;;
        *)
            echo "❌ 输入错误，只能输入 1 / 2 / 3 / 4"
            ;;
    esac
done

# ================================
# 可选：Y1 机械臂 SDK（y1_sdk_python）
# ================================
echo
read -p "是否安装 Y1 机械臂 SDK (y1_sdk_python)? (y/N): " install_y1

if [[ "$install_y1" == "y" || "$install_y1" == "Y" ]]; then
    Y1_SDK_ROOT="${TP_DIR}/y1_sdk_python"

    if [ -d "${Y1_SDK_ROOT}/.git" ]; then
        echo "ℹ️ y1_sdk_python 已存在，准备同步 ${ROS_BRANCH} 最新代码"

        cd "${Y1_SDK_ROOT}"

        STASHED=0
        if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
            STASH_NAME="auto-stash-before-sync-${ROS_BRANCH}-$(date +%Y%m%d_%H%M%S)"
            echo "ℹ️ 检测到本地修改，先临时 stash: ${STASH_NAME}"
            git stash push -u -m "${STASH_NAME}" > /dev/null
            STASHED=1
        fi

        git fetch origin "${ROS_BRANCH}"

        if git show-ref --verify --quiet "refs/heads/${ROS_BRANCH}"; then
            git checkout "${ROS_BRANCH}"
        else
            git checkout -b "${ROS_BRANCH}" "origin/${ROS_BRANCH}"
        fi

        git rebase "origin/${ROS_BRANCH}"

        if [ "${STASHED}" -eq 1 ]; then
            echo "ℹ️ 正在恢复本地修改"
            if git stash pop > /dev/null; then
                echo "✅ 本地修改已恢复"
            else
                echo "⚠️ stash 恢复出现冲突，请手动解决后继续"
                exit 1
            fi
        fi

        cd "${TP_DIR}"
    else
        git clone -b "${ROS_BRANCH}" https://github.com/IMETA-Robotics/y1_sdk_python.git "${Y1_SDK_ROOT}"
    fi

    cd "${Y1_SDK_ROOT}/y1_sdk"
    pip install -e .
    cd "${TP_DIR}"

    echo "✅ y1_sdk_python 安装完成"
else
    echo "⏭️ 跳过 Y1 SDK。若使用 Y1，请参阅 README 中 CAN / y1_ros 相关说明。"
fi

# ================================
# 可选：Piper（pyAgxArm + 重力补偿）
# ================================
echo
read -p "是否安装 Agilex Piper 相关依赖（ROS Pinocchio deb + pyAgxArm + 重力补偿）? (y/N): " install_piper

if [[ "$install_piper" == "y" || "$install_piper" == "Y" ]]; then
    echo "ℹ️ 以下 apt 包需要已为 ${ROS_DISTRO} 配置好 ROS 软件源，否则可能安装失败。"
    sudo apt update
    sudo apt install -y \
        "ros-${ROS_DISTRO}-pinocchio" \
        "ros-${ROS_DISTRO}-hpp-fcl" \
        "ros-${ROS_DISTRO}-coal"

    PY_AGX_DIR="${TP_DIR}/pyAgxArm"
    if [ -d "${PY_AGX_DIR}/.git" ]; then
        echo "ℹ️ pyAgxArm 目录已存在，跳过 clone: ${PY_AGX_DIR}"
    else
        echo "👉 正在 clone pyAgxArm..."
        git clone https://github.com/agilexrobotics/pyAgxArm.git "${PY_AGX_DIR}"
    fi

    echo "👉 pip install -e pyAgxArm"
    pip install -e "${PY_AGX_DIR}"

    GRAVITY_DIR="${TP_DIR}/agilex-arm-gravity-compensation"
    if [ ! -d "${GRAVITY_DIR}" ]; then
        echo "❌ 未找到 ${GRAVITY_DIR}，请确认 third_party 中包含 agilex-arm-gravity-compensation。"
        exit 1
    fi
    echo "👉 pip install -e agilex-arm-gravity-compensation"
    pip install -e "${GRAVITY_DIR}"

    echo "✅ Piper 相关安装完成"
    echo "ℹ️ 使用重力补偿前请按需运行 third_party/agilex-arm-gravity-compensation/can_activate.sh 等步骤，参见该目录 README。"
else
    echo "⏭️ 跳过 Piper 相关安装"
fi

# ================================
# 可选：Orbbec（pyorbbecsdk + udev + PyPI）
# ================================
echo
read -p "是否安装 Orbbec 相机依赖（pyorbbecsdk 仓库、udev 规则、pyorbbecsdk2）? (y/N): " install_orbbec

if [[ "$install_orbbec" == "y" || "$install_orbbec" == "Y" ]]; then
    ORBBEC_DIR="${TP_DIR}/pyorbbecsdk"
    if [ -d "${ORBBEC_DIR}/.git" ]; then
        echo "ℹ️ pyorbbecsdk 目录已存在，跳过 clone: ${ORBBEC_DIR}"
    else
        echo "👉 正在 clone pyorbbecsdk..."
        git clone https://github.com/orbbec/pyorbbecsdk.git "${ORBBEC_DIR}"
    fi

    ENV_SETUP="${ORBBEC_DIR}/scripts/env_setup"
    if [ ! -f "${ENV_SETUP}/install_udev_rules.sh" ]; then
        echo "❌ 未找到 ${ENV_SETUP}/install_udev_rules.sh，请检查 pyorbbecsdk 仓库结构。"
        exit 1
    fi

    chmod +x "${ENV_SETUP}/install_udev_rules.sh"
    echo "👉 安装 Orbbec udev 规则（需要 sudo）"
    (cd "${ENV_SETUP}" && sudo ./install_udev_rules.sh)
    sudo udevadm control --reload && sudo udevadm trigger || true

    echo "👉 pip install pyorbbecsdk2"
    pip install pyorbbecsdk2

    echo "✅ Orbbec 相关安装完成"
else
    echo "⏭️ 跳过 Orbbec 相关安装"
fi

# ================================
# 可选：wuji-retargeting
# ================================
echo
read -p "是否安装 Wuji Retargeting? (y/N): " install_wuji

if [[ "$install_wuji" == "y" || "$install_wuji" == "Y" ]]; then

    if [ -d "${TP_DIR}/wuji-retargeting/.git" ]; then
        echo "ℹ️ wuji-retargeting 已存在，跳过 clone"
    else
        echo "👉 正在 clone wuji-retargeting..."
        git clone --recurse-submodules https://github.com/wuji-technology/wuji-retargeting.git "${TP_DIR}/wuji-retargeting"
    fi

    echo "👉 正在安装 wuji-retargeting (editable mode)..."
    pip install -e "${TP_DIR}/wuji-retargeting"

    echo "✅ wuji-retargeting 安装完成"
else
    echo "⏭️ 跳过 wuji-retargeting 安装"
fi

echo
echo "🎉 所有安装流程完成"
