#!/usr/bin/env python3
import os
import subprocess
import sys

def get_device_info():
    """获取所有 HIDRAW, TTY, VIDEO 设备及其 USB 属性"""
    devices = []
    try:
        # 获取所有具有 devname 的节点，如果没有文件则返回空列表而不是报错
        import glob
        dev_nodes = []
        for pattern in ["/dev/hidraw*", "/dev/video*", "/dev/ttyUSB*", "/dev/ttyACM*"]:
            dev_nodes.extend(glob.glob(pattern))
        
        seen_keys = set()
        for node in dev_nodes:
            try:
                # 获取该节点的属性
                info = subprocess.check_output(f"udevadm info -a -n {node}", shell=True).decode()
                
                # 获取该节点的环境变量 (包含 ID_PATH)
                env_info = subprocess.check_output(f"udevadm info --query=property --name={node}", shell=True).decode()
                id_path = ""
                name = ""
                for line in env_info.splitlines():
                    if "ID_PATH=" in line or "DEVPATH=" in line and not id_path:
                        id_path = line.split("=")[1].strip()
                    if "HID_NAME" in line or "ID_MODEL_FROM_DATABASE" in line:
                        name = line.split("=")[1].strip()

                # 如果 ID_PATH 包含 pci 或 usb，通常是可靠的物理路径
                # 如果没有 ID_PATH，我们将无法稳定绑定到位置
                
                # 解析属性
                import re
                v_match = re.search(r'ATTRS{idVendor}=="([^"]+)"', info)
                m_match = re.search(r'ATTRS{idProduct}=="([^"]+)"', info)
                s_match = re.search(r'ATTRS{serial}=="([^"]+)"', info)
                # 新增：获取接口编号，用于区分同一设备下的多个 hidraw
                i_match = re.search(r'ATTRS{bInterfaceNumber}=="([^"]+)"', info)
                
                vendor = v_match.group(1) if v_match else ""
                model = m_match.group(1) if m_match else ""
                serial = s_match.group(1) if s_match else ""
                iface = i_match.group(1) if i_match else ""
                
                if not vendor or vendor == "1d6b": continue # 跳过 Hub

                # 唯一键包含接口号，以区分同一设备的不同功能口
                key = f"{vendor}:{model}:{serial or id_path}:{iface}"
                if key not in seen_keys:
                    devices.append({
                        'dev_list': [node],
                        'vendor': vendor,
                        'model': model,
                        'serial': serial,
                        'id_path': id_path,
                        'iface': iface,
                        'name': name or f"USB Device {vendor}:{model}"
                    })
                    seen_keys.add(key)
                else:
                    for d in devices:
                        current_key = f"{d['vendor']}:{d['model']}:{d['serial'] or d['id_path']}:{d['iface']}"
                        if current_key == key:
                            if node not in d['dev_list']: d['dev_list'].append(node)
            except:
                continue
    except Exception as e:
        print(f"扫描失败: {e}")
    return devices

def main():
    if os.getuid() != 0:
        print("错误: 请使用 sudo 运行！")
        sys.exit(1)

    print("正在扫描设备...")
    devices = get_device_info()
    if not devices:
        print("未发现设备。")
        return

    for i, dev in enumerate(devices):
        nodes = ",".join(dev['dev_list'])
        # 显示接口号以便用户选择正确的子设备
        iface_hint = f"| Iface: {dev['iface']}" if dev['iface'] else ""
        print(f"[{i}] {dev['name'][:30]:<30} | 节点: {nodes:<20} | ID: {dev['vendor']}:{dev['model']} {iface_hint}")

    choice = input("\n选择要烧录的索引: ").strip()
    if not choice: return
    idx = int(choice)
    target_dev = devices[idx]
    alias = input("输入别名 (如 pedal): ").strip()
    
    # 规则生成逻辑：
    # 1. 如果有 serial，使用 serial。如果没有 serial，降级使用 ID_PATH (物理位置绑定)
    # 2. 对于 hidraw/video 设备，配合接口信息锁定
    
    # 基础匹配项
    base_parts = [
        f'ATTRS{{idVendor}}=="{target_dev["vendor"]}"',
        f'ATTRS{{idProduct}}=="{target_dev["model"]}"'
    ]
    
    if target_dev['serial']:
        base_parts.append(f'ATTRS{{serial}}=="{target_dev["serial"]}"')
    else:
        base_parts.append(f'ENV{{ID_PATH}}=="{target_dev["id_path"]}"')

    # 针对不同子系统的特殊过滤
    if "hidraw" in target_dev['dev_list'][0]:
        # 踏板类：移除复杂的 KERNELS 匹配，直接使用属性路径
        rule = f'SUBSYSTEM=="hidraw", {", ".join(base_parts)}, SYMLINK+="{alias}", MODE="0666"\n'
    elif "video" in target_dev['dev_list'][0]:
        # 摄像头：锁定 index 0
        rule = f'SUBSYSTEM=="video4linux", {", ".join(base_parts)}, ATTR{{index}}=="0", SYMLINK+="{alias}", MODE="0666"\n'
    elif "ttyUSB" in target_dev['dev_list'][0] or "ttyACM" in target_dev['dev_list'][0]:
        # 串口设备
        rule = f'SUBSYSTEM=="tty", {", ".join(base_parts)}, SYMLINK+="{alias}", MODE="0666"\n'
    else:
        # 其他设备兜底
        rule = f'{", ".join(base_parts)}, SYMLINK+="{alias}", MODE="0666"\n'
    
    # 强制每条规则占一行，去除多余空白
    rule = rule.strip() + "\n"
    
    # 确保规则文件中不会出现同一别名的多条冲突规则
    rule_path = "/etc/udev/rules.d/99-usb-custom.rules"
    try:
        # 先读取现有内容
        existing_content = ""
        if os.path.exists(rule_path):
            existing_content = subprocess.check_output(["sudo", "cat", rule_path]).decode()
        
        # 过滤并添加新规则
        lines = [line.strip() for line in existing_content.splitlines() if line.strip() and f'SYMLINK+="{alias}"' not in line]
        lines.append(rule.strip())
        final_rules = "\n".join(lines) + "\n"
        
        # 使用 sudo tee 写入整个文件（确保格式完整）
        subprocess.run(["sudo", "tee", rule_path], input=final_rules.encode(), check=True, capture_output=True)
        print(f"规则已同步到 {rule_path}")
    except Exception as e:
        print(f"写入失败: {e}")
        sys.exit(1)
    
    subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=True)
    subprocess.run(["sudo", "udevadm", "trigger"], check=True)
    print(f"成功！现在应可通过 /dev/{alias} 访问。")

if __name__ == "__main__":
    main()
