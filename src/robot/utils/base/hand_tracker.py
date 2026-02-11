import socket
import threading
import time
import logging
import numpy as np
from typing import Optional, Tuple, Iterable, Dict

# ==============================================================================
# Math Helpers 
# ==============================================================================

def _quat_normalize(quat: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(quat)
    if norm <= 0.0:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=float)
    return quat / norm

def _quat_rotate(points: np.ndarray, quat: np.ndarray) -> np.ndarray:
    """Rotate Nx3 points by quaternion (x, y, z, w)."""
    quat = _quat_normalize(quat)
    q_xyz = quat[:3]
    q_w = quat[3]
    t = 2.0 * np.cross(q_xyz, points)
    return points + q_w * t + np.cross(q_xyz, t)

def _quat_to_matrix(quat: np.ndarray) -> np.ndarray:
    quat = _quat_normalize(quat)
    x, y, z, w = quat
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.array(
        [
            [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)],
            [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)],
            [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)],
        ],
        dtype=float,
    )

def _matrix_to_quat(mat: np.ndarray) -> np.ndarray:
    trace = mat[0, 0] + mat[1, 1] + mat[2, 2]
    if trace > 0.0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (mat[2, 1] - mat[1, 2]) * s
        y = (mat[0, 2] - mat[2, 0]) * s
        z = (mat[1, 0] - mat[0, 1]) * s
    elif mat[0, 0] > mat[1, 1] and mat[0, 0] > mat[2, 2]:
        s = 2.0 * np.sqrt(1.0 + mat[0, 0] - mat[1, 1] - mat[2, 2])
        w = (mat[2, 1] - mat[1, 2]) / s
        x = 0.25 * s
        y = (mat[0, 1] + mat[1, 0]) / s
        z = (mat[0, 2] + mat[2, 0]) / s
    elif mat[1, 1] > mat[2, 2]:
        s = 2.0 * np.sqrt(1.0 + mat[1, 1] - mat[0, 0] - mat[2, 2])
        w = (mat[0, 2] - mat[2, 0]) / s
        x = (mat[0, 1] + mat[1, 0]) / s
        y = 0.25 * s
        z = (mat[1, 2] + mat[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + mat[2, 2] - mat[0, 0] - mat[1, 1])
        w = (mat[1, 0] - mat[0, 1]) / s
        x = (mat[0, 2] + mat[2, 0]) / s
        y = (mat[1, 2] + mat[2, 1]) / s
        z = 0.25 * s
    return _quat_normalize(np.array([x, y, z, w], dtype=float))

# Unity LH (x right, y up, z forward) -> RH (x front, y left, z up)
_UNITY_TO_RH = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=float)

def _convert_vec(vec: np.ndarray) -> np.ndarray:
    return _UNITY_TO_RH @ vec

def _convert_quat(quat: np.ndarray) -> np.ndarray:
    r_unity = _quat_to_matrix(quat)
    r_rh = _UNITY_TO_RH @ r_unity @ _UNITY_TO_RH.T
    return _matrix_to_quat(r_rh)

# ==============================================================================
# Shared Receiver Core (Singleton Logic)
# ==============================================================================

class _HandRawData:
    """存储单只手的最新原始数据"""
    def __init__(self):
        self.wrist_pos: Optional[np.ndarray] = None # Shape (3,)
        self.wrist_quat: Optional[np.ndarray] = None # Shape (4,)
        self.landmarks: Optional[np.ndarray] = None # Shape (N, 3)
        self.updated_at: float = 0.0

# 全局共享状态
_DATA_LOCK = threading.Lock()
_SHARED_HANDS = {
    "left": _HandRawData(),
    "right": _HandRawData()
}
_BG_THREAD: Optional[threading.Thread] = None
_BG_STOP_EVENT = threading.Event()
_IS_LISTENING = False

def _parse_hts_line(line: str) -> Optional[Tuple[str, str, Tuple[float, ...]]]:
    """
    解析 HTS 协议行 (CSV格式)
    Example: "Right Wrist, 1.0, 2.0, 3.0, ..."
    """
    parts = [p.strip() for p in line.split(",")]
    if not parts: return None
    
    label = parts[0].lower()
    # 确定左右
    side = "right" if "right" in label else "left" if "left" in label else None
    if not side: return None
    
    # 确定类型
    kind = "wrist" if "wrist" in label else "landmarks" if "landmarks" in label else None
    if not kind: return None
    
    # 提取数值
    try:
        values = tuple(float(x) for x in parts[1:] if x)
        return (side, kind, values)
    except ValueError:
        return None

