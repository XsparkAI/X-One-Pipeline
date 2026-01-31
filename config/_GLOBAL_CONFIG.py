import os

current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)

ROOT_DIR = os.path.join(current_dir, "..")

CONFIG_DIR = os.path.join(ROOT_DIR, "config")

ROBOTS_PATH = os.path.join(ROOT_DIR, "assets/robots")
DATA_PATH = os.path.join(ROOT_DIR, "data")
COLLECT_CONFIG_PATH = os.path.join(ROOT_DIR, "collect_cfg")

ROBOT_CAN = {
    "left_arm": "can1",
    "right_arm": "can0",
}

CAMERA_SERIALS = {
    'head': "/dev/head_camera",        # Candidate index
    'left_wrist': "/dev/left_wrist_camera",  # Candidate index
    'right_wrist': "/dev/right_wrist_camera", # Candidate index
}

START_POSITION_ANGLE_LEFT_ARM = [
    0,   # Joint 1
    0,   # Joint 2
    0,   # Joint 3
    0,   # Joint 4
    0,   # Joint 5
    0,   # Joint 6
    1.0, # Gripper
]

# Define start position (in degrees)
START_POSITION_ANGLE_RIGHT_ARM = [
    0,   # Joint 1
    0,   # Joint 2
    0,   # Joint 3
    0,   # Joint 4
    0,   # Joint 5
    0,   # Joint 6
    1.0, # Gripper
]