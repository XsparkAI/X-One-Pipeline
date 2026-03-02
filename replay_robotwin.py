import h5py
import argparse
import time
import os

from robot.robot import get_robot
from robot.utils.base.load_file import load_yaml
import pdb

def read_hdf5(file_path):
    with h5py.File(file_path, "r") as f:
        left_arm = f["joint_action/left_arm"][:]
        left_gripper = f["joint_action/left_gripper"][:]
        right_arm = f["joint_action/right_arm"][:]
        right_gripper = f["joint_action/right_gripper"][:]

    return left_arm, left_gripper, right_arm, right_gripper


def run(args):
    # 初始化机器人
    base_cfg = load_yaml(args.base_cfg_path)
    robot = get_robot(base_cfg)
    robot.set_up(teleop=False)
    robot.reset()
    robotwin_data_path = args.robotwin_data_path
    idx = args.idx
    data_path = os.path.join(robotwin_data_path, "data", f"episode{idx}.hdf5")
    
    # 读取数据
    left_arm, left_gripper, right_arm, right_gripper = read_hdf5(data_path)
        
    length = len(left_arm)

    gripper_max_real = max(left_gripper)
    gripper_min_real = min(left_gripper)
    print(f"l g max: {max(left_gripper)}")
    print(f"l g min: {min(left_gripper)}")
    print(f"r g max: {max(right_gripper)}")
    print(f"r g min: {min(right_gripper)}")

    # 人为设定一个夹爪范围
    gripper_max_des = 1.0
    gripper_min_des = 0.5

    # 将已有数据中的夹爪范围 线性映射到 人为设定的范围
    left_gripper = (left_gripper - gripper_min_real) / (gripper_max_real - gripper_min_real) * (gripper_max_des - gripper_min_des) + gripper_min_des
    right_gripper = (right_gripper - gripper_min_real) / (gripper_max_real - gripper_min_real) * (gripper_max_des - gripper_min_des) + gripper_min_des
    print("after mapping: ")
    print(f"l g max: {max(left_gripper)}")
    print(f"l g min: {min(left_gripper)}")
    print(f"r g max: {max(right_gripper)}")
    print(f"r g min: {min(right_gripper)}")

    print(f"Trajectory length: {length}")

    for i in range(length):
        move_data = {
            "arm": {
                "left_arm": {
                    "joint": left_arm[i].tolist(),
                    "gripper": float(left_gripper[i]),
                },
                "right_arm": {
                    "joint": right_arm[i].tolist(),
                    "gripper": float(right_gripper[i]),
                },
            }
        }

        robot.move(move_data)
        time.sleep(1.0 / 10.0)  # 10 Hz
        data = robot.get_obs()
        robot.collect(data)
        # pdb.set_trace() # for debug

    robot.finish(episode_id=idx)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_cfg_path", type=str, required=True)
    parser.add_argument("--robotwin_data_path", type=str, required=True)
    parser.add_argument("--idx", type=int, required=True)

    args = parser.parse_args()

    run(args)