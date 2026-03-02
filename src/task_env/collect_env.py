
from robot.utils.base.data_handler import is_enter_pressed, debug_print
import time
from .base_env import BaseEnv
from robot.utils.base.footpedal import FootPedal

class CollectEnv(BaseEnv):
    def __init__(self, base_cfg):
        super().__init__(base_cfg=base_cfg)
        self.success_num, self.episode_num = 0, 0
        self.base_cfg = base_cfg
        if "use_footpedal" in self.base_cfg["collect"]:
            self.use_footpedal = self.base_cfg["collect"]["use_footpedal"]
        else:
            self.use_footpedal = False
        
        if self.use_footpedal:
            if "footpedal_serial" in self.base_cfg["collect"]:
                footpedal_serial = self.base_cfg["collect"]["footpedal_serial"]
            else:
                footpedal_serial = "/dev/hidraw4"
            self.footpedal = FootPedal(footpedal_serial)
        else:
            self.use_footpedal = False
        
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
        if self.use_footpedal:
            debug_print("COLLECT", "Waiting for foot pedal trigger...", "INFO")
            while not self.footpedal.was_pressed():
                time.sleep(1 / 20)
        else:
            debug_print("COLLECT", "Robot READY. Press Enter to start recording...", "INFO")
            while not is_enter_pressed():
                time.sleep(1 / 20)
        
        debug_print("COLLECT", "Recording... Press Enter again to finish.", "INFO")

        avg_collect_time, collect_num = 0.0, 0
        while True:
            last_time = time.monotonic()

            data = self.robot.get_obs()
            self.robot.collect(data)
            
            if self.use_footpedal:
                if self.footpedal.was_pressed():
                    self.robot.finish(self.episode_idx)
                    break
            else:
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