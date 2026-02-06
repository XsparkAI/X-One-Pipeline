import numpy as np
import threading
import time
from typing import Optional, Tuple

from .network import UDPClient
from .data_parser import parse_hand_data, extract_response_data


class UDPDataManager:
    """极简 UDP 数据管理器：绑定端口、接收、更新缓存"""

    def __init__(self, port: int = 6001):
        self.client = UDPClient(port)

        self._left_target = np.zeros((5, 4), dtype=np.float64)
        self._right_target = np.zeros((5, 4), dtype=np.float64)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._new_data_available = False
        self._first_frame_received = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"UDPDataManager: 后台线程已启动 (port={self.client.port})")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self.client.close()

    def get_hand_data(self) -> Tuple[np.ndarray, np.ndarray, bool]:
        with self._lock:
            has_new = self._new_data_available
            self._new_data_available = False
            return self._left_target.copy(), self._right_target.copy(), has_new

    def wait_for_data(self, timeout: float = 10.0) -> Tuple[np.ndarray, np.ndarray] | Tuple[None, None]:
        print("正在同步网络数据 (UDP)...")
        start = time.time()
        while (time.time() - start) < timeout:
            left, right, has_new = self.get_hand_data()
            if has_new and (np.any(left != 0) and np.any(right != 0)):
                print("数据同步完成 (UDP)")
                return left.copy(), right.copy()
            time.sleep(0.01)
        return None, None

    def _run_loop(self):
        while self._running:
            try:
                response = self.client.recv_once()
            except Exception as e:
                print(f"UDPDataManager: 接收异常 - {e}")
                time.sleep(0.05)
                continue

            if response is None:
                continue

            data = extract_response_data(response)
            left, right = parse_hand_data(data)

            with self._lock:
                self._left_target = left
                self._right_target = right
                self._new_data_available = True

            if not self._first_frame_received:
                print("UDPDataManager: 首帧数据已接收")
                self._first_frame_received = True
