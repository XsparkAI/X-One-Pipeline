"""极简 UDP 客户端：只负责绑定端口并接收 JSON 帧"""

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