def _background_listener_loop(host: str, port: int):
    """后台单例线程：负责 socket 接收并更新 global state"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind((host, port))
        logging.info(f"[HandTracker] Background listener started on {host}:{port}")
    except Exception as e:
        logging.error(f"[HandTracker] Bind failed: {e}")
        return

    sock.settimeout(0.5)

    while not _BG_STOP_EVENT.is_set():
        try:
            data, _ = sock.recvfrom(65536)
            msg = data.decode("utf-8", errors="ignore")
        except socket.timeout:
            continue
        except Exception:
            break

        lines = msg.splitlines()
        updates = []
        
        # 预解析
        for line in lines:
            parsed = _parse_hts_line(line)
            if parsed:
                updates.append(parsed)
        
        # 批量加锁更新
        if updates:
            with _DATA_LOCK:
                now = time.monotonic()
                for side, kind, vals in updates:
                    hand = _SHARED_HANDS[side]
                    arr = np.array(vals, dtype=float)
                    
                    if kind == "wrist" and arr.size >= 7:
                        # 转换 Unity -> RH
                        hand.wrist_pos = _convert_vec(arr[:3])
                        hand.wrist_quat = _convert_quat(arr[3:7])
                        hand.updated_at = now
                    elif kind == "landmarks":
                        # 处理关键点
                        n = arr.size
                        if n > 0 and n % 3 == 0:
                            pts = arr.reshape((-1, 3))
                            # 转换 Unity -> RH
                            hand.landmarks = (_UNITY_TO_RH @ pts.T).T
                            hand.updated_at = now
    
    sock.close()
    logging.info("[HandTracker] Background listener stopped.")

# ==============================================================================
# Public Interface
# ==============================================================================

class HandTracker:


    def __init__(self, hand_side: str = "right", host: str = "0.0.0.0", port: int = 9000):
        self.side = hand_side.lower()
        if self.side not in ["left", "right"]:
            raise ValueError("hand_side must be 'left' or 'right'")
        
        self.host = host
        self.port = port
        
        # 确保后台线程已启动（单例模式）
        self._ensure_listener_started()

    def _ensure_listener_started(self):
        global _BG_THREAD, _IS_LISTENING
        with _DATA_LOCK:
            if not _IS_LISTENING:
                _BG_STOP_EVENT.clear()
                _BG_THREAD = threading.Thread(
                    target=_background_listener_loop,
                    args=(self.host, self.port),
                    daemon=True,
                    name="HandTracker-Global-UDP"
                )
                _BG_THREAD.start()
                _IS_LISTENING = True

    def get_hand_data(self) -> np.ndarray:
        """
        获取当前时刻的手部 21 个关键点数据 (World Space)。
        
        Returns:
            np.ndarray: shape (21, 3). 
                        Index 0 是手腕(Wrist)，
                        Index 1-20 是手指关节。
                        如果无数据，返回全 0 矩阵。
        """
        # --- 临界区：快速拷贝数据 ---
        with _DATA_LOCK:
            raw = _SHARED_HANDS[self.side]
            if raw.landmarks is None:
                return np.zeros((21, 3), dtype=np.float32)
            
            # 拷贝一份引用或数据出来进行后续计算，释放锁，减少阻塞
            wrist_pos = raw.wrist_pos.copy() if raw.wrist_pos is not None else None
            wrist_quat = raw.wrist_quat.copy() if raw.wrist_quat is not None else None
            local_landmarks = raw.landmarks.copy()
        # --- 临界区结束 ---

        # 计算世界坐标 (World Space Calculation)
        # 如果有手腕位姿，将局部关键点转换到世界坐标；否则直接使用流数据
        if wrist_pos is not None and wrist_quat is not None:
            world_pts = _quat_rotate(local_landmarks, wrist_quat) + wrist_pos
        else:
            world_pts = local_landmarks

        # 整理输出格式为 (21, 3)
        # 通常 HTS 流如果是 "landmarks"，指的是手指的 20 个点或者包含手腕的 21 个点
        # 我们这里做一个标准化的拼装：
        result = np.zeros((21, 3), dtype=np.float32)

        # 1. 放入手腕 (Index 0)
        if wrist_pos is not None:
            result[0] = wrist_pos
        elif world_pts.shape[0] == 21:
             # 有些流直接就把手腕放在第0个
             result[0] = world_pts[0]
        
        # 2. 放入手指 (Index 1-20)
        # 如果 raw points 只有 20 个 (纯手指)，则填入 1:21
        # 如果 raw points 有 21 个 (含手腕)，且我们上面单独处理了手腕，这里需要注意对齐
        src_n = world_pts.shape[0]
        
        if src_n == 20:
            result[1:] = world_pts
        elif src_n >= 21:
            # 假设源数据包含了手腕在 index 0，我们直接覆盖整个数组
            result[:21] = world_pts[:21]
        
        return result

    @staticmethod
    def stop_all():
        """停止全局后台线程（通常在程序退出时调用，或者不调用靠 daemon 退出）"""
        global _IS_LISTENING
        logging.info("Stopping HandTracker global listener...")
        _BG_STOP_EVENT.set()
        if _BG_THREAD and _BG_THREAD.is_alive():
            _BG_THREAD.join(timeout=1.0)
        _IS_LISTENING = False

"""
Matplotlib visualizer for HandTracker API.
Rewritten to use the singleton HandTracker for thread-safe data access.

