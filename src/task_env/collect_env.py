
from robot.utils.base.data_handler import is_enter_pressed, debug_print
import time
from .base_env import BaseEnv

class CollectEnv(BaseEnv):
    def __init__(self, base_cfg):
        super().__init__(base_cfg=base_cfg)
        self.success_num, self.episode_num = 0, 0
        self.base_cfg = base_cfg
        
    def collect_one_episode(self):
        self.robot.reset()
        debug_print("main", "Press Enter to start...", "INFO")
        while not self.robot.is_start() or not is_enter_pressed():
            time.sleep(1 / 20)
        
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
                if current_time - last_time > 1 / self.base_cfg['collect']["save_freq"]:
                    avg_collect_time += current_time - last_time
                    break
                else:
                    time.sleep(0.001) # hard code

        extra_info = {}
        avg_collect_time = avg_collect_time / collect_num
        extra_info["avg_time_interval"] = avg_collect_time
        self.robot.collector.add_extra_cfg_info(extra_info)