from .base_robot import *
from .dual_x_arm import Dual_X_Arm

ROBOT_REGISTRY = {
    "dual_x_arm": Dual_X_Arm
}
