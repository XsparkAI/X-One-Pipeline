from .base_robot import *
from .base_robot_node import build_robot_node

# from .dual_x_arm import Dual_X_Arm
# from .dual_test_robot import Dual_Test_Robot
# from .dual_x_arm_master import Dual_X_Arm_master
# from .dual_piperX_master import Dual_PiperX_Master
# from .dual_piper_master import Dual_Piper_Master
# from .dual_piper_orbbec import Dual_Piper_Orbbec
# from .dual_piperX_orbbec import Dual_PiperX_Orbbec
from .dual_ArxX5_master import Dual_ArxX5_Master
from .dual_ArxX5_orbbec import Dual_ArxX5_Orbbec

from robot.utils.base.data_transform_pipeline import X_one_format_pipeline, X_spark_format_pipeline
ROBOT_REGISTRY = {
    # "x-one": Dual_X_Arm,
    # "dual_test_robot": Dual_Test_Robot,
    # "x-one-master": Dual_X_Arm_master,
    # "x-one-piper-master": Dual_Piper_Master,
    # "x-one-piperX-master": Dual_PiperX_Master,
    # "x-one-piper-orbbec": Dual_Piper_Orbbec,
    # "x-one-piperX-orbbec": Dual_PiperX_Orbbec,
    "x-one-x5-master": Dual_ArxX5_Master,
    "x-one-x5-orbbec": Dual_ArxX5_Orbbec,
}

DATA_TRANSFORM_PIPELINE_REGISTRY = {
    "x-old": X_one_format_pipeline,
    "x-one": X_spark_format_pipeline,
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
    
    transform_pipeline = base_cfg["robot"].get('data_transform_pipeline', False)
    if transform_pipeline:
        try:
            pipeline_function = DATA_TRANSFORM_PIPELINE_REGISTRY[transform_pipeline]
            robot_cls.collector._add_data_transform_pipeline(pipeline_function)
        except ImportError as e:
            raise ImportError("Failed to import data_transform_pipeline module. Please ensure it exists.") from e
    
    return robot_cls(base_config=base_cfg)