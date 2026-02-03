import argparse, os
import time
from robot.robot import ROBOT_REGISTRY
from robot.utils.base.data_handler import is_enter_pressed, debug_print
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.load_file import load_yaml
from robot.robot.base_robot_node import build_robot_node

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", type=str)
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
args_cli = parser.parse_args()

if __name__ == "__main__":
    
    collect_config = load_yaml(os.path.join(CONFIG_DIR, f'{args_cli.collect_cfg}.yml'))
    task_name = args_cli.task_name if args_cli.task_name else collect_config.get("task_name")
    collect_config["task_name"] = task_name
    
    os.environ["INFO_LEVEL"] = collect_config.get("INFO_LEVEL") # DEBUG, INFO, ERROR

    robot_type = collect_config["robot"]["type"]
    robot_cls = ROBOT_REGISTRY[robot_type]
    if collect_config['use_node']:
        robot_cls = build_robot_node(robot_cls)
    robot = robot_cls(config=collect_config)
    robot.set_up(teleop=True)

    start_episode = collect_config.get("start_episode")
    num_episode = collect_config.get("num_episode")

    for episode_id in range(start_episode, start_episode + num_episode):
        robot.reset()
        debug_print("main", "Press Enter to start...", "INFO")
        while not robot.is_start() or not is_enter_pressed():
            time.sleep(1 / robot.config["save_freq"])
        debug_print("main", "Press Enter to finish...", "INFO")

        avg_collect_time, collect_num = 0.0, 0
        while True:
            last_time = time.monotonic()

            data = robot.get()
            robot.collect(data)
            
            if is_enter_pressed():
                robot.finish(episode_id)
                break
                
            collect_num += 1

            while True:
                current_time = time.monotonic()
                if current_time - last_time > 1 / robot.config["save_freq"]:
                    avg_collect_time += current_time - last_time
                    break
                else:
                    time.sleep(0.001) # hard code

        extra_info = {}
        avg_collect_time = avg_collect_time / collect_num
        extra_info["avg_time_interval"] = avg_collect_time
        robot.collector.add_extra_config_info(extra_info)