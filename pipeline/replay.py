import argparse, os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.robot import ROBOT_REGISTRY
from robot.robot.base_robot_node import build_robot_node

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", type=str)
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--idx", type=int, required=True, help="config file name for data collection")
parser.add_argument("--collect", action="store_true", help="enable data collection")
parser.add_argument("--collect_idx", type=int, help="required when --collect is set")
args_cli = parser.parse_args()
if args_cli.collect and args_cli.collect_idx is None:
    parser.error("--collect requires --collect_idx (e.g. --collect --collect_idx 3)")

if __name__ == "__main__":
    collect_config = load_yaml(os.path.join(CONFIG_DIR, f'{args_cli.collect_cfg}.yml'))
    os.environ["INFO_LEVEL"] = collect_config.get("INFO_LEVEL") # DEBUG, INFO, ERROR
    task_name = args_cli.task_name if args_cli.task_name else collect_config.get("task_name")
    save_dir = os.path.join(collect_config.get("save_dir"), task_name)
    robot_type = collect_config["robot"]["type"]
    robot_cls = ROBOT_REGISTRY[robot_type]
    if collect_config['use_node']:
        robot_cls = build_robot_node(robot_cls)
    collect_config["task_name"] = task_name
    robot = robot_cls(config=collect_config)
    robot.set_up(teleop=False)
    robot.reset()
    robot.replay(data_path=os.path.join(save_dir, f"{args_cli.idx}.hdf5"), key_banned=["qpos"], is_collect=args_cli.collect, episode_id=args_cli.collect_idx)