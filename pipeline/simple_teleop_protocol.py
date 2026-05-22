# pyright: reportMissingImports=false

import base64
import os
import pickle
import struct
import sys
import importlib.util
from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np

try:
    import torch
    _HAS_TORCH = True
except Exception:
    _HAS_TORCH = False


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


UDP_MAGIC = b"XONE"
UDP_HEADER_STRUCT = struct.Struct("!4sIHH")
UDP_MAX_DATAGRAM = 60000


def configure_qt_environment() -> None:
    pyqt_spec = importlib.util.find_spec("PyQt5")
    qt_plugin_root = None
    if pyqt_spec and pyqt_spec.submodule_search_locations:
        pyqt_root = Path(next(iter(pyqt_spec.submodule_search_locations)))
        candidate = pyqt_root / "Qt5" / "plugins"
        if candidate.is_dir():
            qt_plugin_root = str(candidate)

    if qt_plugin_root:
        qt_platform_plugin_path = os.path.join(qt_plugin_root, "platforms")
        os.environ["QT_PLUGIN_PATH"] = qt_plugin_root
        if os.path.isdir(qt_platform_plugin_path):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = qt_platform_plugin_path

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
    else:
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


def split_obs(obs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(obs, (list, tuple)) and len(obs) == 2:
        return obs[0], obs[1]
    raise ValueError(f"Unexpected obs format: {type(obs)}")


def _to_pickle_safe(obj: Any) -> Any:
    if _HAS_TORCH and isinstance(obj, torch.Tensor):
        return obj.detach().cpu().numpy()
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, Mapping):
        return {key: _to_pickle_safe(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_pickle_safe(value) for value in obj]
    return obj


def pickle_dumps(data: Any) -> bytes:
    return pickle.dumps(_to_pickle_safe(data), protocol=pickle.HIGHEST_PROTOCOL)


def pickle_loads(data: bytes) -> Any:
    return pickle.loads(data)


def recv_exact(sock, size: int) -> bytes:
    chunks = []
    received = 0
    while received < size:
        chunk = sock.recv(min(size - received, 65536))
        if not chunk:
            raise ConnectionError("Incomplete response received")
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


def udp_chunk_payload(payload: bytes, frame_id: int, max_datagram_size: int = UDP_MAX_DATAGRAM) -> list[bytes]:
    header_size = UDP_HEADER_STRUCT.size
    if max_datagram_size <= header_size:
        raise ValueError("max_datagram_size is too small for UDP header")

    chunk_payload_size = max_datagram_size - header_size
    chunk_count = max(1, (len(payload) + chunk_payload_size - 1) // chunk_payload_size)
    datagrams = []
    for chunk_index in range(chunk_count):
        start = chunk_index * chunk_payload_size
        end = start + chunk_payload_size
        chunk = payload[start:end]
        header = UDP_HEADER_STRUCT.pack(UDP_MAGIC, frame_id, chunk_index, chunk_count)
        datagrams.append(header + chunk)
    return datagrams


def udp_parse_datagram(datagram: bytes) -> tuple[int, int, int, bytes]:
    header_size = UDP_HEADER_STRUCT.size
    if len(datagram) < header_size:
        raise ValueError("UDP datagram too small")

    magic, frame_id, chunk_index, chunk_count = UDP_HEADER_STRUCT.unpack(datagram[:header_size])
    if magic != UDP_MAGIC:
        raise ValueError("Invalid UDP magic")

    return frame_id, chunk_index, chunk_count, datagram[header_size:]


def decode_color_image(image: Any, rgb: bool) -> np.ndarray | None:
    if image is None:
        return None

    if isinstance(image, (bytes, bytearray)):
        data = np.frombuffer(image, dtype=np.uint8)
        decoded = cv2.imdecode(data, cv2.IMREAD_COLOR)
    elif isinstance(image, np.ndarray) and image.ndim == 1:
        decoded = cv2.imdecode(image.astype(np.uint8), cv2.IMREAD_COLOR)
    elif isinstance(image, np.ndarray) and image.ndim == 3 and image.shape[2] == 3:
        decoded = np.ascontiguousarray(image)
    else:
        return None

    if decoded is None:
        return None
    if rgb:
        return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    return np.ascontiguousarray(decoded)


def encode_image_payload(image: np.ndarray) -> bytes:
    success, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not success:
        raise RuntimeError("Failed to encode image")
    return encoded.tobytes()


def image_to_base64(image: np.ndarray) -> str:
    return base64.b64encode(image).decode("ascii")