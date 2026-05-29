import h5py, pickle, yaml
import os
import numpy as np
import json
from pathlib import Path

def load_yaml(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_pkl(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")
    with open(file_path, "rb") as f:
        data = pickle.load(f)
    return data


def load_hdf5(file_path: str, key: str | None = None):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")
    with h5py.File(file_path, "r") as f:
        if key is not None:
            return np.array(f[key])

        def walk(group):
            out = {}
            for k, v in group.items():
                out[k] = v[()] if isinstance(v, h5py.Dataset) else walk(v)
            return out

        return walk(f)


def load_robotwin_hdf5(file_path):
    """Load data from HDF5 file in RoboTwin format"""
    if h5py is None:
        print("Error: h5py is required. Install with: pip install h5py")
        return None

    if not os.path.isfile(file_path):
        print(f"Dataset does not exist at \n{file_path}\n")
        return None

    with h5py.File(file_path, "r") as root:
        left_gripper, left_arm = (
            root["/joint_action/left_gripper"][()],
            root["/joint_action/left_arm"][()],
        )
        right_gripper, right_arm = (
            root["/joint_action/right_gripper"][()],
            root["/joint_action/right_arm"][()],
        )

    control_seq = {"left_arm": left_arm, "left_gripper": left_gripper, "right_arm": right_arm, "right_gripper": right_gripper}
    return control_seq


def load_json(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")
    p = Path(file_path)
    with p.open("r", encoding="utf-8") as f:
        s = f.read().strip()
        if s == "":
            return {}
        return json.loads(s)

