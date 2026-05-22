import argparse, os, sys
import threading
from client_server.model_client import ModelClient
from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.data_handler import is_enter_pressed, flush_stdin, debug_print
from robot.robot import get_robot
from robot.utils.extra.footpedal import FootPedal
import time

from simple_teleop_protocol import configure_qt_environment, decode_color_image

# os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/home/user/miniconda3/envs/Xone/lib/qt5/plugins/platforms"

parser = argparse.ArgumentParser()
parser.add_argument("--master_base_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--ip", type=str, required=True, help="IP address of the master")
parser.add_argument("--port", type=int, required=True, help="port number for the master")
parser.add_argument("--timing_log_every", type=int, default=1, help="log teleop timing every N loops")
parser.add_argument("--timing_warn_ms", type=float, default=15.0, help="warn when a teleop loop exceeds this latency in ms")
parser.add_argument("--pedal_right", type=str, default="/dev/pedal_right", help="pedal path used to start/finish recording")
parser.add_argument("--pedal_left", type=str, default="/dev/pedal_left", help="pedal path used to discard the previous trajectory when idle")
parser.add_argument("--idle_poll_hz", type=int, default=50, help="polling frequency while waiting for pedal input")
parser.add_argument("--pedal_debounce_ms", type=float, default=400.0, help="debounce window for foot pedal trigger events in milliseconds")
parser.add_argument("--teleop_freq", type=int, default=None, help="teleop command frequency in Hz, defaults to collect.save_freq")
parser.add_argument("--visual", action="store_true", help="enable local PyQt preview window")
parser.add_argument("--visual_freq", type=int, default=15, help="preview refresh frequency when --visual is enabled")
args_cli = parser.parse_args()

class MasterSessionController:
    def __init__(self):
        self._lock = threading.Lock()
        self._mode = "初始化中"
        self._last_trigger = "无"
        self._last_error = None
        self._recent_events = []
        self._last_move_at = None
        self._loop_latency_ms = None
        self._current_episode = None
        self._slave_state = {}
        self._slave_preview_error = None
        self._slave_fetch_error = None
        self._visual_freq = None

    def _append_event(self, message):
        timestamp = time.strftime("%H:%M:%S")
        with self._lock:
            self._recent_events.insert(0, f"[{timestamp}] {message}")
            self._recent_events = self._recent_events[:8]

    def set_mode(self, mode, trigger=None, error=None, append_event=True):
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

    def set_episode(self, episode_id):
        with self._lock:
            self._current_episode = episode_id

    def note_move(self, loop_latency_ms=None):
        with self._lock:
            self._last_move_at = time.monotonic()
            self._last_trigger = "move"
            self._mode = "采集中"
            self._loop_latency_ms = loop_latency_ms

    def update_slave_visual(self, payload):
        state = {}
        preview_error = None
        fetch_error = None
        visual_freq = None
        if isinstance(payload, dict):
            state = payload.get("state") or {}
            preview_error = payload.get("preview_error")
            fetch_error = payload.get("error")
            visual_freq = payload.get("visual_freq")

        with self._lock:
            self._slave_state = state
            self._slave_preview_error = preview_error
            self._slave_fetch_error = fetch_error
            self._visual_freq = visual_freq

    def get_visual_state(self):
        with self._lock:
            mode = self._mode
            last_trigger = self._last_trigger
            last_error = self._last_error
            recent_events = list(self._recent_events)
            last_move_at = self._last_move_at
            loop_latency_ms = self._loop_latency_ms
            current_episode = self._current_episode
            slave_state = dict(self._slave_state)
            slave_preview_error = self._slave_preview_error
            slave_fetch_error = self._slave_fetch_error
            visual_freq = self._visual_freq

        move_age_s = None
        if last_move_at is not None:
            move_age_s = max(0.0, time.monotonic() - last_move_at)

        return {
            "mode": mode,
            "last_trigger": last_trigger,
            "last_error": last_error,
            "recent_events": recent_events,
            "move_age_s": move_age_s,
            "loop_latency_ms": loop_latency_ms,
            "current_episode": current_episode,
            "slave_mode": slave_state.get("mode") or "未知",
            "slave_last_trigger": slave_state.get("last_trigger") or "无",
            "slave_last_error": slave_state.get("last_error"),
            "slave_recent_events": slave_state.get("recent_events") or [],
            "task_name": slave_state.get("task_name") or "未知",
            "collected_count": slave_state.get("collected_count", 0),
            "slave_move_age_s": slave_state.get("move_age_s"),
            "preview_error": slave_preview_error,
            "slave_fetch_error": slave_fetch_error,
            "visual_freq": visual_freq,
        }


