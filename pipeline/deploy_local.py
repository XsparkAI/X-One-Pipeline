import argparse, os
import importlib
import ast

from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR, ROOT_DIR
from task_env.deploy_local_env import DeployLocalEnv

def parse_args_and_config():
    """Parse CLI args and YAML config, merge overrides"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_name", type=str, required=True, help="Name of the task (e.g., 'pick_and_place')")
    parser.add_argument("--policy_name", type=str, required=True, help="Name of the policy (e.g., 'my_policy')")
    parser.add_argument("--base_cfg", type=str, default="x-one", help="Base config name (without .yml, default: 'x-one')")
    parser.add_argument("--config_path", type=str, required=True, help="Path to config model YAML")
    parser.add_argument("--eval_episode_num", type=int, default=100, help="Number of evaluation episodes")
    parser.add_argument("--overrides", nargs=argparse.REMAINDER, help="Override config values")
    args = parser.parse_args()

    cfg = load_yaml(args.config_path)
    cfg["task_name"] = args.task_name
    cfg["policy_name"] = args.policy_name
    cfg["base_cfg"] = args.base_cfg
    cfg["eval_episode_num"] = args.eval_episode_num

    # Parse overrides: --key value pairs
    def _parse_val(s: str):
        # safer than eval; supports numbers/bool/None/list/dict when properly quoted
        try:
            return ast.literal_eval(s)
        except Exception:
            return s

    if args.overrides:
        tokens = args.overrides

        # Case A: key=value key=value ...
        if all(("=" in t and not t.startswith("-")) for t in tokens):
            for t in tokens:
                k, v = t.split("=", 1)
                cfg[k] = _parse_val(v)
        else:
            # Case B: --key value --key value ...
            if len(tokens) % 2 != 0:
                raise ValueError(f"--overrides expects key value pairs, got: {tokens}")

            it = iter(tokens)
            for key in it:
                val = next(it)
                cfg[key.lstrip("-")] = _parse_val(val)
    return cfg

if __name__ == "__main__":
    cfg = parse_args_and_config()
    base_cfg = load_yaml(os.path.join(CONFIG_DIR, f'{cfg["base_cfg"]}.yml'))
    deploy_cfg = cfg  # In this local deployment, we can use the same config for both base and deploy

    # Load policy_lab
    deploy_env = DeployLocalEnv(base_cfg=base_cfg, deploy_cfg=cfg, task_name=cfg["task_name"])

    for idx in range(cfg["eval_episode_num"]):
        print(f"\033[94m🚀 Running Episode {idx}\033[0m")
        deploy_env.set_episode_idx(idx)
        deploy_env.reset() # reset model, robot, and environment
        deploy_env.eval_one_episode()
        deploy_env.finish_episode()
