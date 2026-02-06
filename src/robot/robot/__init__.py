from .base_robot import *
from .base_robot_node import build_robot_node

from .dual_x_arm import Dual_X_Arm
from .dual_test_robot import Dual_Test_Robot
from .dual_x_arm_master import Dual_X_Arm_master
from .dual_x_arm_wuji_hand import Dual_X_Arm_hand
ROBOT_REGISTRY = {
    "x-one": Dual_X_Arm,
    "dual_test_robot": Dual_Test_Robot,
    "dual_x_arm_master": Dual_X_Arm_master,
    "dual_x_arm_hand": Dual_X_Arm_hand,
}

def get_robot(base_cfg):
    robot_type = base_cfg["robot"]["type"]
    robot_cls = ROBOT_REGISTRY[robot_type]
    if base_cfg["robot"].get('use_node', False):
        robot_cls = build_robot_node(robot_cls)
    robot = robot_cls(base_config=base_cfg)
    return robot