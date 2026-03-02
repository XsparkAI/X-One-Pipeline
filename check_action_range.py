import h5py
import numpy as np

episode_idx = 20

file_a = f"./data/cover_blocks/demo_clean/data/episode{episode_idx}.hdf5" # orgin data
file_b = f"./data/cover_blocks/x-one/data/episode{episode_idx}.hdf5" # replay data

def load_actions(path):
    with h5py.File(path, "r") as f:
        left_arm = f["joint_action/left_arm"][:]
        right_arm = f["joint_action/right_arm"][:]
        left_gripper = f["joint_action/left_gripper"][:]
        right_gripper = f["joint_action/right_gripper"][:]
    return left_arm, right_arm, left_gripper, right_gripper


# 读取
la1, ra1, lg1, rg1 = load_actions(file_a)
la2, ra2, lg2, rg2 = load_actions(file_b)


# 把gripper进行线性映射
gripper_max_real = max(lg1)
gripper_min_real = min(lg1)

# 人为设定一个夹爪范围
gripper_max_des = 1.0
gripper_min_des = 0.5

# 将已有数据中的夹爪范围 线性映射到 人为设定的范围
lg1 = (lg1 - gripper_min_real) / (gripper_max_real - gripper_min_real) * (gripper_max_des - gripper_min_des) + gripper_min_des
rg1 = (rg1 - gripper_min_real) / (gripper_max_real - gripper_min_real) * (gripper_max_des - gripper_min_des) + gripper_min_des



# ======================
# 作差
# ======================

diff_left_arm = la1 - la2
diff_right_arm = ra1 - ra2
diff_left_gripper = lg1 - lg2
diff_right_gripper = rg1 - rg2


# 求 max
max_per_joint_left = np.abs(diff_left_arm).max(axis=0)
max_per_joint_right = np.abs(diff_right_arm).max(axis=0)
overall_max_left_arm = max_per_joint_left.max()
overall_max_right_arm = max_per_joint_right.max()

max_norm_left_gripper = np.abs(diff_left_gripper).max()
max_norm_right_gripper = np.abs(diff_right_gripper).max()

print(f"Left Arm Max Norm:      {overall_max_left_arm:.6f}")
print(f"Right Arm Max Norm:     {overall_max_right_arm:.6f}")
print(f"Left Gripper Max Abs:   {max_norm_left_gripper:.6f}")
print(f"Right Gripper Max Abs:  {max_norm_right_gripper:.6f}")
