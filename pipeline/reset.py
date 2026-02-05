import argparse, os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.robot import get_robot

parser = argparse.ArgumentParser()
parser.add_argument("--robot_cfg", type=str, required=True, help="config file name for robot setup")
args_cli = parser.parse_args()

if __name__ == "__main__":
    robot_cfg = load_yaml(os.path.join(CONFIG_DIR, "robot",f'{args_cli.robot_cfg}.yml'))
    os.environ["INFO_LEVEL"] = robot_cfg.get("INFO_LEVEL", "INFO") # DEBUG, INFO, ERROR
    robot = get_robot(robot_cfg)
    
    robot.set_up(teleop=False)
    robot.reset()