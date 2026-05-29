from robot.controller.arm_controller import ArmController
from robot.utils.base.data_handler import debug_print

from arx_x5_python_sdk import SingleArm
import atexit
import os
import signal
import threading
import time
import weakref
import numpy as np
from robot.config._GLOBAL_CONFIG import THIRD_PARTY_PATH

_SHUTDOWN_HOLD_SEC = 0.3
_NATIVE_TEARDOWN_SEC = 2.5

_ACTIVE_CONTROLLERS = weakref.WeakSet()
_SHUTDOWN_HOOKS_REGISTERED = False


def _cleanup_all_controllers():
    for controller in list(_ACTIVE_CONTROLLERS):
        controller.cleanup()


def _handle_shutdown_signal(signum, _frame):
    _cleanup_all_controllers()
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


def _register_shutdown_hooks():
    global _SHUTDOWN_HOOKS_REGISTERED
    if _SHUTDOWN_HOOKS_REGISTERED:
        return
    _SHUTDOWN_HOOKS_REGISTERED = True
    atexit.register(_cleanup_all_controllers)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_shutdown_signal)
        except (ValueError, OSError):
            pass


class _NativeOutputFilter:
    def __init__(self, mute_markers):
        self._mute_markers = tuple(mute_markers)
        self._streams = []
        self._users = 0
        self._lock = threading.Lock()


    def acquire(self):
        with self._lock:
            self._users += 1
            if self._streams:
                return

            self._streams = [self._redirect_fd(1), self._redirect_fd(2)]


    def release(self):
        with self._lock:
            if self._users == 0:
                return

            self._users -= 1
            if self._users > 0:
                return

            streams = self._streams
            self._streams = []

        for target_fd, original_fd, _ in streams:
            os.dup2(original_fd, target_fd)

        for _, _, reader in streams:
            reader.join(timeout=1)

        for _, original_fd, _ in streams:
            os.close(original_fd)


    def _redirect_fd(self, target_fd):
        original_fd = os.dup(target_fd)
        read_fd, write_fd = os.pipe()

        os.dup2(write_fd, target_fd)
        os.close(write_fd)

        reader = threading.Thread(
            target=self._forward_filtered_output,
            args=(read_fd, original_fd),
            daemon=True,
        )
        reader.start()

        return target_fd, original_fd, reader


    def _forward_filtered_output(self, read_fd, target_fd):
        with os.fdopen(read_fd, "rb", closefd=True) as pipe_reader:
            for raw_line in iter(pipe_reader.readline, b""):
                line = raw_line.decode("utf-8", errors="replace")

                if any(marker in line for marker in self._mute_markers):
                    continue

                os.write(target_fd, raw_line)


_ARX_OUTPUT_FILTER = _NativeOutputFilter(("ARX方舟无限", "方舟无限"))


class ArxX5Controller(ArmController):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.controller_type = "user_controller"
        self.controller = None
        self._output_filter = _ARX_OUTPUT_FILTER
        self._output_filter.acquire()
        self._output_filter_acquired = True
        self._cleaned_up = False
        _ACTIVE_CONTROLLERS.add(self)
        _register_shutdown_hooks()


    def set_up(self, can:str, arm_type=2, teleop=False):

        config = {
            "can_port": can,
            "type": arm_type,
            "num_joints": 7,
            "dt": 0.05
        }
        self.controller = SingleArm(config)

        # wait for the arm to be ready
        print(f"Waiting for {self.name} to be ready...")
        start_time = time.time()
        while time.time() < start_time + 10:
            time.sleep(0.01)
            if np.all(np.abs(self.controller.get_joint_velocities()) < 0.05):
                break
        time.sleep(3)
        self.change_mode(teleop=False) # set control mode to enable gripper control
        print(f"-----------------{self.name} set up done-----------------")

        if teleop:
            self.change_mode(teleop=True)


    def change_mode(self, teleop):
        if self.controller is None:
            return
        if teleop:
            self.controller.gravity_compensation()
        else:
            curr_joint = self.controller.get_joint_positions()
            self.controller.set_joint_positions(curr_joint)

    def get_state(self):
        state = {}

        state["joint"] = np.array(self.controller.get_joint_positions()[:6])
        state["eef"] = np.array(self.controller.get_ee_pose_xyzrpy())
        
        # -3.4(open)～0(close) -> 0(close)～1(open)
        state["gripper"] = float(self.controller.get_joint_positions()[-1] / -3.4)

        return state


    def set_position(self, position):
        self.controller.set_ee_pose_xyzrpy(np.array(position))

    
    def set_joint(self, joint):
        self.controller.set_joint_positions(np.array(joint))

    def set_gripper(self, gripper):
        """
        0 for close, 1 for open;
        -0.1 for firm grasp
        """

        gripper = gripper * -3.4
        self.controller.set_gripper_pos(gripper)
    
    def reset(self):
        self.controller.go_home()
        time.sleep(2)

    def _shutdown_arm(self):
        if self.controller is None:
            return

        curr_joint = self.controller.get_joint_positions()
        self.controller.set_joint_positions(curr_joint[:6])
        time.sleep(0.05)
        self.controller.protect_mode()
        time.sleep(_SHUTDOWN_HOLD_SEC)

    def cleanup(self):
        if self._cleaned_up:
            return
        self._cleaned_up = True

        print(f"Cleaning up {self.name}...")
        controller = self.controller
        try:
            if controller is not None:
                self._shutdown_arm()
        except Exception as e:
            print(f"[{self.name}] shutdown warning: {e}")
        finally:
            self.controller = None
            if controller is not None:
                del controller
            time.sleep(_NATIVE_TEARDOWN_SEC)
            if self._output_filter_acquired:
                self._output_filter.release()
                self._output_filter_acquired = False

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()
        return False


if __name__ == "__main__":

    import threading

    try:
        arm = ArxX5Controller("test_X5_right")
        arm.set_up("can1")

        move_ee_pose = [0.0, 0.0, 0.06, 0.0, 0.0, 0.0]
        arm.set_position(move_ee_pose)
        move_ee_pose = [0.0, 0.0, 0.03, 0.0, 0.0, 0.0]
        arm.set_position(move_ee_pose)
        # print("当前状态:", arm.get_state())
        time.sleep(3)

        arm.set_gripper(0.0)
        # print(arm.get_state()["gripper"])
        time.sleep(3)
        arm.set_gripper(1.0)
        print(arm.get_state()["gripper"])
        time.sleep(3)
        
        arm.change_mode(teleop=True)
        for i in range(5):
            print(arm.get_state()["gripper"])
            time.sleep(1)
        time.sleep(5)
        arm.change_mode(teleop=False)
        print("----------------------stop teleop------------------------")
        time.sleep(5)
        print("teleop mode test done------------------")

        # while True:

        #     arm.change_mode(teleop=True)

        # thread = threading.Thread(target=arm.change_mode, args=(True), daemon=True)
        # thread.start()

        

    except Exception as e:
        print(f"发生异常: {e}")