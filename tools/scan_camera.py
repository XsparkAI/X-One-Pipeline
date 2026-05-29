import cv2
import threading
import time
import queue
import os

class CameraThread(threading.Thread):
    def __init__(self, index):
        super().__init__()
        self.index = index
        self.cap = cv2.VideoCapture(index)
        self.frame = None
        self.running = True
        self.daemon = True

    def run(self):
        while self.running:
            # 使用更平滑的读取
            ret, frame = self.cap.read()
            if ret:
                self.frame = frame
            else:
                # 如果读取失败，稍作等待
                time.sleep(0.01)
        
        # 线程结束前释放
        if self.cap.isOpened():
            self.cap.release()

    def stop(self):
        self.running = False

def scan_cameras(max_to_test=10):
    """扫描可用的摄像头索引"""
    available_indices = []
    print("正在扫描摄像头，请稍候...")
    for i in range(max_to_test):
        # 尝试获取设备名称 (Linux 特有)
        name = "Unknown"
        device_name_path = f"/sys/class/video4linux/video{i}/name"
        if os.path.exists(device_name_path):
            with open(device_name_path, 'r') as f:
                name = f.read().strip()

        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            # 确认能读取到帧
            ret, _ = cap.read()
            if ret:
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                # 提示：Linux 中通常 video0, 2, 4 是图像流，video1, 3, 5 是元数据流
                print(f"发现摄像头 [索引 {i}]: {name} ({int(width)}x{int(height)})")
                available_indices.append(i)
            cap.release()
    return available_indices

def main():
    indices = scan_cameras()
    
    while True:
        if not indices:
            print("\n未发现任何可用的摄像头。")
            rescan = input("按回车重新扫描，或输入 'q' 退出: ").strip().lower()
            if rescan == 'q':
                break
            indices = scan_cameras()
            continue

        print("\n" + "="*30)
        print("可用的摄像头索引列表:", indices)
        print("操作指引:")
        print("  - 输入索引 (如 '0') 或多个索引 (如 '0,1') 开始预览")
        print("  - 直接回车预览所有发现的摄像头")
        print("  - 输入 'r' 重新扫描设备")
        print("  - 输入 'q' 退出程序")
        print("="*30)
        
        user_input = input("\n请输入指令: ").strip().lower()

        if user_input == 'q':
            break
        if user_input == 'r':
            indices = scan_cameras()
            continue

        try:
            if not user_input:
                selected_indices = indices
            else:
                selected_indices = [int(i.strip()) for i in user_input.split(",") if i.strip()]
        except ValueError:
            print(">>> 输入格式错误，请输入数字、逗号或指令。")
            continue

        # 启动采集线程
        cam_threads = {}
        for idx in selected_indices:
            print(f"正在初始化摄像头 {idx}...")
            t = CameraThread(idx)
            if not t.cap.isOpened():
                print(f"警告: 无法打开摄像头 {idx}")
                continue
            t.start()
            cam_threads[idx] = t

        if not cam_threads:
            print(">>> 没有成功启动任何预览。")
            continue

        print("\n>>> 预览已启动")
        print(">>> 窗口快捷键:")
        print("    [q]: 停止当前预览，返回菜单切换摄像头")
        print("    [ESC]: 直接退出程序")

        should_exit_program = False
        try:
            while True:
                for idx, t in cam_threads.items():
                    if t.frame is not None:
                        cv2.imshow(f"Camera {idx}", t.frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == 27: # ESC 键
                    should_exit_program = True
                    break
                if key == ord('q'):
                    print("\n正在停止预览，返回菜单...")
                    break
                
                if not any(t.is_alive() for t in cam_threads.values()):
                    print("\n摄像头连接断开。")
                    break

        except KeyboardInterrupt:
            should_exit_program = True
        finally:
            # 必须按照 停止 -> 等待线程释放资源 -> 销毁窗口 的顺序
            for t in cam_threads.values():
                t.stop()
            
            for t in cam_threads.values():
                t.join(timeout=1.0)
            
            cv2.destroyAllWindows()
            # 给 OpenCV 一点时间清理 UI
            cv2.waitKey(10)

        if should_exit_program:
            break

    print("\n程序已退出。")

if __name__ == "__main__":
    main()
