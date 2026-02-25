import h5py

file_path = "/home/xspark-ai/project/RoboTwin/data/place_shoe/demo_clean/data/episode0.hdf5"

# def print_hdf5_structure(name, obj):
#     if isinstance(obj, h5py.Dataset):
#         print(f"[DATASET] {name}  shape={obj.shape}  dtype={obj.dtype}")
#     elif isinstance(obj, h5py.Group):
#         print(f"[GROUP]   {name}")

# with h5py.File(file_path, "r") as f:
#     print("=" * 80)
#     print("HDF5 Structure:")
#     print("=" * 80)
#     f.visititems(print_hdf5_structure)
#     print("=" * 80)

import h5py
import numpy as np

with h5py.File(file_path, "r") as f:
    left_arm = f["joint_action/left_arm"][:]
    left_gripper = f["joint_action/left_gripper"][:]
    right_arm = f["joint_action/right_arm"][:]
    right_gripper = f["joint_action/right_gripper"][:]

print("left_arm shape:", left_arm.shape)
print("left_gripper shape:", left_gripper.shape)
print("right_arm shape:", right_arm.shape)
print("right_gripper shape:", right_gripper.shape)

print("\nFirst 5 rows of left_arm:")
print(right_arm[:5])

print("\nFirst 5 values of left_gripper:")
print(right_gripper[:5])

