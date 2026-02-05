from .base_robot import *
from .base_robot_node import build_robot_node

from .dual_x_arm import Dual_X_Arm
from .dual_test_robot import Dual_Test_Robot
from .dual_x_arm_master import Dual_X_Arm_master

ROBOT_REGISTRY = {
    "dual_x_arm": Dual_X_Arm,
    "dual_test_robot": Dual_Test_Robot,
    "dual_x_arm_master": Dual_X_Arm_master,
}

def get_robot(robot_cfg):
    robot_type = robot_cfg["type"]
    robot_cls = ROBOT_REGISTRY[robot_type]
    if robot_cfg.get('use_node', False):
        robot_cls = build_robot_node(robot_cls)
    robot = robot_cls(robot_config=robot_cfg)
    return robot