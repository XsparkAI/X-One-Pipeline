
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
        debug_print("COLLECT", "Waiting for robot ready and Enter key...", "INFO")
        
        # Check config
        if 'collect' not in self.base_cfg or 'save_freq' not in self.base_cfg['collect']:
            debug_print("COLLECT", "Missing 'save_freq' in config. Using default 30Hz.", "WARNING")
            save_freq = 30
        else:
            save_freq = self.base_cfg['collect']["save_freq"]
            if save_freq <= 0:
                debug_print("COLLECT", f"Invalid save_freq: {save_freq}. Resetting to 30.", "ERROR")
                save_freq = 30

        while not self.robot.is_start():
            debug_print("COLLECT", "Robot not started yet, verify hardware connection.", "WARNING")
            time.sleep(1)
        
        debug_print("COLLECT", "Robot READY. Press Enter to start recording...", "INFO")
        while not is_enter_pressed():
            time.sleep(1 / 20)
        
        debug_print("COLLECT", "Recording... Press Enter again to finish.", "INFO")

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
                if current_time - last_time > 1 / save_freq:
                    avg_collect_time += current_time - last_time
                    break
                else:
                    time.sleep(0.001) # hard code

        extra_info = {}
        avg_collect_time = avg_collect_time / collect_num
        extra_info["avg_time_interval"] = avg_collect_time
        self.robot.collector.add_extra_cfg_info(extra_info)