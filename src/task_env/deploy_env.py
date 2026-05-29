import os
import random
from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import ROOT_DIR, POLLING_INTERVAL
from robot.utils.base.data_handler import debug_print
from .base_env import BaseEnv
from datetime import datetime
from client_server.model_client import ModelClient
import time

class DeployEnv(BaseEnv):
    def __init__(self, base_cfg, deploy_cfg, task_name):
        super().__init__(base_cfg=base_cfg)
        self.success_num, self.episode_num = 0, 0
        self.deploy_cfg = deploy_cfg

        self.save_dir = os.path.join(deploy_cfg.get("result_dir"), task_name, deploy_cfg.get("policy_name"))
        
        task_info_path = os.path.join(ROOT_DIR, f"task_info/{task_name}.json")
        if not os.path.exists(task_info_path):
            debug_print("DEPLOY", f"Task info file not found: {task_info_path}", "ERROR")
            raise FileNotFoundError(f"Missing task configuration: {task_info_path}")
            
        self.task_info = load_yaml(task_info_path)
        if 'step_lim' not in self.task_info:
            debug_print("DEPLOY", f"'step_lim' missing in {task_info_path}, using default 500", "WARNING")
            self.episode_step_limit = 500
        else:
            self.episode_step_limit = self.task_info['step_lim']
            
        os.makedirs(self.save_dir, exist_ok=True)
        self.model_client = ModelClient(port=deploy_cfg['port'])
        self.robot.set_up(teleop=False)

        if self.deploy_cfg.get("deploy", False):
            self.force_reach_mode = True if deploy_cfg["deploy"].get("force_reach", False) else False
            debug_print("DEPLOY", "deloy policy force_reach_mode=True.", "INFO")
        else:
            self.force_reach_mode = False
            debug_print("DEPLOY", "deloy policy force_reach_mode=False.", "INFO")

    def get_obs(self):
        return self.robot.get_obs()

    def eval_one_episode(self):
        policy_name = self.deploy_cfg['policy_name']
        try:
            eval_module = __import__(f'policy_lab.{policy_name}.deploy', fromlist=['eval_one_episode'])
        except ImportError as e:
            debug_print("DEPLOY", f"Failed to import policy module: policy_lab.{policy_name}.deploy. Error: {e}", "ERROR")
            raise e
            
        if not hasattr(eval_module, 'eval_one_episode'):
            debug_print("DEPLOY", f"Module 'policy_lab.{policy_name}.deploy' does not have 'eval_one_episode' function", "ERROR")
            raise AttributeError(f"Missing eval_one_episode in policy module")
            
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
        if self.episode_step > self.episode_step_limit:
            return
        
        self.episode_step += 1

        super().take_action(action)

        self.last_time = time.monotonic()
        if self.force_reach_mode:
            while self.robot.is_move():
                time.sleep(POLLING_INTERVAL)
        else:
            # Safe freq check
            try:
                raw_freq = self.base_cfg.get('collect', {}).get('save_freq', 10)
                if raw_freq <= 0:
                    raw_freq = 10
                    debug_print("DEPLOY", "Invalid save_freq <= 0, defaulting to 10Hz", "WARNING")
                save_period = 1 / raw_freq
            except (KeyError, ZeroDivisionError):
                save_period = 1 / 10
                
            while True:
                now = time.monotonic()
                if now - self.last_time > save_period:
                    break
                else:
                    time.sleep(POLLING_INTERVAL)
            self.last_time = now

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