Usage:
    python visualizer_new.py --host 0.0.0.0 --port 9000
"""

# from __future__ import annotations

import argparse
import time

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Please install numpy and matplotlib."
    ) from exc
# ==============================================================================
# Helper Functions for Plotting
# ==============================================================================

def _set_axes_from_bounds(ax: plt.Axes, center: np.ndarray, limit: float) -> None:
    """Set axes limits and aspect from center and half-extent."""
    ax.set_xlim(center[0] - limit, center[0] + limit)
    ax.set_ylim(center[1] - limit, center[1] + limit)
    ax.set_zlim(center[2] - limit, center[2] + limit)
    try:
        # Matplotlib >= 3.3.0
        ax.set_box_aspect([1.0, 1.0, 1.0])
    except Exception:
        pass


def _finger_segments_from_21points(
    points: np.ndarray
) -> Tuple[Tuple[np.ndarray, np.ndarray], ...]:
    """
    Generate line segments for 21-point hand data.
    Index 0 is wrist.
    Indices:
      Thumb: 1,2,3,4
      Index: 5,6,7,8
      Middle: 9,10,11,12
      Ring: 13,14,15,16
      Little: 17,18,19,20
    """
    # points shape: (21, 3)
    wrist = points[0]
    
    segments = []
    
    # helper for creating chain: wrist -> 0 -> 1 -> 2 -> 3
    # BUT index logical structure is: wrist -> joint1 -> joint2 -> joint3 -> tip
    
    fingers_indices = [
        (1, 2, 3, 4),      # Thumb
        (5, 6, 7, 8),      # Index
        (9, 10, 11, 12),   # Middle
        (13, 14, 15, 16),  # Ring
        (17, 18, 19, 20),  # Little
    ]
    
    for finger_idxs in fingers_indices:
        # Segment from Wrist to first joint
        segments.append((wrist, points[finger_idxs[0]]))
        # Segments between joints
        for i in range(len(finger_idxs) - 1):
            start_idx = finger_idxs[i]
            end_idx = finger_idxs[i+1]
            segments.append((points[start_idx], points[end_idx]))
            
    return tuple(segments)


def _init_finger_lines(ax: plt.Axes, color: str) -> list:
    """Initialize Line3D objects for fingers."""
    lines = []
    # 5 fingers * 4 segments per finger = 20 segments
    for _ in range(20):
        (line,) = ax.plot([], [], [], color=color, linewidth=2)
        lines.append(line)
    return lines


def _update_finger_lines(lines: list, segments) -> None:
    """Update line coordinates."""
    for line, (start, end) in zip(lines, segments):
        line.set_data([start[0], end[0]], [start[1], end[1]])
        line.set_3d_properties([start[2], end[2]])


# ==============================================================================
# Main Visualizer Loop
# ==============================================================================

def run_visualizer_new(
    host: str,
    port: int,
    show_left: bool,
    show_right: bool,
    axis_limit: float,
    alpha: float,
    show_fingers: bool,
) -> None:
    """Run the matplotlib visualizer using HandTracker input."""
    
    print(f"Initializing HandTrackers on {host}:{port}...")
    # Instantiate trackers (will reuse the same background listener)
    left_tracker = HandTracker(hand_side="left", host=host, port=port)
    right_tracker = HandTracker(hand_side="right", host=host, port=port)

    # --- Setup Matplotlib Figure ---
    plt.ion()
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_xlabel("X (Front)")
    ax.set_ylabel("Y (Left)")
    ax.set_zlabel("Z (Up)")
    
    # View angle preference
    try:
        ax.view_init(elev=10, azim=-170, roll=0)
    except TypeError:
        ax.view_init(elev=10, azim=-170)

    # Initialize Scatters
    # Right: Red-ish
    right_scatter = ax.scatter([], [], [], c="#E45756", s=200, label="Right Finger")
    right_wrist_sc = ax.scatter([], [], [], c="#B2333C", s=60, marker="x", label="Right Wrist")
    
    # Left: Blue-ish
    left_scatter = ax.scatter([], [], [], c="#4C78A8", s=20, label="Left Finger")
    left_wrist_sc = ax.scatter([], [], [], c="#2D5E8D", s=60, marker="x", label="Left Wrist")
    
    # Origin reference
    ax.scatter([0.0], [0.0], [0.0], c="#222222", s=40, marker="o")
    ax.legend(loc="upper right")

    # Initialize Lines
    right_lines = _init_finger_lines(ax, color="#FFE692") if show_fingers else []
    left_lines = _init_finger_lines(ax, color="#94FFDF") if show_fingers else []

    plt.show(block=False)

    # EMA state for camera smoothing
    ema_center = None
    ema_limit = axis_limit

    print("Visualizer running. Close plot window to exit.")

    try:
        while plt.fignum_exists(fig.number):
            points_for_bounds = []

            # --- Update Right Hand ---
            if show_right:
                # 获取数据 (21, 3)
                r_data = right_tracker.get_hand_data()
                
                # Check validity (check if all zeros)
                if np.any(r_data):
                    wrist = r_data[0]
                    fingers = r_data[1:] # 20 points
                    
                    # Update Scatter
                    right_scatter._offsets3d = (fingers[:, 0], fingers[:, 1], fingers[:, 2])
                    right_wrist_sc._offsets3d = ([wrist[0]], [wrist[1]], [wrist[2]])
                    
                    # Update lines
                    if show_fingers:
                        segments = _finger_segments_from_21points(r_data)
                        _update_finger_lines(right_lines, segments)
                    
                    points_for_bounds.append(r_data)

            # --- Update Left Hand ---
            if show_left:
                l_data = left_tracker.get_hand_data()
                
                if np.any(l_data):
                    wrist = l_data[0]
                    fingers = l_data[1:]
                    
                    left_scatter._offsets3d = (fingers[:, 0], fingers[:, 1], fingers[:, 2])
                    left_wrist_sc._offsets3d = ([wrist[0]], [wrist[1]], [wrist[2]])
                    
                    if show_fingers:
                        segments = _finger_segments_from_21points(l_data)
                        _update_finger_lines(left_lines, segments)
                    
                    points_for_bounds.append(l_data)

            # --- Dynamic Camera Scaling (EMA) ---
            if points_for_bounds:
                all_points = np.vstack(points_for_bounds)
                # Filter out pure zeros if any glitch happens, though np.any check handles most
                mins = all_points.min(axis=0)
                maxs = all_points.max(axis=0)
                
                center = (mins + maxs) * 0.5
                extent = (maxs - mins).max() * 0.5
                
                # minimal padding
                padding = max(extent * 0.3, 0.05)
                target_limit = max(extent + padding, 0.1)

                if ema_center is None:
                    ema_center = center
                    ema_limit = target_limit
                else:
                    ema_center = (1.0 - alpha) * ema_center + alpha * center
                    ema_limit = (1.0 - alpha) * ema_limit + alpha * target_limit
                
                _set_axes_from_bounds(ax, ema_center, float(ema_limit))

            # --- Refresh Plot ---
            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            
            # Control framerate (~30-60hz cap)
            plt.pause(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping trackers...")
        HandTracker.stop_all()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Matplotlib visualizer using the Shared HandTracker.",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host/IP to bind to (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9000,
        help="Port to listen on (default: 9000).",
    )
    parser.add_argument(
        "--left-only",
        action="store_true",
        help="Only visualize the left hand.",
    )
    parser.add_argument(
        "--right-only",
        action="store_true",
        help="Only visualize the right hand.",
    )
    parser.add_argument(
        "--axis-limit",
        type=float,
        default=0.4,
        help="Initial axis limit scale (default: 0.4).",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.1,
        help="Smoothing factor for camera (default: 0.1).",
    )
    parser.add_argument(
        "--no-fingers",
        action="store_true",
        help="Disable finger lines (scatter only).",
    )
    args = parser.parse_args()

    if args.left_only and args.right_only:
        raise SystemExit("Choose only one of --left-only or --right-only.")

    show_left = not args.right_only
    show_right = not args.left_only

    logging.basicConfig(level=logging.INFO)

    run_visualizer_new(
        host=args.host,
        port=args.port,
        show_left=show_left,
        show_right=show_right,
        axis_limit=args.axis_limit,
        alpha=args.alpha,
        show_fingers=not args.no_fingers,
    )


if __name__ == "__main__":
    main()