import argparse, os
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.load_file import load_yaml
from task_env.collect_env import CollectEnv

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", type=str)
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--st_idx", type=int, help="start episode index")
args_cli = parser.parse_args()

if __name__ == "__main__":
    collect_cfg = load_yaml(os.path.join(CONFIG_DIR, f'{args_cli.collect_cfg}.yml'))
    task_name = args_cli.task_name if args_cli.task_name else collect_cfg.get("task_name")
    collect_cfg["task_name"] = task_name
    
    os.environ["INFO_LEVEL"] = collect_cfg.get("INFO_LEVEL") # DEBUG, INFO, ERROR

    TASK_ENV = CollectEnv(env_cfg=collect_cfg)
    TASK_ENV.set_up(teleop=True)
    
    START = collect_cfg.get("st_idx", 0)
    END = collect_cfg.get("num_episode")

    for i, episode_id in enumerate(range(START, END), start=1):
        print(
            f"\n\033[96m══════════════════════════════════════════════\033[0m\n"
            f"\033[94m▶ Episode\033[0m  \033[97m{i:>3}/{END:<3}\033[0m   "
            f"\033[90m(id={episode_id}, range={START}-{END})\033[0m\n"
            f"\033[92m[START]\033[0m set_episode_idx -> {episode_id}\n"
        )

        TASK_ENV.set_episode_idx(episode_id)
        TASK_ENV.collect_one_episode()

        print(
            f"\033[92m[DONE ]\033[0m episode_id={episode_id}\n"
            f"\033[96m══════════════════════════════════════════════\033[0m"
        )
