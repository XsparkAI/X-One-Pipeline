#!/usr/bin/env bash
set -e

# compile project
pip install -e .

SDK_DIR="third_party/y1_sdk_python"

cd third_party

# ================================
# 安装 y1_sdk_python
# ================================
if [ -d "y1_sdk_python/.git" ]; then
    echo "ℹ️ y1_sdk_python 已存在，跳过 clone"
else
    while true; do
        echo
        echo "请选择 ROS 版本："
        echo "  1) noetic"
        echo "  2) humble"
        echo "  3) 使用鱼香 ROS 安装 ROS（安装完成后再选择 1 或 2）"
        read -p "请输入 1 / 2 / 3: " ros_choice

        case "${ros_choice}" in
            1)
                echo "👉 使用 noetic 分支"
                git clone https://github.com/IMETA-Robotics/y1_sdk_python.git
                break
                ;;
            2)
                echo "👉 使用 humble 分支"
                git clone -b humble https://github.com/IMETA-Robotics/y1_sdk_python.git
                break
                ;;
            3)
                echo "👉 使用鱼香 ROS 安装 ROS"
                cd ~

                wget http://fishros.com/install -O fishros

                set +e
                bash fishros
                set -e

                cd - > /dev/null
                echo
                echo "✅ ROS 安装流程结束，请重新选择 1 或 2"
                ;;
            *)
                echo "❌ 输入错误，只能输入 1 / 2 / 3"
                ;;
        esac
    done
fi

# install y1_sdk (无论是否 clone，都执行)
cd y1_sdk_python/y1_sdk
pip install -e .
cd ../..

echo "✅ y1_sdk_python 安装完成"


# ================================
# 可选安装 wuji-retargeting
# ================================
echo
read -p "是否安装 Wuji Retargeting? (y/N): " install_wuji

if [[ "$install_wuji" == "y" || "$install_wuji" == "Y" ]]; then

    if [ -d "wuji-retargeting/.git" ]; then
        echo "ℹ️ wuji-retargeting 已存在，跳过 clone"
    else
        echo "👉 正在 clone wuji-retargeting..."
        git clone https://github.com/wuji-technology/wuji-retargeting.git
    fi

    echo "👉 正在安装 wuji-retargeting (editable mode)..."
    cd wuji-retargeting
    pip install -e .
    cd ..

    echo "✅ wuji-retargeting 安装完成"
else
    echo "⏭️ 跳过 wuji-retargeting 安装"
fi


echo
echo "🎉 所有安装流程完成"
