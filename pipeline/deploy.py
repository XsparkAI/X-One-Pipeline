import argparse, os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR, ROOT_DIR
from task_env.deploy_env import DeployEnv

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", required=True, type=str)
parser.add_argument("--policy_name", type=str, required=True, help="policy_lab module name for deployment")
parser.add_argument("--robot_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--port", type=int, required=True, help="number of evaluation episodes")
parser.add_argument("--eval_episode", type=int, default=100, help="number of evaluation episodes")
parser.add_argument("--collect_cfg", type=str, required=False, help="config file name for data collection")
args_cli = parser.parse_args()

if __name__ == "__main__":
    robot_cfg = load_yaml(os.path.join(CONFIG_DIR, "robot/",f'{args_cli.robot_cfg}.yml'))
    
    deploy_cfg = load_yaml(os.path.join(ROOT_DIR, f"policy_lab/{args_cli.policy_name}/deploy.yml"))
    deploy_cfg['port'] = args_cli.port
    deploy_cfg["policy_name"] = args_cli.policy_name
    
    task_name = args_cli.task_name

    collect_cfg_path = args_cli.collect_cfg if hasattr(args_cli, "collect_cfg") else None
    if collect_cfg_path is not None:
        collect_cfg_path = os.path.join(CONFIG_DIR, "collect/",f'{collect_cfg_path}.yml')
        collect_cfg = load_yaml(collect_cfg_path)
        collect_cfg["task_name"] = task_name
    else:
        collect_cfg=None

    deploy_env = DeployEnv(robot_cfg=robot_cfg,deploy_cfg=deploy_cfg, task_name=task_name, collect_cfg=collect_cfg)

    # Load policy_lab
    for idx in range(args_cli.eval_episode):
        print(f"\033[94m🚀 Running Episode {idx}\033[0m")
        deploy_env.set_episode_idx(idx)
        deploy_env.reset() # reset model, robot, and environment
        deploy_env.eval_one_episode()
        deploy_env.finish_episode()
