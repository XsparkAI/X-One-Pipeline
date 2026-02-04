import argparse, os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.robot import ROBOT_REGISTRY

parser = argparse.ArgumentParser()
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
args_cli = parser.parse_args()

if __name__ == "__main__":
    collect_cfg = load_yaml(os.path.join(CONFIG_DIR, f'{args_cli.collect_cfg}.yml'))
    os.environ["INFO_LEVEL"] = collect_cfg.get("INFO_LEVEL") # DEBUG, INFO, ERROR
    robot_type = collect_cfg["robot"]["type"]
    robot = ROBOT_REGISTRY[robot_type](config=collect_cfg)
    robot.set_up(teleop=False)
    robot.reset()