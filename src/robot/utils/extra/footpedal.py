import os
import time
import threading

class FootPedal:
    """
    USB 脚踏板读取类。
    同时兼容两类 hidraw 设备：
    1. 键盘式设备，持续上报按下/松开状态；
    2. 触发式设备，仅在踩下瞬间发送一个数据包。
    """
    def __init__(self, dev_node="/dev/pedal"):
        self.dev_node = self._resolve_device(dev_node)
        self.running = True
        self._pressed_flag = False
        self._is_pressed = False
        self._lock = threading.Lock()
        self._callbacks = []
        self.report_mode = self._detect_report_mode(self.dev_node)
        
        if os.path.exists(self.dev_node):
            try:
                # 检查权限
                fd = os.open(self.dev_node, os.O_RDONLY)
                os.close(fd)
                self.thread = threading.Thread(target=self._listen, daemon=True)
                self.thread.start()
                print(f"[FootPedal] 已在后台开启监听: {self.dev_node} (mode={self.report_mode})")
            except PermissionError:
                print(f"[FootPedal] 权限不足: 无法读取 {self.dev_node}，请尝试使用 sudo 运行程序。")
        else:
            print(f"[FootPedal] 警告: 未找到设备 {self.dev_node}")

    def _resolve_device(self, dev_node):
        if os.path.exists(dev_node):
            return dev_node
        if dev_node != "/dev/pedal":
            return dev_node

        detected = self._find_hidraw_device()
        if detected:
            print(f"[FootPedal] /dev/pedal 不存在，自动使用 {detected}")
            return detected
        return dev_node

    def _find_hidraw_device(self):
        sys_class = "/sys/class/hidraw"
        if not os.path.isdir(sys_class):
            return None

        keyboard_candidate = None
        lintx_candidate = None
        for hidraw_name in sorted(os.listdir(sys_class)):
            dev_node = f"/dev/{hidraw_name}"
            real_path = os.path.realpath(os.path.join(sys_class, hidraw_name))
            hid_device_path = os.path.dirname(os.path.dirname(real_path))
            iface_path = os.path.dirname(hid_device_path)
            uevent_path = os.path.join(hid_device_path, "uevent")
            hid_name = self._read_uevent_value(uevent_path, "HID_NAME")
            interface_number = self._read_text_file(os.path.join(iface_path, "bInterfaceNumber"))
            if hid_name == "KM-key08" and interface_number == "00":
                keyboard_candidate = dev_node
                break
            if hid_name and "LinTx" in hid_name:
                lintx_candidate = dev_node

        return keyboard_candidate or lintx_candidate

    def _read_uevent_value(self, file_path, key):
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith(f"{key}="):
                        return line.strip().split("=", 1)[1]
        except OSError:
            return None
        return None

    def _read_text_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return None

    def _detect_report_mode(self, dev_node):
        hidraw_name = os.path.basename(dev_node)
        real_path = os.path.realpath(f"/sys/class/hidraw/{hidraw_name}")
        descriptor_path = os.path.join(os.path.dirname(os.path.dirname(real_path)), "report_descriptor")
        try:
            with open(descriptor_path, "rb") as handle:
                descriptor = handle.read()
        except OSError:
            return "trigger"

        if descriptor.startswith(b"\x05\x01\x09\x06"):
            return "keyboard"
        return "trigger"

    def _handle_keyboard_report(self, data):
        pressed = bool(data[:1] and data[0]) or any(byte != 0 for byte in data[2:])
        callbacks = []
        triggered = False
        with self._lock:
            was_pressed = self._is_pressed
            self._is_pressed = pressed
            if pressed and not was_pressed:
                self._pressed_flag = True
                callbacks = list(self._callbacks)
                triggered = True
        return triggered, callbacks

    def _handle_trigger_report(self, data):
        if not data:
            return False, []
        callbacks = []
        with self._lock:
            self._pressed_flag = True
            callbacks = list(self._callbacks)
        return True, callbacks

    def _listen(self):
        fd = None
        try:
            # hidraw 使用阻塞读取模式，数据到达后再解析为按下边沿或当前状态
            fd = os.open(self.dev_node, os.O_RDONLY)
            while self.running:
                data = os.read(fd, 64)
                if not data:
                    continue

                if self.report_mode == "keyboard":
                    triggered, callbacks = self._handle_keyboard_report(data)
                else:
                    triggered, callbacks = self._handle_trigger_report(data)

                if triggered:
                    for callback in callbacks:
                        try:
                            callback()
                        except Exception:
                            pass
        except Exception as e:
            if self.running:
                print(f"[FootPedal] 读取线程异常终止: {e}")
        finally:
            try:
                os.close(fd)
            except:
                pass

    def register_callback(self, callback):
        """注册一个在触发信号时自动执行的回调函数"""
        self._callbacks.append(callback)

    def is_pressed(self):
        """返回脚踏板当前是否处于按下状态。"""
        with self._lock:
            return self._is_pressed

    def was_pressed(self):
        """
        核心接口：查询自上次检查以来是否有踩下动作。
        该方法带有'自锁/清除'机制，返回 True 后会重置状态。
        """
        with self._lock:
            if self._pressed_flag:
                self._pressed_flag = False
                return True
            return False

    def stop(self):
        """停止监听并清理线程"""
        self.running = False

# 测试代码
if __name__ == "__main__":
    pedal = FootPedal("/dev/pedal")

    print("\n--- 工作模式: 等待脚踏板触发 (Ctrl+C 退出) ---")
    try:
        while True:
            # 示例 B：轮询检查
            if pedal.was_pressed():
                print(">>> [轮询检查] 获取到了踩下信号！")
            time.sleep(0.01)
    except KeyboardInterrupt:
        pedal.stop()
        print("\n已安全退出。")
