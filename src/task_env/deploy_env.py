import os
import random
from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import ROOT_DIR
from .base_env import BaseEnv
from datetime import datetime
from client_server.model_client import ModelClient
import time

class DeployEnv(BaseEnv):
    def __init__(self, deploy_cfg, env_cfg):
        super().__init__(env_cfg=env_cfg)
        self.success_num, self.episode_num = 0, 0
        self.deploy_cfg, self.env_cfg = deploy_cfg, env_cfg
        self.save_dir = os.path.join(deploy_cfg.get("result_dir"), deploy_cfg.get("policy_name"), env_cfg['task_name'])
        self.task_info = load_yaml(os.path.join(ROOT_DIR, f"task_info/{env_cfg['task_name']}.json"))
        self.episode_step_limit = self.task_info['step_lim']
        os.makedirs(self.save_dir, exist_ok=True)
        self.model_client = ModelClient(port=deploy_cfg['port'])
        self.robot.set_up(teleop=False)

    def get_obs(self): # TODO: type
        return self.robot.get_obs()

    def eval_one_episode(self):
        policy_name = self.deploy_cfg['policy_name']
        eval_module = __import__(f'policy_lab.{policy_name}.deploy', fromlist=['eval_one_episode'])
        eval_module.eval_one_episode(TASK_ENV=self, model_client=self.model_client)
    
    def reset(self):
        self.robot.reset()
        self.model_client.call(func_name="reset")
        self.episode_step = 0

    def get_instruction(self):
        instruction = random.choice(self.task_info['instructions'])
        print("Get Instruction:", instruction)
        return instruction

    def take_action(self, action):
        print(f"Action Step: {self.episode_step} / {self.episode_step_limit} (step_limit)", end='\r')
        self.episode_step += 1
        super().take_action(action)
        time.sleep(1 / self.robot.config["save_freq"])

    def is_episode_end(self):
        return self.episode_step >= self.episode_step_limit
    
    def finish_episode(self):
        # Finalize and log information for the completed episode
        print(f"\nEpisode {self.episode_idx} finished. Please input episode result (1=success, 2=fail): ", end="")
        x = input().strip()

        # simple validation loop
        while x not in {"1", "2"}:
            print("Invalid input. Please enter 1 (success) or 2 (fail): ", end="")
            x = input().strip()

        is_success = (x == "1")
        if is_success:
            self.success_num += 1

        self.episode_num += 1
        success_rate = self.success_num / self.episode_num if self.episode_num > 0 else 0.0

        # colored console output
        print(
            f"\033[92mSuccess Rate: {success_rate:.2%}  "
            f"(success={self.success_num}, total={self.episode_num})\033[0m"
        )

        # write to log
        log_path = os.path.join(self.save_dir, "eval_result.txt")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = (
            f"[{ts}] episode={self.episode_idx} result={'success' if is_success else 'fail'} "
            f"success={self.success_num} total={self.episode_num} "
            f"success_rate={success_rate:.4f} ({success_rate:.2%})\n"
        )

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)