class DebouncedPedal:
    def __init__(self, pedal, debounce_ms):
        self.pedal = pedal
        self.debounce_seconds = max(0.0, float(debounce_ms) / 1000.0)
        self.last_trigger_time = 0.0

    def clear_pending(self):
        while self.pedal.was_pressed():
            pass

    def poll(self):
        triggered = False
        while self.pedal.was_pressed():
            triggered = True

        if not triggered:
            return False

        now = time.monotonic()
        if now - self.last_trigger_time < self.debounce_seconds:
            return False

        self.last_trigger_time = now
        return True


def wait_for_idle_command(base_pedal, center_pedal, idle_poll_hz, stop_event=None):
    interval = 1.0 / max(1, idle_poll_hz)
    while True:
        if stop_event is not None and stop_event.is_set():
            return "stop"
        if base_pedal.poll():
            return "toggle_collect"
        if center_pedal.poll():
            return "discard_last"
        if is_enter_pressed():
            return "toggle_collect"
        time.sleep(interval)


def client_call_with_retry(client, host, port, func_name, obs=None, retries=1):
    last_error = None
    current_client = client
    for attempt in range(retries + 1):
        try:
            return current_client.call(func_name=func_name, obs=obs), current_client
        except ConnectionError as exc:
            last_error = exc
            current_client.close()
            if attempt >= retries:
                raise
            debug_print("TELEOP", f"RPC {func_name} failed once, reconnecting: {exc}", "WARNING")
            current_client = ModelClient(host=host, port=port)
    raise last_error


def client_send_with_retry(client, host, port, payload, retries=1):
    last_error = None
    current_client = client
    for attempt in range(retries + 1):
        try:
            current_client._send(payload)
            return current_client
        except ConnectionError as exc:
            last_error = exc
            current_client.close()
            if attempt >= retries:
                raise
            debug_print("TELEOP", f"One-way move send failed once, reconnecting: {exc}", "WARNING")
            current_client = ModelClient(host=host, port=port)
    raise last_error


def resolve_teleop_freq(master_base_cfg):
    if args_cli.teleop_freq is not None:
        return max(1, args_cli.teleop_freq)

    collect_cfg = master_base_cfg.get("collect") or {}
    if collect_cfg.get("save_freq") is not None:
        return max(1, int(collect_cfg["save_freq"]))

    return 30


def build_arm_obs(data):
    return {
        "arm": {
            "left_arm": {
                "joint": data["left_arm"]["joint"],
                "gripper": data["left_arm"]["gripper"],
            },
            "right_arm": {
                "joint": data["right_arm"]["joint"],
                "gripper": data["right_arm"]["gripper"],
            }
        }
    }


def reset_master_only(master_robot):
    master_robot.reset()


def reset_master_with_slave_follow(master_robot, client, host, port, teleop_freq):
    reset_error = []

    def _reset_master_target():
        try:
            reset_master_only(master_robot)
        except Exception as exc:
            reset_error.append(exc)

    reset_thread = threading.Thread(target=_reset_master_target)
    reset_thread.start()

    sleep_interval = 1 / max(1, teleop_freq)
    try:
        while reset_thread.is_alive():
            data = master_robot.get_obs()[0]
            obs = build_arm_obs(data)
            client = client_send_with_retry(client, host, port, {"cmd": "move", "obs": obs})
            time.sleep(sleep_interval)

        data = master_robot.get_obs()[0]
        obs = build_arm_obs(data)
        client = client_send_with_retry(client, host, port, {"cmd": "move", "obs": obs})
    finally:
        reset_thread.join()

    if reset_error:
        raise reset_error[0]

    return client


