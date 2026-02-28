''' 把旧格式的replay数据 转换成 RoboTwin 格式'''
import h5py
import numpy as np
import os

def convert_replay_to_origin(input_path, output_path):
    with h5py.File(input_path, "r") as fin, \
         h5py.File(output_path, "w") as fout:

        # ===============================
        # 1️⃣ 处理 joint → joint_action
        # ===============================
        joint_action_group = fout.create_group("joint_action")

        # left arm
        left_joint = fin["left_arm/joint"][:]
        left_gripper = fin["left_arm/gripper"][:]

        joint_action_group.create_dataset("left_arm", data=left_joint)
        joint_action_group.create_dataset("left_gripper", data=left_gripper)

        # right arm
        right_joint = fin["right_arm/joint"][:]
        right_gripper = fin["right_arm/gripper"][:]

        joint_action_group.create_dataset("right_arm", data=right_joint)
        joint_action_group.create_dataset("right_gripper", data=right_gripper)

        # ===============================
        # 2️⃣ 处理 color → rgb
        # ===============================
        obs_group = fout.create_group("observation")

        def copy_camera(src_group_name, dst_group_name):
            if src_group_name in fin:
                cam_group = obs_group.create_group(dst_group_name)
                rgb_data = fin[f"{src_group_name}/color"][:]
                cam_group.create_dataset("rgb", data=rgb_data)

        # 映射关系
        copy_camera("cam_head", "head_camera")
        copy_camera("cam_left_wrist", "left_camera")
        copy_camera("cam_right_wrist", "right_camera")

    print(f"✅ Converted: {input_path} → {output_path}")


if __name__ == "__main__":
    root_dir = "./data/cover_blocks/x-one/"
    for idx in range(100):
        input_file = root_dir+"data_replay/"+str(idx)+".hdf5"
        output_file = root_dir+"data/episode"+str(idx)+".hdf5"

        convert_replay_to_origin(input_file, output_file)