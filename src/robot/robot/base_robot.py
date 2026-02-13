from typing import Dict, Any
import time
from robot.data.collect_any import CollectAny
from robot.utils.base.data_handler import debug_print, hdf5_groups_to_dict, dict_to_list
import os
import glob
import random
import numpy as np

# add your controller/sensor type here
ALLOW_TYPES = ["arm", "mobile", "image", "tactile", "teleop"]
KEY_BANNED = ["timestamp", "qpos"]
    
class Robot:
    def __init__(self, base_config) -> None:
        if "robot" not in base_config:
            debug_print("ROBOT", "Missing 'robot' section in config!", "ERROR")
            raise KeyError("Config missing 'robot' section")
            
        self.robot_config = base_config["robot"]
        self.name = self.robot_config.get("type", "unknown_robot")
        
        self.controllers = {}
        self.sensors = {}

        if "collect" not in base_config:
            debug_print(self.name, "Missing 'collect' section in config, collector will be disabled.", "WARNING")
            self.collect_cfg = {}
            self.collector = None
        else:
            collect_cfg = base_config["collect"]
            collect_cfg["floder_name"] = collect_cfg.get("type", "default")
            self.collect_cfg = collect_cfg
            debug_print(self.name, f"set collect_cfg: \n {collect_cfg}", "INFO")
            self.collector = CollectAny(collect_cfg)
        
        self.last_controller_data = None
        self.move_tolerance = self.robot_config.get("move_tolerance", 0.001)
        self.bias = self.robot_config.get("bias", None)

    def set_up(self):
        for controller_type in self.controllers.keys():
            if controller_type not in ALLOW_TYPES:
                debug_print(self.name, f"It's recommanded to set your controller type into our format.\nYOUR STPE:{controller_type}\n\
                            ALLOW_TYPES:{ALLOW_TYPES}", "WARNING")
        
        for sensor_type in self.sensors.keys():
            if sensor_type not in ALLOW_TYPES:
                debug_print(self.name, f"It's recommanded to set your sensor type into our format.\nYOUR STPE:{sensor_type}\n\
                            ALLOW_TYPES:{ALLOW_TYPES}", "WARNING")

    def set_collect_type(self,INFO_NAMES: Dict[str, Any]):
        for key,value in INFO_NAMES.items():
            if key in self.controllers:
                for controller in self.controllers[key].values():
                    controller.set_collect_info(value)
            if key in self.sensors:
                for sensor in self.sensors[key].values():
                    sensor.set_collect_info(value)
    
    def get_obs(self):
        controller_data, sensor_data = {}, {}

        if self.controllers is not None:
            for type_name, controller_type in self.controllers.items():
                for controller_name, controller in controller_type.items():
                    controller_data[controller_name] = controller.get()

        if self.sensors is not None:
            for type_name, sensor_type in self.sensors.items(): 
                for sensor_name, sensor in sensor_type.items():
                    sensor_data[sensor_name] = sensor.get()

        return [controller_data, sensor_data]
    
    def collect(self, data):
        if self.collector is None:
            raise ValueError("Should setup collector by running collect_init(collect_dfg) first!")
        self.collector.collect(data[0], data[1])
    
    def finish(self, episode_id=None):
        if self.collector is None:
            raise ValueError("Should setup collector by running collect_init(collect_dfg) first!")
        
        extra_info = {}
        for controller_type in self.controllers.keys():
            extra_info[controller_type] = []
            for key in self.controllers[controller_type].keys():
                extra_info[controller_type].append(key)
        
        for sensor_type in self.sensors.keys():
            extra_info[sensor_type] = []
            for key in self.sensors[sensor_type].keys():
                extra_info[sensor_type].append(key)

        self.collector.add_extra_cfg_info(extra_info, repeat=False)
        self.collector.write(episode_id)
    
    def move(self, move_data, key_banned=None):
        if move_data is None:
            return
        
        for controller_type_name, controller_type in move_data.items():
            for controller_name, controller_action in controller_type.items():
                if self.bias:
                    if controller_name in self.bias.keys():
                        for k in self.bias[controller_name].keys():
                            controller_action[k] += self.bias[controller_name][k]
                if key_banned is None:        
                    self.controllers[controller_type_name][controller_name].move(controller_action, is_delta=False)
                else:
                    controller_action = remove_duplicate_keys(controller_action, key_banned)
                    self.controllers[controller_type_name][controller_name].move(controller_action, is_delta=False)

    def is_start(self):
        debug_print(self.name, "your are using is_start(), this will return True.", "DEBUG")
        return True

    def reset(self):
        debug_print(self.name, "your are using reset(), this will return True.", "DEBUG")
        return True
    
    def is_move(self):
        controller_data = {}
        for type_name, controller_type in self.controllers.items():
            for controller_name, controller in controller_type.items():
                controller_data[controller_name] = controller.get()
        
        if self.last_controller_data is None:
            self.last_controller_data = controller_data
            return True
        else:
            for part, current_subdata in controller_data.items():
                previous_subdata = self.last_controller_data.get(part)
                if previous_subdata is None:
                    return True

                if isinstance(current_subdata, dict):
                    for key, current_value in current_subdata.items():
                        if key in KEY_BANNED:
                            continue
                        
                        previous_value = previous_subdata.get(key)
                        if previous_value is None:
                            return True 

                        current_arr = np.atleast_1d(current_value)
                        previous_arr = np.atleast_1d(previous_value)

                        if current_arr.shape != previous_arr.shape:
                            self.last_controller_data = controller_data
                            return True 

                        if np.any(np.abs(current_arr - previous_arr) > self.move_tolerance):
                            self.last_controller_data = controller_data
                            return True 
                else:
                    current_arr = np.atleast_1d(current_subdata)
                    previous_arr = np.atleast_1d(previous_subdata)

                    if current_arr.shape != previous_arr.shape:
                        self.last_controller_data = controller_data
                        print(5)
                        return True

                    if np.any(np.abs(current_arr - previous_arr) > self.move_tolerance):
                        self.last_controller_data = controller_data
                        print(6)
                        return True
            return False

    def replay(self, data_path, fps=30, key_banned=None, is_collect=False, episode_id=None):
        time_interval = 1 / fps
        episode_data = dict_to_list(hdf5_groups_to_dict(data_path))
        
        now_time = last_time = time.monotonic()
        for current_action in episode_data:
            while now_time - last_time < time_interval:
                now_time = time.monotonic()
                time.sleep(0.00001)
            if is_collect:
                data = self.get_obs()
                self.collect(data)
            
            self.play_once(current_action, key_banned)
            last_time = time.monotonic()
        if is_collect:
            self.finish(episode_id)
    
    def play_once(self, episode: Dict[str, Any], key_banned=None):
        for controller_type, controller_group in self.controllers.items():
            for controller_name, controller in controller_group.items():
                if controller_name in episode:
                    controller_action = episode[controller_name].copy()
                    
                    move_data = {
                        controller_type: {
                            controller_name: controller_action,
                        },
                    }
                    self.move(move_data, key_banned=key_banned)

def remove_duplicate_keys(source_dict, keys_to_remove):
    return {k: v for k, v in source_dict.items() if k not in keys_to_remove}

if __name__ == "__main__":
    robot = Robot()
    robot.vis_video("save/test_robot/0.hdf5", "cam_head")