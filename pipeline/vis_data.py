import argparse, os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.data_handler import vis_video

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", type=str)
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--robot_cfg", type=str, required=True, help="config file name for robot setup")
parser.add_argument("--idx", type=int, required=True, help="config file name for data collection")
parser.add_argument("--save_path", type=str, help="path to save the video")
parser.add_argument("--picture_key", type=str, default="cam_head", help="the key of the picture to be shown")
args_cli = parser.parse_args()

if __name__ == "__main__":
    collect_cfg = load_yaml(os.path.join(CONFIG_DIR, "collect", f'{args_cli.collect_cfg}.yml'))
    robot_cfg = load_yaml(os.path.join(CONFIG_DIR, "robot", f'{args_cli.robot_cfg}.yml'))
    task_name = args_cli.task_name if args_cli.task_name else collect_cfg.get("task_name")

    robot_name = robot_cfg["type"]
    if robot_cfg.get("use_node", False):
        robot_name = robot_name

    save_dir = os.path.join(collect_cfg.get("save_dir"), robot_name, task_name)
    data_path = os.path.join(save_dir, f"{args_cli.idx}.hdf5")
    print("load data from:", data_path)
    vis_video(data_path, args_cli.picture_key, args_cli.save_path)