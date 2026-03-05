#!/usr/bin/env python3
import os
import subprocess
import sys

def get_camera_info():
    """获取所有 video 录像设备，按 ID_PATH 和 ID_SERIAL 分组以支持相同型号相机"""
    cameras = []
    try:
        # 导出 udev 数据库
        output = subprocess.check_output("udevadm info --export-db", shell=True).decode()
        
        all_found = []
        current_dev = {}
        
        for line in output.splitlines():
            if line.startswith("P: "):
                # 解析上一个设备
                if current_dev.get('subsystem') == "video4linux":
                    # 只保留 ID_USB_INTERFACE_NUM=00 (主数据流) 或无此属性的 (非USB)
                    if current_dev.get('interface_num', '00') == '00':
                        all_found.append(current_dev)
                current_dev = {'dev_node': None, 'vendor': None, 'model': None, 'serial': '', 'name': '', 'subsystem': '', 'interface_num': '', 'id_path': ''}
            elif line.startswith("N: "):
                current_dev['dev_node'] = "/dev/" + line[3:].strip()
            elif line.startswith("E: SUBSYSTEM="):
                current_dev['subsystem'] = line.split("=")[1].strip()
            elif line.startswith("E: ID_VENDOR_ID="):
                current_dev['vendor'] = line.split("=")[1].strip()
            elif line.startswith("E: ID_MODEL_ID="):
                current_dev['model'] = line.split("=")[1].strip()
            elif line.startswith("E: ID_SERIAL_SHORT="):
                current_dev['serial'] = line.split("=")[1].strip()
            elif line.startswith("E: ID_V4L_PRODUCT="):
                current_dev['name'] = line.split("=")[1].strip()
            elif line.startswith("E: ID_USB_INTERFACE_NUM="):
                current_dev['interface_num'] = line.split("=")[1].strip()
            elif line.startswith("E: ID_PATH="):
                current_dev['id_path'] = line.split("=")[1].strip()

        # 排除 1d6b (Hub)
        all_found = [d for d in all_found if d.get('vendor') != "1d6b"]

        # 处理完全相同的相机 (Serial 相同但 ID_PATH 不同)
        # 我们使用 ID_PATH 作为区分主键，因为即使 Serial 相同，物理位置也是不同的
        for dev in all_found:
            cameras.append({
                'dev': dev['dev_node'],
                'vendor': dev['vendor'],
                'model': dev['model'],
                'serial': dev['serial'],
                'name': dev['name'],
                'id_path': dev['id_path']
            })

        return cameras
    except Exception as e:
        print(f"扫描设备失败: {e}")
    return []

def main():
    if os.getuid() != 0:
        print("错误: 请使用 sudo 运行此程序！")
        sys.exit(1)

    print("正在扫描摄像头设备...")
    cameras = get_camera_info()
    
    if not cameras:
        print("未能识别到有效的 USB 摄像头。")
        return

    print(f"找到 {len(cameras)} 个摄像头节点:")
    for i, cam in enumerate(cameras):
        name = cam['name'] if cam['name'] else "Unknown Camera"
        # 显示 ID_PATH 的后半段作为位置参考
        pos = cam['id_path'].split("-")[-1] if cam['id_path'] else "N/A"
        print(f"[{i}] {name[:20]:<20} | 节点: {cam['dev']:<12} | S/N: {cam['serial']:<15} | 物理位置: {pos}")

    mappings = {
        'head_camera': None,
        'left_wrist_camera': None,
        'right_wrist_camera': None
    }

    print("\n请按提示分配摄像头 (输入索引号，相同型号请根据物理位置判断):")
    for role in mappings.keys():
        while True:
            choice = input(f"请输入 {role} 的索引 (跳过按回车): ").strip()
            if not choice:
                break
            try:
                idx = int(choice)
                if 0 <= idx < len(cameras):
                    mappings[role] = cameras[idx]
                    break
                else:
                    print("无效索引。")
            except ValueError:
                print("请输入数字。")

    rule_content = ""
    assigned = False
    for role, cam in mappings.items():
        if cam:
            # 最终方案：直接使用系统的 ID_PATH 环境变量
            # 这能完美解决：
            # 1. 相同序列号相机的冲突
            # 2. 重新拔插后别名消失的问题
            # 3. 过滤掉无画面的索引 (因为主接口末尾通常是 :1.0)
            
            line = (
                f'SUBSYSTEM=="video4linux", ENV{{ID_PATH}}=="{cam["id_path"]}", '
                f'ATTR{{index}}=="0", SYMLINK+="{role}", MODE="0666"\n'
            )
            rule_content += line
            assigned = True

    if not assigned: return

    rule_path = "/etc/udev/rules.d/99-usb-cameras.rules"
    try:
        # 使用追加模式，或者你也可以保持 w 模式（因为这个脚本是一次性分配三个相机的）
        with open(rule_path, "w") as f:
            f.write(rule_content)
        print(f"\n规则已写入 {rule_path}")
        subprocess.run(["udevadm", "control", "--reload-rules"], check=True)
        subprocess.run(["udevadm", "trigger"], check=True)
        print("成功！重启或重新插拔后别名生效。")
    except Exception as e:
        print(f"写入失败: {e}")

if __name__ == "__main__":
    main()
