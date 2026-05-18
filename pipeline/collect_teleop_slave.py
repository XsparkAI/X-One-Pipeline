import argparse, glob, os
import sys
import numpy as np
from client_server.model_server import ModelServer
from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.robot import get_robot
import threading
import time

from simple_teleop_protocol import configure_qt_environment, decode_color_image, encode_image_payload, split_obs

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", required=True, type=str)
parser.add_argument("--slave_base_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--ip", type=str, required=True, help="IP address of the server")
parser.add_argument("--port", type=int, required=True, help="Port number of the server")
parser.add_argument("--visual", action="store_true", help="enable local PyQt preview window")
parser.add_argument("--visual_freq", type=int, default=15, help="preview refresh frequency when --visual is enabled")
args_cli = parser.parse_args()


class SlaveSessionController:
    def __init__(self, robot, preview_buffer=None):
        self.robot = robot
        self._lock = threading.Lock()
        self._mode = "等待指令"
        self._last_trigger = "无"
        self._last_error = None
        self._recent_events = []
        self._last_move_at = None
        self._preview_lock = threading.Lock()
        self._preview_buffer = preview_buffer

    def _append_event(self, message):
        timestamp = time.strftime("%H:%M:%S")
        with self._lock:
            self._recent_events.insert(0, f"[{timestamp}] {message}")
            self._recent_events = self._recent_events[:8]

    def _get_collection_stats(self):
        collector = getattr(self.robot, "collector", None)
        if collector is None:
            return {
                "task_name": "未知",
                "collected_count": 0,
            }

        collect_cfg = getattr(collector, "collect_cfg", None) or {}
        task_name = collect_cfg.get("task_name") or "未知"
        save_dir = collect_cfg.get("save_dir")
        collect_type = collect_cfg.get("type")

        if not save_dir or not collect_type:
            return {
                "task_name": task_name,
                "collected_count": 0,
            }

        episode_dir = os.path.join(save_dir, task_name, collect_type)
        hdf5_files = glob.glob(os.path.join(episode_dir, "*.hdf5"))
        collected_count = sum(
            1
            for file_path in hdf5_files
            if os.path.splitext(os.path.basename(file_path))[0].isdigit()
        )
        return {
            "task_name": task_name,
            "collected_count": collected_count,
        }

    def _set_mode(self, mode, trigger=None, error=None, append_event=True):
        with self._lock:
            self._mode = mode
            if trigger is not None:
                self._last_trigger = trigger
            self._last_error = error

        if append_event:
            message = mode if trigger is None else f"{trigger} -> {mode}"
            if error:
                message = f"{message} | error={error}"
            self._append_event(message)

    def _invoke_robot_method(self, method_name, obs=None):
        method = getattr(self.robot, method_name, None)
        if callable(method):
            return method(obs) if obs is not None else method()
        return True

    def _run_command(self, command_name, active_mode, done_mode, obs=None, *, log_event=True):
        self._set_mode(active_mode, trigger=command_name, append_event=log_event)
        try:
            result = self._invoke_robot_method(command_name, obs)
        except Exception as exc:
            self._set_mode(f"{active_mode}失败", trigger=command_name, error=str(exc), append_event=log_event)
            raise

        self._set_mode(done_mode, trigger=command_name, append_event=log_event)
        return result

    def get_visual_state(self):
        with self._lock:
            mode = self._mode
            last_trigger = self._last_trigger
            last_error = self._last_error
            recent_events = list(self._recent_events)
            last_move_at = self._last_move_at

        collection_stats = self._get_collection_stats()

        move_age_s = None
        if last_move_at is not None:
            move_age_s = max(0.0, time.monotonic() - last_move_at)

        return {
            "mode": mode,
            "last_trigger": last_trigger,
            "last_error": last_error,
            "recent_events": recent_events,
            "move_age_s": move_age_s,
            "task_name": collection_stats["task_name"],
            "collected_count": collection_stats["collected_count"],
        }

    def attach_preview_buffer(self, preview_buffer):
        with self._preview_lock:
            self._preview_buffer = preview_buffer

    def _ensure_preview_buffer(self, visual_freq):
        with self._preview_lock:
            if self._preview_buffer is None:
                self._preview_buffer = PreviewBuffer(self.robot, visual_freq)
                self._preview_buffer.start()
            else:
                self._preview_buffer.set_visual_freq(visual_freq)
            return self._preview_buffer

    def stop_preview_buffer(self):
        with self._preview_lock:
            preview_buffer = self._preview_buffer
            self._preview_buffer = None

        if preview_buffer is not None:
            preview_buffer.stop()

    def get_visual_data(self, obs=None):
        visual_freq = args_cli.visual_freq
        if isinstance(obs, dict):
            visual_freq = obs.get("visual_freq", visual_freq)

        preview_buffer = self._ensure_preview_buffer(visual_freq)
        frames = preview_buffer.get_latest_frames()
        encoded_frames = {}
        frame_errors = []
        for key, image in frames.items():
            if image is None:
                continue
            try:
                encoded_frames[key] = encode_image_payload(image)
            except Exception as exc:
                frame_errors.append(f"{key}: {exc}")

        preview_error = preview_buffer.get_last_error()
        if frame_errors:
            preview_error = "; ".join(frame_errors)

        return {
            "state": self.get_visual_state(),
            "frames": encoded_frames,
            "preview_error": preview_error,
            "visual_freq": preview_buffer.visual_freq,
        }

    def start(self, obs=None):
        return self._run_command("start", "开始采集中...", "采集中", obs)

    def reset(self, obs=None):
        return self._run_command("reset", "重置中...", "已重置，等待开始", obs)

    def finish(self, obs=None):
        return self._run_command("finish", "结束采集中...", "采集结束", obs)

    def move(self, obs=None):
        with self._lock:
            self._last_move_at = time.monotonic()
            if self._mode not in ("采集中", "开始采集中..."):
                self._mode = "采集中"
            self._last_trigger = "move"

        try:
            return self._invoke_robot_method("move", obs)
        except Exception as exc:
            self._set_mode("采集中断", trigger="move", error=str(exc), append_event=True)
            raise

    def reload_cameras(self, obs=None):
        return self._run_command("reload_cameras", "重载相机中...", "相机已重载", obs)

    def discard_last_episode(self, obs=None):
        self._set_mode("删除上一条数据中...", trigger="discard_last_episode")
        try:
            collector = getattr(self.robot, "collector", None)
            if collector is None:
                result = {"discarded": False, "reason": "collector_unavailable"}
                self._set_mode("删除失败", trigger="discard_last_episode", error=result["reason"])
                return result

            collect_cfg = getattr(collector, "collect_cfg", None)
            if collect_cfg is None:
                result = {"discarded": False, "reason": "collector_config_unavailable"}
                self._set_mode("删除失败", trigger="discard_last_episode", error=result["reason"])
                return result

            save_dir = os.path.join(
                collect_cfg["save_dir"],
                collect_cfg["task_name"],
                collect_cfg["type"],
            )
            hdf5_files = glob.glob(os.path.join(save_dir, "*.hdf5"))
            episode_files = []
            for file_path in hdf5_files:
                file_name = os.path.basename(file_path)
                episode_name, ext = os.path.splitext(file_name)
                if ext != ".hdf5" or not episode_name.isdigit():
                    continue
                episode_files.append((int(episode_name), file_path))

            if not episode_files:
                result = {"discarded": False, "reason": "no_episode"}
                self._set_mode("没有可删除的数据", trigger="discard_last_episode")
                return result

            episode_id, file_path = max(episode_files, key=lambda item: item[0])
            os.remove(file_path)
            collector.episode_index = episode_id
            collector.episode = []
            collector.last_controller_data = None

            result = {
                "discarded": True,
                "episode_id": episode_id,
                "file_path": file_path,
            }
            self._set_mode(f"已删除上一条数据 (episode {episode_id})", trigger="discard_last_episode")
            return result
        except Exception as exc:
            result = {
                "discarded": False,
                "reason": "exception",
                "error": str(exc),
            }
            self._set_mode("删除失败", trigger="discard_last_episode", error=str(exc))
            return result


