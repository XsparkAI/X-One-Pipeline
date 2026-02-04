from .base_robot import *
from .dual_x_arm import Dual_X_Arm
from .dual_test_robot import Dual_Test_Robot

ROBOT_REGISTRY = {
    "dual_x_arm": Dual_X_Arm,
    "dual_test_robot": Dual_Test_Robot,
}