def run_teleop_session(master_robot, base_pedal_raw, center_pedal_raw, session_controller=None, stop_event=None):
    ip = args_cli.ip
    port = args_cli.port
    master_base_cfg = load_yaml(os.path.join(CONFIG_DIR, f"{args_cli.master_base_cfg}.yml"))
    teleop_freq = resolve_teleop_freq(master_base_cfg)
    timing_log_every = max(1, args_cli.timing_log_every)
    timing_warn_ms = args_cli.timing_warn_ms
    idle_poll_hz = max(1, args_cli.idle_poll_hz)
    pedal_debounce_ms = args_cli.pedal_debounce_ms

    base_pedal = DebouncedPedal(base_pedal_raw, pedal_debounce_ms)
    center_pedal = DebouncedPedal(center_pedal_raw, pedal_debounce_ms)
    client = ModelClient(host=ip, port=port)

    step = 0
    flush_stdin()

    try:
        base_pedal.clear_pending()
        center_pedal.clear_pending()
        if session_controller is not None:
            session_controller.set_mode("重置主臂中...", trigger="reset")
        reset_master_only(master_robot)
        base_pedal.clear_pending()
        center_pedal.clear_pending()
        if session_controller is not None:
            session_controller.set_mode("已重置，等待开始", trigger="reset")
        debug_print("TELEOP", "Master robot reset. Waiting for pedal_right to start collecting.", "INFO")

        while stop_event is None or not stop_event.is_set():
            print(f"STEP: {step}")
            if session_controller is not None:
                session_controller.set_mode("空闲，等待开始", trigger="idle")
            debug_print("TELEOP", "Idle. pedal_right starts recording; pedal_left discards the previous trajectory.", "INFO")

            idle_command = wait_for_idle_command(base_pedal, center_pedal, idle_poll_hz, stop_event=stop_event)
            if idle_command == "stop":
                break

            if idle_command == "discard_last":
                if session_controller is not None:
                    session_controller.set_mode("请求删除上一条数据...", trigger="discard_last_episode")
                discard_result, client = client_call_with_retry(client, ip, port, "discard_last_episode")
                if discard_result and discard_result.get("discarded"):
                    if session_controller is not None:
                        session_controller.set_mode(
                            f"已删除上一条数据 (episode {discard_result['episode_id']})",
                            trigger="discard_last_episode",
                        )
                    debug_print("TELEOP", f"Discarded episode {discard_result['episode_id']}", "INFO")
                else:
                    reason = "unknown"
                    if isinstance(discard_result, dict):
                        reason = discard_result.get("reason", reason)
                        error = discard_result.get("error")
                        if error:
                            reason = f"{reason}: {error}"
                    if session_controller is not None:
                        session_controller.set_mode("删除失败", trigger="discard_last_episode", error=reason)
                    debug_print("TELEOP", f"Discard skipped: {reason}", "WARNING")
                continue

            current_step = step
            step += 1
            if session_controller is not None:
                session_controller.set_episode(current_step)
                session_controller.set_mode("开始采集中...", trigger="start")

            _, client = client_call_with_retry(client, ip, port, "start")
            base_pedal.clear_pending()
            center_pedal.clear_pending()

            if session_controller is not None:
                session_controller.set_mode("采集中", trigger="start")
            debug_print("TELEOP", f"Start to collect episode {current_step}. Press pedal_right again to finish.", "INFO")

            teleop_loop_idx = 0
            last_loop_end_ns = None
            while stop_event is None or not stop_event.is_set():
                if base_pedal.poll() or is_enter_pressed():
                    if session_controller is not None:
                        session_controller.set_mode("结束前复位主臂中...", trigger="finish")
                    debug_print("TELEOP", f"Resetting master robot for episode {current_step} while slave keeps following.", "INFO")
                    client = reset_master_with_slave_follow(master_robot, client, ip, port, teleop_freq)
                    _, client = client_call_with_retry(client, ip, port, "finish")
                    base_pedal.clear_pending()
                    center_pedal.clear_pending()
                    if session_controller is not None:
                        session_controller.set_mode("采集结束", trigger="finish")
                    debug_print("TELEOP", f"Finish current trajectory {current_step}. Master reset completed before finish.", "INFO")
                    break

                loop_start_ns = time.monotonic_ns()
                data = master_robot.get_obs()[0]
                after_get_obs_ns = time.monotonic_ns()
                obs = build_arm_obs(data)
                after_pack_ns = time.monotonic_ns()
                client = client_send_with_retry(client, ip, port, {"cmd": "move", "obs": obs})
                after_send_ns = time.monotonic_ns()

                loop_total_ms = (after_send_ns - loop_start_ns) / 1_000_000
                get_obs_ms = (after_get_obs_ns - loop_start_ns) / 1_000_000
                pack_ms = (after_pack_ns - after_get_obs_ns) / 1_000_000
                send_ms = (after_send_ns - after_pack_ns) / 1_000_000
                inter_loop_ms = None
                if last_loop_end_ns is not None:
                    inter_loop_ms = (loop_start_ns - last_loop_end_ns) / 1_000_000

                if session_controller is not None:
                    session_controller.note_move(loop_total_ms)

                if teleop_loop_idx % timing_log_every == 0:
                    timing_msg = (
                        f"idx={teleop_loop_idx} "
                        f"get_obs_ms={get_obs_ms:.3f} "
                        f"pack_ms={pack_ms:.3f} "
                        f"send_ms={send_ms:.3f} "
                        f"loop_ms={loop_total_ms:.3f}"
                    )
                    if inter_loop_ms is not None:
                        timing_msg += f" inter_loop_ms={inter_loop_ms:.3f}"
                    timing_level = "WARNING" if loop_total_ms >= timing_warn_ms else "DEBUG"
                    debug_print("TELEOP_TIMING", timing_msg, timing_level)

                last_loop_end_ns = after_send_ns
                teleop_loop_idx += 1
                time.sleep(1 / teleop_freq)

        if session_controller is not None and (stop_event is not None and stop_event.is_set()):
            session_controller.set_mode("已停止", trigger="stop")
    except Exception as exc:
        if session_controller is not None:
            session_controller.set_mode("运行失败", trigger="error", error=str(exc))
        raise
    finally:
        base_pedal_raw.stop()
        center_pedal_raw.stop()
        client.close()


