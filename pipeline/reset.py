import argparse, os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.robot import ROBOT_REGISTRY

parser = argparse.ArgumentParser()
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
args_cli = parser.parse_args()
if args_cli.collect and args_cli.collect_idx is None:
    parser.error("--collect requires --collect_idx (e.g. --collect --collect_idx 3)")

if __name__ == "__main__":
    collect_config = load_yaml(os.path.join(CONFIG_DIR, f'{args_cli.collect_cfg}.yml'))
    os.environ["INFO_LEVEL"] = collect_config.get("INFO_LEVEL") # DEBUG, INFO, ERROR
    robot_type = collect_config["robot"]["type"]
    robot = ROBOT_REGISTRY[robot_type](config=collect_config)
    robot.set_up(teleop=False)
    robot.reset()