import argparse, os
import threading
from client_server.model_client import ModelClient
from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.data_handler import is_enter_pressed, flush_stdin, debug_print
from robot.robot import get_robot
from robot.utils.extra.footpedal import FootPedal
import time

parser = argparse.ArgumentParser()
parser.add_argument("--master_base_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--ip", type=str, required=True, help="IP address of the master")
parser.add_argument("--port", type=int, required=True, help="port number for the master")
parser.add_argument("--teleop_freq", type=int, default=60, help="freq for teleop")
parser.add_argument("--timing_log_every", type=int, default=1, help="log teleop timing every N loops")
parser.add_argument("--timing_warn_ms", type=float, default=15.0, help="warn when a teleop loop exceeds this latency in ms")
parser.add_argument("--pedal_base", type=str, default="/dev/pedal_base", help="pedal path used to start/finish recording")
parser.add_argument("--pedal_center", type=str, default="/dev/pedal_center", help="pedal path used to discard the previous trajectory when idle")
parser.add_argument("--idle_poll_hz", type=int, default=50, help="polling frequency while waiting for pedal input")
parser.add_argument("--pedal_debounce_ms", type=float, default=400.0, help="debounce window for foot pedal trigger events in milliseconds")
args_cli = parser.parse_args()


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


def wait_for_idle_command(base_pedal, center_pedal, idle_poll_hz):
    interval = 1.0 / max(1, idle_poll_hz)
    while True:
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


def main():
    ip = args_cli.ip
    port = args_cli.port
    master_base_cfg = load_yaml(os.path.join(CONFIG_DIR, f"{args_cli.master_base_cfg}.yml"))
    teleop_freq = args_cli.teleop_freq
    timing_log_every = max(1, args_cli.timing_log_every)
    timing_warn_ms = args_cli.timing_warn_ms
    idle_poll_hz = max(1, args_cli.idle_poll_hz)
    pedal_debounce_ms = args_cli.pedal_debounce_ms
    master_robot = get_robot(master_base_cfg)
    master_robot.set_up(teleop=True)
    base_pedal_raw = FootPedal(args_cli.pedal_base)
    center_pedal_raw = FootPedal(args_cli.pedal_center)
    base_pedal = DebouncedPedal(base_pedal_raw, pedal_debounce_ms)
    center_pedal = DebouncedPedal(center_pedal_raw, pedal_debounce_ms)
    
    client = ModelClient(host=ip, port=port)

    # Keep main thread alive until KeyboardInterrupt
    step = 0

    # clean keyboard
    flush_stdin()

    try:
        base_pedal.clear_pending()
        center_pedal.clear_pending()
        reset_master_only(master_robot)
        base_pedal.clear_pending()
        center_pedal.clear_pending()
        debug_print("TELEOP", "Master robot reset. Waiting for pedal_base to start collecting.", "INFO")

        while True:
            print(f"STEP: {step}")
            debug_print("TELEOP", "Idle. pedal_base starts recording; pedal_center discards the previous trajectory.", "INFO")

            idle_command = wait_for_idle_command(base_pedal, center_pedal, idle_poll_hz)
            if idle_command == "discard_last":
                discard_result, client = client_call_with_retry(client, ip, port, "discard_last_episode")
                if discard_result and discard_result.get("discarded"):
                    debug_print("TELEOP", f"Discarded episode {discard_result['episode_id']}", "INFO")
                else:
                    reason = "unknown"
                    if isinstance(discard_result, dict):
                        reason = discard_result.get("reason", reason)
                        error = discard_result.get("error")
                        if error:
                            reason = f"{reason}: {error}"
                    debug_print("TELEOP", f"Discard skipped: {reason}", "WARNING")
                continue

            current_step = step
            step += 1

            _, client = client_call_with_retry(client, ip, port, "start")
            base_pedal.clear_pending()
            center_pedal.clear_pending()

            debug_print("TELEOP", f"Start to collect episode {current_step}. Press pedal_base again to finish.", "INFO")

            teleop_loop_idx = 0
            last_loop_end_ns = None
            while True:
                if base_pedal.poll() or is_enter_pressed():
                    debug_print("TELEOP", f"Resetting master robot for episode {current_step} while slave keeps following.", "INFO")
                    client = reset_master_with_slave_follow(master_robot, client, ip, port, teleop_freq)
                    _, client = client_call_with_retry(client, ip, port, "finish")
                    base_pedal.clear_pending()
                    center_pedal.clear_pending()
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
    finally:
        base_pedal_raw.stop()
        center_pedal_raw.stop()
        client.close()
    
if __name__ == "__main__":
    main()