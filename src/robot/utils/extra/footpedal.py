import os
import time
import threading

class FootPedal:
    """
    USB 脚踏板读取类。
    针对触发式设备（仅在踩下瞬间发送一个数据包）进行封装。
    """
    def __init__(self, dev_node="/dev/hidraw4"):
        self.dev_node = dev_node
        self.running = True
        self._pressed_flag = False
        self._lock = threading.Lock()
        self._callbacks = []
        
        if os.path.exists(dev_node):
            try:
                # 检查权限
                fd = os.open(dev_node, os.O_RDONLY)
                os.close(fd)
                self.thread = threading.Thread(target=self._listen, daemon=True)
                self.thread.start()
                print(f"[FootPedal] 已在后台开启监听: {dev_node}")
            except PermissionError:
                print(f"[FootPedal] 权限不足: 无法读取 {dev_node}，请尝试使用 sudo 运行程序。")
        else:
            print(f"[FootPedal] 警告: 未找到设备 {dev_node}")
        
        def my_action():
            print(">>> [回调方式] 收到触发信号！")
        self.register_callback(my_action)

    def _listen(self):
        try:
            # 针对仅发送一瞬间信号的设备，使用阻塞读取模式
            fd = os.open(self.dev_node, os.O_RDONLY)
            while self.running:
                data = os.read(fd, 64)
                if data:
                    with self._lock:
                        self._pressed_flag = True
                    # 执行异步回调
                    for callback in self._callbacks:
                        try:
                            callback()
                        except:
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
    pedal = FootPedal("/dev/hidraw4")

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