class PreviewBuffer:
    FRAME_KEYS = (
        ("cam_left_wrist", "Left Wrist"),
        ("cam_head", "Head"),
        ("cam_right_wrist", "Right Wrist"),
    )

    def __init__(self, robot, visual_freq):
        self.robot = robot
        self.visual_freq = max(1, int(visual_freq))
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.latest_frames = {}
        self.last_error = None

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        self.thread = None

    def set_visual_freq(self, visual_freq):
        self.visual_freq = max(1, int(visual_freq))

    def get_latest_frames(self):
        with self.lock:
            return dict(self.latest_frames)

    def get_last_error(self):
        with self.lock:
            return self.last_error

    def _capture_loop(self):
        next_capture_at = time.monotonic()

        while self.running:
            interval = 1.0 / max(1, int(self.visual_freq))
            now = time.monotonic()
            if now < next_capture_at:
                time.sleep(min(next_capture_at - now, 0.01))
                continue

            try:
                _, sensor_data = split_obs(self.robot.get_obs())
                preview_frames = {}
                for key, _ in self.FRAME_KEYS:
                    camera_data = sensor_data.get(key) or {}
                    color_data = camera_data.get("color")
                    if isinstance(color_data, np.ndarray) and color_data.ndim == 3 and color_data.shape[2] == 3:
                        preview_frames[key] = np.ascontiguousarray(color_data)
                    else:
                        # Sensors provide RGB arrays, but JPEG encoding in BaseVisionSensor
                        # goes through OpenCV without an RGB->BGR swap first. After imdecode,
                        # the numeric array already matches the original RGB ordering.
                        preview_frames[key] = decode_color_image(color_data, rgb=False)

                with self.lock:
                    self.latest_frames = preview_frames
                    self.last_error = None
            except Exception as exc:
                with self.lock:
                    self.last_error = str(exc)

            next_capture_at += interval
            if next_capture_at < time.monotonic():
                next_capture_at = time.monotonic()


