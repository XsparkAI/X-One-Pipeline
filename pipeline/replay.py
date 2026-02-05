import argparse, os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.robot import get_robot
from robot.robot.base_robot_node import build_robot_node

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", type=str)
parser.add_argument("--robot_cfg", type=str, required=True, help="config file name for robot setup")
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--idx", type=int, required=True, help="config file name for data collection")
parser.add_argument("--collect", action="store_true", help="enable data collection")
parser.add_argument("--collect_idx", type=int, help="required when --collect is set")
args_cli = parser.parse_args()
if args_cli.collect and args_cli.collect_idx is None:
    parser.error("--collect requires --collect_idx (e.g. --collect --collect_idx 3)")

if __name__ == "__main__":
    collect_cfg = load_yaml(os.path.join(CONFIG_DIR, "collect",f'{args_cli.collect_cfg}.yml'))
    os.environ["INFO_LEVEL"] = collect_cfg.get("INFO_LEVEL", "INFO") # DEBUG, INFO, ERROR
    robot_cfg = load_yaml(os.path.join(CONFIG_DIR, "robot",f'{args_cli.robot_cfg}.yml'))

    task_name = args_cli.task_name if args_cli.task_name else collect_cfg.get("task_name")
    save_dir = os.path.join(collect_cfg.get("save_dir"), robot_cfg["type"],task_name)

    collect_cfg["task_name"] = task_name

    robot = get_robot(robot_cfg)
    robot.collect_init(collect_cfg)

    robot.set_up(teleop=False)
    robot.reset()
    
    robot.replay(data_path=os.path.join(save_dir, f"{args_cli.idx}.hdf5"), key_banned=["qpos"], is_collect=args_cli.collect, episode_id=args_cli.collect_idx)