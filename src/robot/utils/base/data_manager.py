import numpy as np
import threading
import time
from typing import Optional, Tuple

import json
import socket
from typing import Any, Dict, Optional

class UDPClient:
    def __init__(self, port: int, timeout: float = 0.05, bufsize: int = 4096):
        self.port = int(port)
        self.bufsize = bufsize
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(timeout)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", self.port))

    def recv_once(self) -> Optional[Dict[str, Any]]:
        """接收一帧 JSON 数据，超时返回 None。"""
        try:
            data, _addr = self._sock.recvfrom(self.bufsize)
            return json.loads(data.decode("utf-8"))
        except socket.timeout:
            return None
        except Exception:
            return None

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass

    @property
    def socket(self) -> socket.socket:
        return self._sock

import numpy as np
from typing import Dict, Any, Tuple


def parse_hand_data(data: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """
    解析手部关节数据
    
    将字典格式的关节数据转换为 (5, 4) 的 numpy 数组。
    
    Args:
        data: 包含关节数据的字典，键名格式为 "left_finger{1-5}_joint{1-4}"
              或 "right_finger{1-5}_joint{1-4}"
    
    Returns:
        (left_array, right_array): 左右手的关节数据，shape=(5, 4)
        
    数组布局:
        - 行: 5个手指 (F1-F5)
        - 列: 4个关节 (J1-J4)
    """
    left = np.zeros((5, 4), dtype=np.float64)
    right = np.zeros((5, 4), dtype=np.float64)
    
    for finger in range(1, 6):
        for joint in range(1, 5):
            left_key = f"left_finger{finger}_joint{joint}"
            right_key = f"right_finger{finger}_joint{joint}"
            
            if left_key in data:
                left[finger - 1, joint - 1] = float(data[left_key])
            if right_key in data:
                right[finger - 1, joint - 1] = float(data[right_key])
    
    return left, right


def extract_response_data(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取响应中的数据部分
    
    Args:
        response: 服务器原始响应
        
    Returns:
        提取的数据字典
    """
    return response.get("res", response)

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
