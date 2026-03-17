#!/usr/bin/env python3
import os
import subprocess
import sys

# 设备识别信息
VENDOR_ID = "2e3c"
PRODUCT_ID = "af01"
ALIAS = "ft_sensor"
RULE_PATH = "/etc/udev/rules.d/99-haptron-ft.rules"

def run_command(cmd, shell=True):
    try:
        if shell:
            subprocess.run(cmd, shell=True, check=True)
        else:
            subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"执行失败: {cmd}\n错误: {e}")
        return False
    return True

def setup_udev_rule(alias):
    print(f"开始配置 udev 规则，将设备 {VENDOR_ID}:{PRODUCT_ID} 绑定为 /dev/{alias}...")
    
    # 规则内容说明:
    # 1. ATTRS{idVendor} 和 ATTRS{idProduct} 用于匹配设备
    # 2. SYMLINK+="{alias}" 创建稳定别名
    # 3. MODE="0666" 赋予读写权限
    # 4. 包含对 usb-serial 驱动的触发处理
    rule_content = f'SUBSYSTEM=="usb", ATTRS{{idVendor}}=="{VENDOR_ID}", ATTRS{{idProduct}}=="{PRODUCT_ID}", MODE="0666"\n'
    rule_content += f'SUBSYSTEM=="usb-serial", ATTRS{{idVendor}}=="{VENDOR_ID}", ATTRS{{idProduct}}=="{PRODUCT_ID}", SYMLINK+="{alias}", MODE="0666"\n'
    rule_content += f'KERNEL=="ttyUSB*", ATTRS{{idVendor}}=="{VENDOR_ID}", ATTRS{{idProduct}}=="{PRODUCT_ID}", SYMLINK+="{alias}", MODE="0666"\n'

    try:
        # 获取现有的规则内容，避免覆盖其他别名
        existing_content = ""
        if os.path.exists("/tmp/99-haptron-ft.rules"):
             with open("/tmp/99-haptron-ft.rules", "r") as f:
                existing_content = f.read()
        elif os.path.exists(RULE_PATH):
            # 如果本地没有，尝试从系统目录读取（需要读取权限）
            try:
                existing_content = subprocess.check_output(f"cat {RULE_PATH}", shell=True, text=True)
            except:
                existing_content = ""

        # 检查是否已经存在该别名的规则，如果存在则不重复添加
        if f'SYMLINK+="{alias}"' in existing_content:
            print(f"警告：别名 {alias} 的规则已存在，正在尝试更新/重新应用...")
            # 简单处理：如果已存在，我们可以选择先删除旧的同名行，这里为了安全采用追加或替换逻辑
            lines = [line for line in existing_content.splitlines() if f'SYMLINK+="{alias}"' not in line]
            existing_content = "\n".join(lines) + "\n"

        final_content = existing_content + rule_content

        # 写入临时文件
        with open("/tmp/99-haptron-ft.rules", "w") as f:
            f.write(final_content)
        
        # 移动到系统目录并加载
        print("正在应用系统配置 (需要 sudo 权限)...")
        run_command(f"sudo mv /tmp/99-haptron-ft.rules {RULE_PATH}")
        run_command("sudo udevadm control --reload-rules")
        run_command("sudo udevadm trigger")
        
        # 针对当前的 usb-serial 驱动进行一次手动绑定
        print("正在强制加载 usbserial 驱动并注册设备 ID...")
        run_command("sudo modprobe usbserial")
        run_command(f"echo {VENDOR_ID} {PRODUCT_ID} | sudo tee /sys/bus/usb-serial/drivers/generic/new_id", shell=True)
        
        print(f"\n配置完成！")
        print(f"现在即使重新插入，该设备也会自动挂载到: /dev/{alias}")
        print(f"并且已自动设置权限为 0666 (所有人可访问)。")
        
    except Exception as e:
        print(f"发生异常: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="配置 HAPTRON 传感器 udev 规则")
    parser.add_argument("--alias", default="ft_sensor", help="自定义别名 (默认: ft_sensor)")
    args = parser.parse_args()

    if os.geteuid() != 0:
        print("提示：检测到当前不是 root 用户，脚本将尝试使用 sudo 执行关键步骤。")
    
    setup_udev_rule(args.alias)
