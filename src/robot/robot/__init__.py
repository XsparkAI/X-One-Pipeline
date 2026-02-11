from .base_robot import *
from .base_robot_node import build_robot_node

from .dual_x_arm import Dual_X_Arm
from .dual_test_robot import Dual_Test_Robot
from .dual_x_arm_master import Dual_X_Arm_master
# from .dual_x_arm_mobile import Dual_X_Arm_Mobile
from .dual_x_arm_wuji_hand import Dual_X_Arm_hand

ROBOT_REGISTRY = {
    "x-one": Dual_X_Arm,
    "dual_test_robot": Dual_Test_Robot,
    "dual_x_arm_master": Dual_X_Arm_master,
    # "x-one-mobile": Dual_X_Arm_Mobile,
    "dual_x_arm_hand": Dual_X_Arm_hand,
}

def get_robot(base_cfg):
    robot_type = base_cfg["robot"].get("type")
    
    # 1. 检查配置是否存在
    if not robot_type:
        raise KeyError("配置文件中缺少 ['robot']['type'] 字段，请检查您的 config.yml")
        
    # 2. 检查注册表
    if robot_type not in ROBOT_REGISTRY:
        available = list(ROBOT_REGISTRY.keys())
        raise ValueError(f"未找到机器人类型 '{robot_type}'。当前已注册的可选类型有: {available}")
        
    robot_cls = ROBOT_REGISTRY[robot_type]
    
    # 3. 实例化前置处理
    if base_cfg["robot"].get('use_node', False):
        robot_cls = build_robot_node(robot_cls)
        
    return robot_cls(base_config=base_cfg)