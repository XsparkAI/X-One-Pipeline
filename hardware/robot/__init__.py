from .base_robot import *
from .dual_x_arm import Dual_X_Arm
from .dual_x_arm_node import Dual_X_Arm_Node

ROBOT_REGISTRY = {
    "dual_x_arm": Dual_X_Arm,
    "dual_x_arm_node": Dual_X_Arm_Node
}
