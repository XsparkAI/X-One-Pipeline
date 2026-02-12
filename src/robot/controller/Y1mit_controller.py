from robot.controller.arm_controller import ArmController
from robot.utils.base.data_handler import debug_print

from y1_sdk import Y1SDKInterface, ControlMode
import os
import time
from robot.config._GLOBAL_CONFIG import THIRD_PARTY_PATH
'''
Piper base code from:
https://github.com/agilexrobotics/piper_sdk.git
'''

package_path = os.path.join(THIRD_PARTY_PATH, "y1_sdk_python/y1_ros/src/y1_controller/")
if not os.path.exists(package_path):
    package_path = os.path.join(THIRD_PARTY_PATH, "y1_sdk_python/y1_ros2/src/y1_controller/")

class Y1Controller(ArmController):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.controller_type = "user_controller"
        self.controller = None
    
    def set_up(self, can:str, arm_end_type=3, mode="nrt"):
        self.arm_end_type = arm_end_type
        if arm_end_type == 0:
            urdf_path = os.path.join(package_path, f"urdf/y1_no_gripper.urdf")
        elif arm_end_type == 1:
            urdf_path = os.path.join(package_path, f"urdf/y1_gripper_t.urdf")
        elif arm_end_type == 2:
            urdf_path = os.path.join(package_path, f"urdf/y1_gripper_g.urdf")
        elif arm_end_type == 3:
            urdf_path = os.path.join(package_path, f"urdf/y1_with_gripper.urdf")
        
        self.controller = Y1SDKInterface(
            can_id=can,
            urdf_path=urdf_path,
            arm_end_type=arm_end_type,
            enable_arm=True,
        )

        if not self.controller.Init():
            debug_print(self.name, "Init Fail!", "ERROR")

        self.change_mode(mode)

    def change_mode(self, mode:str):
        if mode == "teleop":
            self.controller.SetArmControlMode(ControlMode.GRAVITY_COMPENSATION)
        elif mode=="nrt":
            self.controller.SetArmControlMode(ControlMode.NRT_JOINT_POSITION)
        elif mode=="mit":
            self.controller.SetArmControlMode(ControlMode.MIT_CONTROL)
        else:
            raise ValueError(f"Unsupported mode: {mode}. Supported modes are 'teleop', 'nrt', and 'mit'.")
        
    def get_state(self):
        state = {}
        
        eef = self.controller.GetArmEndPose()
        joint = self.controller.GetJointPosition()
        vel = self.controller.GetJointVelocity()
        torgue = self.controller.GetJointEffort()
        state["end_pose"] = eef
        state["joint_position"] = joint[:6]
        state["joint_velocity"] = vel[:6]
        state["joint_torque"] = torgue[:6]

        if self.arm_end_type != 0:
            state["gripper"] = joint[6] / 100

        return state

    # All returned values are expressed in meters,if the value represents an angle, it is returned in radians
    def set_position(self, position):
        self.controller.SetArmEndPose(list(position))
    
    def set_joint(self, joint):
        try:
            debug_print("Y1_controller", f"\033[92m{self.name:<10}\033[0m: "f"[{', '.join(f'{x:9.3f}' for x in joint)}]", "DEBUG")
            self.controller.SetArmJointPosition(list(joint), 5)
        except Exception as e:
            debug_print(self.name, f"set_joint to: {joint}", "ERROR")
            debug_print(self.name, f"set_joint error: {e}", "ERROR")

    # The input gripper value is in the range [0, 1], representing the degree of opening.
    def set_gripper(self, gripper):
        gripper = gripper * 100
        self.controller.SetGripperStroke(gripper)

    def set_joint_torque(self, torque):
        try:
            debug_print("Y1_controller", f"\033[92m{self.name:<10}\033[0m: "f"[{', '.join(f'{x:9.3f}' for x in torque)}]", "DEBUG")
            self.controller.MitControlArm(list(torque))
        except Exception as e:
            debug_print(self.name, f"set_joint_torque to: {torque}", "ERROR")
            debug_print(self.name, f"set_joint_torque error: {e}", "ERROR")
    
    def __del__(self):
        try:
            if hasattr(self, 'controller'):
                # Add any necessary cleanup for the arm controller
                pass
        except:
            pass
    
from robot.utils.base.data_handler import is_enter_pressed
import csv
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

