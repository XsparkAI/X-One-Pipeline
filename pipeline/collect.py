import argparse, os
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.load_file import load_yaml
from task_env.collect_env import CollectEnv

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", type=str)
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
args_cli = parser.parse_args()

if __name__ == "__main__":
    collect_cfg = load_yaml(os.path.join(CONFIG_DIR, f'{args_cli.collect_cfg}.yml'))
    task_name = args_cli.task_name if args_cli.task_name else collect_cfg.get("task_name")
    collect_cfg["task_name"] = task_name
    
    os.environ["INFO_LEVEL"] = collect_cfg.get("INFO_LEVEL") # DEBUG, INFO, ERROR

    TASK_ENV = CollectEnv(env_cfg=collect_cfg)

    start_episode = collect_cfg.get("start_episode")
    num_episode = collect_cfg.get("num_episode")
    TASK_ENV.set_up(teleop=True)
    for episode_id in range(start_episode, start_episode + num_episode):
        TASK_ENV.set_episode_idx(episode_id)
        TASK_ENV.collect_one_episode()