def run_visual_app(session_controller, host, port, visual_freq):
    configure_qt_environment()

    from PyQt5 import QtCore, QtGui, QtWidgets

    class RemoteVisualWorker(QtCore.QThread):
        data_ready = QtCore.pyqtSignal(object)

        def __init__(self, host, port, fps):
            super().__init__()
            self.host = host
            self.port = port
            self.fps = max(1, int(fps))
            self.running = True
            self.client = ModelClient(host=host, port=port)

        def run(self):
            next_pull_at = time.monotonic()
            while self.running:
                interval = 1.0 / self.fps
                now = time.monotonic()
                if now < next_pull_at:
                    time.sleep(min(next_pull_at - now, 0.01))
                    continue

                payload = None
                try:
                    payload, self.client = client_call_with_retry(
                        self.client,
                        self.host,
                        self.port,
                        "get_visual_data",
                        obs={"visual_freq": self.fps},
                    )
                except Exception as exc:
                    payload = {"error": str(exc), "state": {}, "frames": {}}

                self.data_ready.emit(payload)
                next_pull_at += interval
                if next_pull_at < time.monotonic():
                    next_pull_at = time.monotonic()

        def stop(self):
            self.running = False
            self.client.close()
            self.wait(2000)

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

    class PreviewWindow(QtWidgets.QWidget):
        frame_keys = (
            ("cam_left_wrist", "Left Wrist"),
            ("cam_head", "Head"),
            ("cam_right_wrist", "Right Wrist"),
        )

        def __init__(self, controller, host, port, fps):
            super().__init__()
            self.session_controller = controller
            self.host = host
            self.port = port
            self.latest_frames = {}
            self.image_panels = []
            self.worker = RemoteVisualWorker(host, port, fps)

            self.setWindowTitle("Collect Teleop Master Preview")
            self.resize(1440, 860)
            self._build_ui()

            self.worker.data_ready.connect(self.on_visual_data_ready)
            self.worker.start()

            self.status_timer = QtCore.QTimer(self)
            self.status_timer.timeout.connect(self.refresh_status)
            self.status_timer.start(500)
            self.refresh_status()

        def _build_ui(self):
            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setContentsMargins(12, 12, 12, 12)
            main_layout.setSpacing(10)

            self.status_label = QtWidgets.QLabel("当前模式: 主控启动中")
            self.status_label.setAlignment(QtCore.Qt.AlignCenter)
            self.status_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #f4f4f4; background: #1f2937; border-radius: 8px; padding: 10px;")
            main_layout.addWidget(self.status_label)

            status_grid = QtWidgets.QGridLayout()
            status_grid.setHorizontalSpacing(16)
            status_grid.setVerticalSpacing(8)

            self.trigger_label = QtWidgets.QLabel("最近发送: 无")
            self.trigger_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.trigger_label.setStyleSheet("font-size: 14px; font-weight: 600;")
            status_grid.addWidget(self.trigger_label, 0, 0)

            self.flow_label = QtWidgets.QLabel("主控链路: idle -> start -> move(持续) -> finish")
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

            self.slave_status_label = QtWidgets.QLabel("")
            self.slave_status_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.slave_status_label.setStyleSheet("font-size: 14px;")
            status_grid.addWidget(self.slave_status_label, 1, 1)

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
            for key, title in self.frame_keys:
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
            state = self.session_controller.get_visual_state()
            current_mode = state.get("mode") or "等待指令"
            last_trigger = state.get("last_trigger") or "无"
            task_name = state.get("task_name") or "未知"
            collected_count = state.get("collected_count") or 0
            current_episode = state.get("current_episode")
            slave_mode = state.get("slave_mode") or "未知"
            slave_last_trigger = state.get("slave_last_trigger") or "无"
            visual_freq = state.get("visual_freq") or self.worker.fps

            move_age_s = state.get("move_age_s")
            move_hint = "move 未发送"
            if move_age_s is not None:
                move_hint = f"最近 move: {move_age_s:.1f}s 前"

            loop_latency_ms = state.get("loop_latency_ms")
            latency_hint = "loop=NA"
            if loop_latency_ms is not None:
                latency_hint = f"loop={loop_latency_ms:.2f}ms"

            episode_hint = "当前 episode: 未开始"
            if current_episode is not None:
                episode_hint = f"当前 episode: {current_episode}"

            self.status_label.setText(f"当前模式: {current_mode}")
            self.trigger_label.setText(f"最近发送: {last_trigger}")
            self.meta_label.setText(
                f"server={self.host}:{self.port} | preview={visual_freq}Hz | {move_hint} | {latency_hint}"
            )
            self.dataset_label.setText(f"当前任务: {task_name} | 已采集条数: {collected_count} | {episode_hint}")
            self.slave_status_label.setText(f"Slave状态: {slave_mode} | Slave最近触发: {slave_last_trigger}")

            error_parts = []
            if state.get("last_error"):
                error_parts.append(f"master={state['last_error']}")
            if state.get("slave_last_error"):
                error_parts.append(f"slave={state['slave_last_error']}")
            if state.get("preview_error"):
                error_parts.append(f"preview={state['preview_error']}")
            if state.get("slave_fetch_error"):
                error_parts.append(f"fetch={state['slave_fetch_error']}")
            self.error_label.setText(f"最近错误: {' | '.join(error_parts) if error_parts else '无'}")

            events = []
            events.extend(state.get("recent_events") or [])
            events.extend((state.get("slave_recent_events") or [])[:4])
            self.event_list.clear()
            for event in events[:8]:
                self.event_list.addItem(event)

        def reload_cameras(self):
            temp_client = None
            try:
                temp_client = ModelClient(host=self.host, port=self.port)
                client_call_with_retry(temp_client, self.host, self.port, "reload_cameras")
                self.refresh_status()
            except Exception as exc:
                self.session_controller.set_mode("重载相机失败", trigger="reload_cameras", error=str(exc))
            finally:
                if temp_client is not None:
                    temp_client.close()

        def on_visual_data_ready(self, payload):
            self.session_controller.update_slave_visual(payload)
            frames = {}
            if isinstance(payload, dict):
                frames = payload.get("frames") or {}

            decoded_frames = {}
            for key, image_payload in frames.items():
                image = decode_color_image(image_payload, rgb=False)
                if image is not None:
                    decoded_frames[key] = image

            if decoded_frames:
                self.latest_frames = decoded_frames

            self._render_latest_frames()
            self.refresh_status()

        def _render_latest_frames(self):
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
                self._render_latest_frames()

        def closeEvent(self, event):
            self.status_timer.stop()
            self.worker.stop()
            super().closeEvent(event)

    app = QtWidgets.QApplication(sys.argv)
    window = PreviewWindow(session_controller, host, port, visual_freq)
    window.showMaximized()
    return app.exec_()


def main():
    ip = args_cli.ip
    port = args_cli.port
    master_base_cfg = load_yaml(os.path.join(CONFIG_DIR, f"{args_cli.master_base_cfg}.yml"))
    master_robot = get_robot(master_base_cfg)
    master_robot.set_up(teleop=True)
    base_pedal_raw = FootPedal(args_cli.pedal_right)
    center_pedal_raw = FootPedal(args_cli.pedal_left)
    session_controller = MasterSessionController()

    if args_cli.visual:
        stop_event = threading.Event()
        teleop_thread = threading.Thread(
            target=run_teleop_session,
            args=(master_robot, base_pedal_raw, center_pedal_raw, session_controller, stop_event),
            daemon=True,
        )
        teleop_thread.start()

        try:
            run_visual_app(session_controller, ip, port, args_cli.visual_freq)
        finally:
            stop_event.set()
            teleop_thread.join(timeout=2.0)
        return

    run_teleop_session(master_robot, base_pedal_raw, center_pedal_raw, session_controller)
    
if __name__ == "__main__":
    main()