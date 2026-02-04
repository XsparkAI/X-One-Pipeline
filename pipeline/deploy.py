import argparse, os

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR, ROOT_DIR
from task_env.deploy_env import DeployEnv

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", type=str)
parser.add_argument("--policy_name", type=str, required=True, help="policy_lab module name for deployment")
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--port", type=int, required=True, help="number of evaluation episodes")
parser.add_argument("--eval_episode", type=int, default=100, help="number of evaluation episodes")
args_cli = parser.parse_args()

if __name__ == "__main__":
    collect_cfg = load_yaml(os.path.join(CONFIG_DIR, f'{args_cli.collect_cfg}.yml'))
    task_name = args_cli.task_name if args_cli.task_name else collect_cfg.get("task_name")
    policy_name = args_cli.policy_name
    collect_cfg["task_name"], collect_cfg['policy_name'] = task_name, policy_name
    
    deploy_cfg = load_yaml(os.path.join(ROOT_DIR, f'policy_lab/{policy_name}/deploy.yml'))
    deploy_cfg["task_name"], deploy_cfg['policy_name'], deploy_cfg['port'] = task_name, policy_name, args_cli.port
    
    deploy_env = DeployEnv(deploy_cfg=deploy_cfg, env_cfg=collect_cfg)

    # Load policy_lab
    for idx in range(args_cli.eval_episode):
        print(f"\033[94m🚀 Running Episode {idx}\033[0m")
        deploy_env.set_episode_idx(idx)
        deploy_env.reset() # reset model, robot, and environment
        deploy_env.eval_one_episode()
        deploy_env.finish_episode()
