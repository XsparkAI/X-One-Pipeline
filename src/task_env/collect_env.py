import os
import random
from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import ROOT_DIR
from datetime import datetime
from robot.utils.base.data_handler import is_enter_pressed, debug_print
import time
from .base_env import BaseEnv

class CollectEnv(BaseEnv):
    def __init__(self, env_cfg):
        if env_cfg.get("collect", False):
            env_cfg["collect"] = None 

        super().__init__(env_cfg=env_cfg)
        self.success_num, self.episode_num = 0, 0
        self.env_cfg = env_cfg
        

    def collect_one_episode(self):
        self.robot.reset()
        debug_print("main", "Press Enter to start...", "INFO")
        while not self.robot.is_start() or not is_enter_pressed():
            time.sleep(1 / self.env_cfg["save_freq"])
        debug_print("main", "Press Enter to finish...", "INFO")

        avg_collect_time, collect_num = 0.0, 0
        while True:
            last_time = time.monotonic()

            data = self.robot.get_obs()
            self.robot.collect(data)
            
            if is_enter_pressed():
                self.robot.finish(self.episode_idx)
                break
                
            collect_num += 1

            while True:
                current_time = time.monotonic()
                if current_time - last_time > 1 / self.env_cfg["save_freq"]:
                    avg_collect_time += current_time - last_time
                    break
                else:
                    time.sleep(0.001) # hard code

        extra_info = {}
        avg_collect_time = avg_collect_time / collect_num
        extra_info["avg_time_interval"] = avg_collect_time
        self.robot.collector.add_extra_cfg_info(extra_info)
    
    def eval_one_episode(self):
        policy_name = self.deploy_cfg['policy_name']
        eval_module = __import__(f'policy_lab.{policy_name}.deploy', fromlist=['eval_one_episode'])
        eval_module.eval_one_episode(TASK_ENV=self, model=self.model)
    
    def reset(self):
        self.model.reset()
        self.episode_step = 0