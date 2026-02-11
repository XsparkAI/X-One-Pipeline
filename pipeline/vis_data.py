import argparse, os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.data_handler import vis_video, debug_print
from robot.robot import get_robot

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", type=str, required=True)
parser.add_argument("--base_cfg", type=str, required=True)
parser.add_argument("--idx", type=int, required=True, help="config file name for data collection")
parser.add_argument("--save_path", type=str, help="path to save the video")
parser.add_argument("--picture_key", type=str, default="cam_head", help="the key of the picture to be shown")
args_cli = parser.parse_args()

if __name__ == "__main__":
    base_cfg = load_yaml(os.path.join(CONFIG_DIR, f'{args_cli.base_cfg}.yml'))
    task_name = args_cli.task_name

    robot = get_robot(base_cfg)

    save_dir = os.path.join(base_cfg["collect"].get("save_dir"), task_name, base_cfg["collect"].get("type"))
    data_path = os.path.join(save_dir, f"{args_cli.idx}.hdf5")
    debug_print("vis_data", f"load data from: {data_path}", "INFO")
    vis_video(data_path, args_cli.picture_key, args_cli.save_path)