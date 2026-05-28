import argparse
import inspect
import os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.robot import get_robot

parser = argparse.ArgumentParser()
parser.add_argument("--base_cfg", type=str, required=True, help="config file name for robot setup")
args_cli = parser.parse_args()


def _apply_reset_overrides(base_cfg):
    reset_cfg = base_cfg.setdefault("reset", {})

    if base_cfg.get("collect") and base_cfg["collect"].get("task_name") is None:
        base_cfg["collect"]["task_name"] = "_reset"

    base_cfg.setdefault("robot", {})
    base_cfg["robot"]["use_node"] = reset_cfg.get("use_node", False)

    return reset_cfg


def _build_setup_kwargs(robot, reset_cfg):
    kwargs = {"teleop": False}
    if "setup_cameras" in reset_cfg:
        kwargs["setup_cameras"] = reset_cfg["setup_cameras"]

    sig = inspect.signature(robot.set_up)
    return {k: v for k, v in kwargs.items() if k in sig.parameters}


def _maybe_ros_shutdown(reset_cfg, robot_type):
    ros_shutdown = reset_cfg.get("ros_shutdown")
    if ros_shutdown is None:
        ros_shutdown = robot_type == "r1pro"
    if not ros_shutdown:
        return

    try:
        from robot.utils.ros.ros2_hub import Ros2Hub

        Ros2Hub.shutdown_if_initialized()
    except Exception:
        pass


if __name__ == "__main__":
    base_cfg = load_yaml(os.path.join(CONFIG_DIR, f"{args_cli.base_cfg}.yml"))
    os.environ["INFO_LEVEL"] = base_cfg.get("INFO_LEVEL", "INFO") # DEBUG, INFO, ERROR

    reset_cfg = _apply_reset_overrides(base_cfg)
    robot = get_robot(base_cfg)
    try:
        robot.set_up(**_build_setup_kwargs(robot, reset_cfg))
        robot.reset()
    finally:
        _maybe_ros_shutdown(reset_cfg, base_cfg["robot"]["type"])
