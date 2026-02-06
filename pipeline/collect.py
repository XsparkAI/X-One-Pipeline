import argparse, os
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.load_file import load_yaml
from task_env.collect_env import CollectEnv

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", type=str, required=True)
parser.add_argument("--base_cfg", type=str, required=True)
parser.add_argument("--st_idx", type=int, default=0, help="start episode index")
args_cli = parser.parse_args()

if __name__ == "__main__":
    # get cfg
    base_cfg = load_yaml(os.path.join(CONFIG_DIR, f'{args_cli.base_cfg}.yml'))
    task_name = args_cli.task_name
    base_cfg["collect"]["task_name"] = task_name

    # setup INFO level
    os.environ["INFO_LEVEL"] = base_cfg.get("INFO_LEVEL", "INFO") # DEBUG, INFO, ERROR

    TASK_ENV = CollectEnv(base_cfg)
    TASK_ENV.set_up(teleop=True)
    
    START = args_cli.st_idx
    END = base_cfg["collect"].get("num_episode")

    for episode_id in range(START, END):
        print(
            f"\n\033[96m══════════════════════════════════════════════\033[0m\n"
            f"\033[94m▶ Episode\033[0m  \033[97m{episode_id:>3}/{END-1:<3}\033[0m   "
            f"\033[90m(id={episode_id}, range={START}-{END-1}), start from 0\033[0m\n"
            f"\033[92m[START]\033[0m set_episode_idx -> {episode_id}\n"
        )

        TASK_ENV.set_episode_idx(episode_id)
        TASK_ENV.collect_one_episode()

        print(
            f"\033[92m[DONE ]\033[0m episode_id={episode_id}\n"
            f"\033[96m══════════════════════════════════════════════\033[0m"
        )