def collect_tarj(robot):
    # 采集时长（秒）
    FREQ = 100  # Hz
    DURATION = 2  # 采集10秒，可自行修改
    PERIOD = 1.0 / FREQ
    # CSV 文件名
    csv_filename = f"data/traj_p.csv"

    # 写 CSV 文件头
    with open(csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        print("开始采集数据...")
        while not is_enter_pressed():
            positions = robot.get_state()["joint_position"]
            # 保存到 CSV
            writer.writerow(positions)

            time.sleep(PERIOD)

def run_tarj(robot):
    FREQ = 100  # Hz
    PERIOD = 1.0 / FREQ

    points = np.loadtxt("data/traj_p.csv", delimiter=",")

    points = points[6*FREQ : -6*FREQ , :]

    # ===============================
    # 先运动到第一个点（安全过渡）
    # ===============================
    first_point = points[0]
    robot.set_joint(np.array(first_point))
    time.sleep(5)  # 给一些时间到达第一个点

    # ===============================
    # 新 CSV 文件用于记录实际执行数据
    # ===============================
    new_csv_filename = f"data/executed_traj_pvt.csv"

    with open(new_csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        # ===============================
        # 执行轨迹 + 采集反馈
        # ===============================
        print("开始执行轨迹并采集数据...")
        for point in points:
            # 发送目标点（这里只设置位置，速度和力矩限制可以调整）
            robot.set_joint(np.array(point))

            # 提取数据
            data = robot.get_state()
            positions = data["joint_position"]
            velocities = data["joint_velocity"]
            currents = data["joint_torque"]

            # 保存到 CSV
            writer.writerow(positions + velocities + currents)
            time.sleep(PERIOD)

    print(f"轨迹执行完成，已保存到 {new_csv_filename}")


    robot.set_joint(np.array([0] * 7))

    time.sleep(5)

def is_ld(calc):
    def butter_lowpass_filter(data, cutoff, fs, order=4):
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype="low", analog=False)
        y = filtfilt(b, a, data, axis=0)  # 双向滤波避免相位延迟
        return y

    points = np.loadtxt("data/executed_traj_pvt.csv", delimiter=",")
    import pdb;pdb.set_trace()
    points = points[1200:, :]

    # 你存的格式不确定 列数可能有偏差，这里要改成你的实际格式
    positions = points[:, :6]  # 接下来 7 列是关节位置
    velocities = points[:, 6:12]  # 7 列是关节速度
    taus = points[:, 12:18]  # 7 列是关节力矩

    # 参数示例：
    fs = 100  # 采样频率 (Hz) —— 这个需要你确认
    cutoff = 2.0  # 截止频率 (Hz) —— 保留低频变化，去掉快速噪声
    order = 4
    taus_filtered = butter_lowpass_filter(taus, cutoff, fs, order) 

    regressors = np.zeros((len(positions), 6, 59))

    for i in range(len(positions)):
        regressor = calc.calc(
            positions[i], velocities[i], np.zeros_like(velocities[i])
        )  # shape (7, 69)
        regressors[i] = regressor

    # tau = regressor@beta
    beta = np.linalg.pinv(
        regressors.reshape(len(positions) * 6, -1)
    ) @ taus_filtered.reshape(len(positions) * 6, -1)

    np.save("ls_id_beta.npy", beta)

    pred_taus = regressors @ beta

    # plot, 对比真实值和预测值, 真实值为实线(蓝色), 预测值为虚线(红色)
    # 使用subplot，设置颜色
    fig, axs = plt.subplots(6, 1, figsize=(12, 12))

    for p in range(6):
        axs[p].plot(taus[:, p], label=f"tau_{p+1}", color="blue")
        axs[p].plot(
            pred_taus[:, p], "--", label=f"pred_tau_{p+1}", color="red"
        )  # dashed line
        axs[p].set_xlabel("Time step")
        axs[p].set_ylabel("Joint Torque")
        axs[p].set_title(f"LS Tau Prediction for tau_{p+1}")
        axs[p].legend(loc="upper right", fontsize="small", ncol=2)
    plt.tight_layout()

    plt.savefig("data/ls_id_results.png", dpi=300)
    plt.show()

if __name__=="__main__":
    robot = Y1Controller("test_y1_right")
    robot.set_up("can2", 0, "nrt")
    robot.set_joint([0., 0., 0., 0., 0, 0])
    time.sleep(3)

    robot.change_mode("mit")
    time.sleep(1)
    
    from .calc_dynamics import CalcDynamics
    # calc = CalcDynamics()

    # collect_tarj(robot)
    # run_tarj(robot)
    # is_ld(calc)

    beta = np.load("ls_id_beta.npy")
    dynamics_regressor = CalcDynamics()
    while True:
        data = robot.get_state()
        positions = data["joint_position"]
        velocities = data["joint_velocity"]

        regressor = dynamics_regressor.calc(positions, velocities * 0, np.zeros(6))

        tau = regressor @ beta

        robot.set_joint_torque(tau.ravel().tolist())