def run_visual_app(server, preview_buffer, visual_freq):
    configure_qt_environment()

    from PyQt5 import QtCore, QtGui, QtWidgets

    def qimage_from_rgb(image):
        height, width, channel = image.shape
        bytes_per_line = channel * width
        qimage = QtGui.QImage(
            image.data,
            width,
            height,
            bytes_per_line,
            QtGui.QImage.Format_RGB888,
        )
        return qimage.copy()

    class LocalPreviewWorker(QtCore.QThread):
        frame_ready = QtCore.pyqtSignal(object)

        def __init__(self, preview_source, fps):
            super().__init__()
            self.preview_source = preview_source
            self.fps = max(1, int(fps))
            self.running = True

        def run(self):
            interval = 1.0 / self.fps
            while self.running:
                frames = self.preview_source.get_latest_frames()
                if frames:
                    self.frame_ready.emit(frames)
                time.sleep(interval)

        def stop(self):
            self.running = False

    class PreviewWindow(QtWidgets.QWidget):
        def __init__(self, model_server, preview_source, fps):
            super().__init__()
            self.model_server = model_server
            self.preview_source = preview_source
            self.latest_frames = {}
            self.image_panels = []
            self.worker = LocalPreviewWorker(preview_source, fps)

            self.setWindowTitle("Collect Teleop Slave Preview")
            self.resize(1440, 860)
            self._build_ui()

            self.worker.frame_ready.connect(self.on_frames_ready)
            self.worker.start()

            self.status_timer = QtCore.QTimer(self)
            self.status_timer.timeout.connect(self.refresh_status)
            self.status_timer.start(500)
            self.refresh_status()

        def _build_ui(self):
            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setContentsMargins(12, 12, 12, 12)
            main_layout.setSpacing(10)

            self.status_label = QtWidgets.QLabel("当前模式: 服务启动中")
            self.status_label.setAlignment(QtCore.Qt.AlignCenter)
            self.status_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #f4f4f4; background: #1f2937; border-radius: 8px; padding: 10px;")
            main_layout.addWidget(self.status_label)

            status_grid = QtWidgets.QGridLayout()
            status_grid.setHorizontalSpacing(16)
            status_grid.setVerticalSpacing(8)

            self.trigger_label = QtWidgets.QLabel("最近触发: 无")
            self.trigger_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.trigger_label.setStyleSheet("font-size: 14px; font-weight: 600;")
            status_grid.addWidget(self.trigger_label, 0, 0)

            self.flow_label = QtWidgets.QLabel("触发链路: reset -> start -> move(持续) -> finish")
            self.flow_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.flow_label.setStyleSheet("font-size: 14px;")
            status_grid.addWidget(self.flow_label, 0, 1)

            self.meta_label = QtWidgets.QLabel("")
            self.meta_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            status_grid.addWidget(self.meta_label, 1, 0)

            self.dataset_label = QtWidgets.QLabel("")
            self.dataset_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.dataset_label.setStyleSheet("font-size: 14px; font-weight: 600;")
            status_grid.addWidget(self.dataset_label, 2, 0)

            self.error_label = QtWidgets.QLabel("")
            self.error_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.error_label.setStyleSheet("font-size: 13px; color: #b91c1c;")
            status_grid.addWidget(self.error_label, 2, 1)

            main_layout.addLayout(status_grid)

            self.event_list = QtWidgets.QListWidget()
            self.event_list.setMinimumHeight(110)
            self.event_list.setMaximumHeight(150)
            self.event_list.setStyleSheet("background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px;")
            main_layout.addWidget(self.event_list)

            self.image_scroll = QtWidgets.QScrollArea()
            self.image_scroll.setWidgetResizable(True)
            self.image_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

            self.image_container = QtWidgets.QWidget()
            self.image_grid = QtWidgets.QGridLayout(self.image_container)
            self.image_grid.setContentsMargins(0, 0, 0, 0)
            self.image_grid.setHorizontalSpacing(12)
            self.image_grid.setVerticalSpacing(12)

            self.image_labels = {}
            for key, title in PreviewBuffer.FRAME_KEYS:
                panel_widget = QtWidgets.QFrame()
                panel_widget.setStyleSheet("background: #0b1220; border: 1px solid #1f2937; border-radius: 10px;")
                panel_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

                panel = QtWidgets.QVBoxLayout(panel_widget)
                panel.setContentsMargins(10, 10, 10, 10)
                panel.setSpacing(8)

                title_label = QtWidgets.QLabel(title)
                title_label.setAlignment(QtCore.Qt.AlignCenter)
                title_label.setStyleSheet("font-size: 15px; font-weight: 700;")

                image_label = QtWidgets.QLabel("Waiting for image...")
                image_label.setAlignment(QtCore.Qt.AlignCenter)
                image_label.setMinimumSize(320, 240)
                image_label.setStyleSheet("background: #111; color: #ddd; border: 1px solid #444; border-radius: 6px;")
                image_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

                panel.addWidget(title_label)
                panel.addWidget(image_label, stretch=1)
                self.image_panels.append(panel_widget)
                self.image_labels[key] = image_label

            self.image_scroll.setWidget(self.image_container)
            main_layout.addWidget(self.image_scroll, stretch=1)
            self._relayout_image_panels()

            buttons = QtWidgets.QHBoxLayout()
            self.reload_button = QtWidgets.QPushButton("Reload Cameras")
            self.quit_button = QtWidgets.QPushButton("Quit")
            buttons.addWidget(self.reload_button)
            buttons.addWidget(self.quit_button)
            main_layout.addLayout(buttons)

            self.reload_button.clicked.connect(self.reload_cameras)
            self.quit_button.clicked.connect(self.close)

        def _compute_image_columns(self):
            available_width = max(1, self.image_scroll.viewport().width())
            if available_width >= 1380:
                return 3
            if available_width >= 900:
                return 2
            return 1

        def _relayout_image_panels(self):
            while self.image_grid.count():
                item = self.image_grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(self.image_container)

            column_count = self._compute_image_columns()
            for index, panel in enumerate(self.image_panels):
                row = index // column_count
                column = index % column_count
                self.image_grid.addWidget(panel, row, column)

            for column in range(column_count):
                self.image_grid.setColumnStretch(column, 1)

        def refresh_status(self):
            state = {}
            state_getter = getattr(self.model_server.model, "get_visual_state", None)
            if callable(state_getter):
                state = state_getter() or {}

            preview_error = self.preview_source.get_last_error() or "none"
            current_mode = state.get("mode") or "等待指令"
            last_trigger = state.get("last_trigger") or "无"
            task_name = state.get("task_name") or "未知"
            collected_count = state.get("collected_count")
            if collected_count is None:
                collected_count = 0
            move_age_s = state.get("move_age_s")
            move_hint = "move 未触发"
            if move_age_s is not None:
                move_hint = f"最近 move: {move_age_s:.1f}s 前"

            self.status_label.setText(f"当前模式: {current_mode}")
            self.trigger_label.setText(f"最近触发: {last_trigger}")
            self.meta_label.setText(
                f"server={self.model_server.host}:{self.model_server.port} | preview={self.preview_source.visual_freq}Hz | {move_hint} | preview_error={preview_error}"
            )
            self.dataset_label.setText(f"当前任务: {task_name} | 已采集条数: {collected_count}")

            last_error = state.get("last_error")
            self.error_label.setText(f"最近错误: {last_error}" if last_error else "最近错误: 无")

            events = state.get("recent_events") or []
            self.event_list.clear()
            for event in events:
                self.event_list.addItem(event)

        def reload_cameras(self):
            try:
                method = getattr(self.model_server.model, "reload_cameras", None)
                if callable(method):
                    method()
                    self.refresh_status()
            except Exception as exc:
                self.error_label.setText(f"最近错误: reload failed: {exc}")

        def on_frames_ready(self, frames):
            self.latest_frames = frames or {}
            for key, label in self.image_labels.items():
                image = self.latest_frames.get(key)
                if image is None:
                    label.setPixmap(QtGui.QPixmap())
                    label.setText(f"{key}: no image")
                    continue

                pixmap = QtGui.QPixmap.fromImage(qimage_from_rgb(image))
                scaled = pixmap.scaled(label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                label.setText("")
                label.setPixmap(scaled)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._relayout_image_panels()
            if self.latest_frames:
                self.on_frames_ready(self.latest_frames)

        def closeEvent(self, event):
            self.status_timer.stop()
            self.worker.stop()
            self.worker.wait(2000)
            super().closeEvent(event)

    app = QtWidgets.QApplication(sys.argv)
    window = PreviewWindow(server, preview_buffer, visual_freq)
    window.showMaximized()
    return app.exec_()

def main():
    ip = args_cli.ip
    port = args_cli.port
    slave_base_cfg = load_yaml(os.path.join(CONFIG_DIR, f"{args_cli.slave_base_cfg}.yml"))
    task_name = args_cli.task_name
    slave_base_cfg["collect"]["task_name"] = task_name
    
    slave_robot = get_robot(slave_base_cfg)
    slave_robot.set_up(teleop=False)
    session_controller = SlaveSessionController(slave_robot)

    server = ModelServer(session_controller, host=ip, port=port)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()

    preview_buffer = None
    if args_cli.visual:
        preview_buffer = PreviewBuffer(slave_robot, args_cli.visual_freq)
        preview_buffer.start()
        session_controller.attach_preview_buffer(preview_buffer)

        try:
            run_visual_app(server, preview_buffer, args_cli.visual_freq)
        finally:
            session_controller.stop_preview_buffer()
            server.stop()
            thread.join(timeout=2.0)
        return

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    finally:
        session_controller.stop_preview_buffer()
        server.stop()
        thread.join()

if __name__ == "__main__":
    main()