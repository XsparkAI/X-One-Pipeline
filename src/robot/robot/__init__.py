from .base_robot import *
from .base_robot_node import build_robot_node
from robot.utils.base.data_transform_pipeline import X_one_format_pipeline, X_spark_format_pipeline

# Lazy registry: only import the selected robot class to avoid optional deps
# (e.g. agx_pinocchio for Piper) when running R1 Pro only.
ROBOT_REGISTRY = {
    "dual_test_robot": ("robot.robot.dual_test_robot", "Dual_Test_Robot"),
    "x-one-piper-master": ("robot.robot.dual_piper_master", "Dual_Piper_Master"),
    "x-one-piperX-master": ("robot.robot.dual_piperX_master", "Dual_PiperX_Master"),
    "x-one-piper-orbbec": ("robot.robot.dual_piper_orbbec", "Dual_Piper_Orbbec"),
    "x-one-piperX-orbbec": ("robot.robot.dual_piperX_orbbec", "Dual_PiperX_Orbbec"),
    "x-one-x5-master": ("robot.robot.dual_ArxX5_master", "Dual_ArxX5_Master"),
    "x-one-x5-orbbec": ("robot.robot.dual_ArxX5_orbbec", "Dual_ArxX5_Orbbec"),
}

DATA_TRANSFORM_PIPELINE_REGISTRY = {
    "x-old": X_one_format_pipeline,
    "x-one": X_spark_format_pipeline,
}


def _load_robot_class(robot_type):
    if robot_type not in ROBOT_REGISTRY:
        available = list(ROBOT_REGISTRY.keys())
        raise ValueError(
            f"未找到机器人类型 '{robot_type}'。当前已注册的可选类型有: {available}"
        )

    module_path, class_name = ROBOT_REGISTRY[robot_type]
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_robot(base_cfg):
    robot_type = base_cfg["robot"].get("type")

    if not robot_type:
        raise KeyError("配置文件中缺少 ['robot']['type'] 字段，请检查您的 config.yml")

    robot_cls = _load_robot_class(robot_type)

    if base_cfg["robot"].get("use_node", False):
        robot_cls = build_robot_node(robot_cls)

    transform_pipeline = base_cfg["robot"].get("data_transform_pipeline", False)
    if transform_pipeline:
        try:
            pipeline_function = DATA_TRANSFORM_PIPELINE_REGISTRY[transform_pipeline]
            robot_cls.collector._add_data_transform_pipeline(pipeline_function)
        except ImportError as e:
            raise ImportError(
                "Failed to import data_transform_pipeline module. Please ensure it exists."
            ) from e

    return robot_cls(base_config=base_cfg)