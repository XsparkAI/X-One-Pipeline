from robot.controller.arm_controller import ArmController
from robot.utils.base.data_handler import debug_print

from arx_x5_python_sdk import SingleArm
import os
import threading
import time
import numpy as np
from robot.config._GLOBAL_CONFIG import THIRD_PARTY_PATH


class ArxX5Controller(ArmController):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.controller_type = "user_controller"
        self.controller = None
        self._native_output_active = False
        self._native_stdout_original_fd = None
        self._native_stderr_original_fd = None
        self._native_stdout_reader = None
        self._native_stderr_reader = None
        self._mute_markers = ("ARX方舟无限", "方舟无限")
        self._start_native_output_filter()


    def _forward_filtered_output(self, read_fd, target_fd):
        with os.fdopen(read_fd, "rb", closefd=True) as pipe_reader:
            for raw_line in iter(pipe_reader.readline, b""):
                try:
                    line = raw_line.decode("utf-8", errors="replace")
                except Exception:
                    line = raw_line.decode(errors="replace")

                if any(marker in line for marker in self._mute_markers):
                    continue

                os.write(target_fd, raw_line)


    def _start_native_output_filter(self):
        if self._native_output_active:
            return

        self._native_stdout_original_fd = os.dup(1)
        self._native_stderr_original_fd = os.dup(2)

        stdout_read_fd, stdout_write_fd = os.pipe()
        stderr_read_fd, stderr_write_fd = os.pipe()

        os.dup2(stdout_write_fd, 1)
        os.dup2(stderr_write_fd, 2)
        os.close(stdout_write_fd)
        os.close(stderr_write_fd)

        self._native_stdout_reader = threading.Thread(
            target=self._forward_filtered_output,
            args=(stdout_read_fd, self._native_stdout_original_fd),
            daemon=True,
        )
        self._native_stderr_reader = threading.Thread(
            target=self._forward_filtered_output,
            args=(stderr_read_fd, self._native_stderr_original_fd),
            daemon=True,
        )
        self._native_stdout_reader.start()
        self._native_stderr_reader.start()
        self._native_output_active = True


    def _stop_native_output_filter(self):
        if not self._native_output_active:
            return

        os.dup2(self._native_stdout_original_fd, 1)
        os.dup2(self._native_stderr_original_fd, 2)
        os.close(self._native_stdout_original_fd)
        os.close(self._native_stderr_original_fd)
        self._native_stdout_original_fd = None
        self._native_stderr_original_fd = None
        self._native_output_active = False

        if self._native_stdout_reader is not None:
            self._native_stdout_reader.join(timeout=1)
            self._native_stdout_reader = None
        if self._native_stderr_reader is not None:
            self._native_stderr_reader.join(timeout=1)
            self._native_stderr_reader = None


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

        gripper = gripper * 3.4 - 3.4
        self.controller.set_gripper_pos(gripper)

    
    def reset(self):
        self.controller.go_home()
        time.sleep(2)


    def cleanup(self):
        print("Cleaning up ArxX5Controller...")
        self.reset()
        self._stop_native_output_filter()
        self.controller = None
        time.sleep(3)



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


    finally:
        arm.reset()