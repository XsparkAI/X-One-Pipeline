from typing import Dict, Any
import time
from robot.data.collect_any import CollectAny
from robot.utils.base.data_handler import debug_print, hdf5_groups_to_dict, dict_to_list
import os
import glob
import random
import numpy as np

# add your controller/sensor type here
ALLOW_TYPES = ["arm", "mobile","image", "tactile", "teleop"]
KEY_BANNED = ["timestamp", "qpos"]
class ReplaySampler:
    def __init__(self, replay_paths):
        self.replay_paths = list(replay_paths)   # 原始全集
        self._pool = []                           # 当前可抽取池
        self._reset_pool()

    def _reset_pool(self):
        """重新填充并打乱"""
        self._pool = self.replay_paths.copy()
        random.shuffle(self._pool)

    def sample(self) -> str:
        """
        每次随机取一个不重复的元素
        如果用完，自动重置
        """
        if not self._pool:
            self._reset_pool()

        return self._pool.pop()
    
class OfflineEval:
    def __init__(self, hdf5_path) -> None:
        debug_print("OfflineEval", f"Replay data: {hdf5_path}.", "INFO")
        self.ptr = 0
        self.episode = dict_to_list(hdf5_groups_to_dict(hdf5_path))
    
    def get_data(self):
        try:
            data = self.episode[self.ptr], self.episode[self.ptr]
        except:
            return None
        return data

    def move_once(self):
        self.ptr += 1
    
class Robot:
    def __init__(self, config, start_episode=0) -> None:
        self.name = self.__class__.__name__
        self.controllers = {}
        self.sensors = {}

        self.config = config
        self.collector = CollectAny(config, start_episode=start_episode)
        self.last_controller_data = None
        self.move_tolerance = config.get("move_tolerance", 0.001)

        self.replay_sample = None
        self.offline_eval = None
        data_path = None

        if self.config.get("deploy", False):
            data_path = self.config["deploy"].get("offline_eval", None) # List[file_path], file_path, floder_path

        if data_path is not None:
            if isinstance(data_path, list):
                replay_paths = data_path
            elif os.path.isfile(data_path):
                replay_paths = [data_path]
            else:
                 replay_paths = glob.glob(os.path.join(data_path, "*.hdf5"))
            self.replay_sample = ReplaySampler(replay_paths=replay_paths)

    def set_up(self):
        for controller_type in self.controllers.keys():
            if controller_type not in ALLOW_TYPES:
                debug_print(self.name, f"It's recommanded to set your controller type into our format.\nYOUR STPE:{controller_type}\n\
                            ALLOW_TYPES:{ALLOW_TYPES}", "WARNING")
        
        for sensor_type in self.sensors.keys():
            if sensor_type not in ALLOW_TYPES:
                debug_print(self.name, f"It's recommanded to set your sensor type into our format.\nYOUR STPE:{sensor_type}\n\
                            ALLOW_TYPES:{ALLOW_TYPES}", "WARNING")
        
        controller_names = []
        for _, controller in self.controllers.items():
            controller_names.extend(controller.keys())

        # 去重（可选）
        self.controller_names = list(set(controller_names))
        
        sensor_names = []
        for _, sensor in self.sensors.items():
            sensor_names.extend(sensor.keys())

        # 去重（可选）
        self.sensor_names = list(set(controller_names))

    def set_collect_type(self,INFO_NAMES: Dict[str, Any]):
        for key,value in INFO_NAMES.items():
            if key in self.controllers:
                for controller in self.controllers[key].values():
                    controller.set_collect_info(value)
            if key in self.sensors:
                for sensor in self.sensors[key].values():
                    sensor.set_collect_info(value)
    
    def get_obs(self):
        if self.replay_sample is not None:
            if self.offline_eval is None:
                self.offline_eval = OfflineEval(self.replay_sample.sample())
            data = self.offline_eval.get_data()
            if data is None:
                return None
            
            controller_data, sensor_data = data

            controller_data = {
                k: v
                for k, v in controller_data.items()
                if k in self.controller_names
            }

            sensor_data = {
                k: v
                for k, v in sensor_data.items()
                if k in self.sensor_names
            }

            return controller_data, sensor_data
        
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
        self.collector.collect(data[0], data[1])
    
    def finish(self, episode_id=None):
        extra_info = {}
        for controller_type in self.controllers.keys():
            extra_info[controller_type] = []
            for key in self.controllers[controller_type].keys():
                extra_info[controller_type].append(key)
        
        for sensor_type in self.sensors.keys():
            extra_info[sensor_type] = []
            for key in self.sensors[sensor_type].keys():
                extra_info[sensor_type].append(key)

        self.collector.add_extra_cfg_info(extra_info)
        self.collector.write(episode_id)
    
    def move(self, move_data, key_banned=None):
        if self.offline_eval is not None:
            self.offline_eval.move_once()
        
        if move_data is None:
            return
        for controller_type_name, controller_type in move_data.items():
            for controller_name, controller_action in controller_type.items():
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
        # reload a new tarjectory
        if self.offline_eval is not None:
            self.offline_eval = None
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

    def replay(self, data_path, key_banned=None, is_collect=False, episode_id=None):
        time_interval = 1 / 20
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
                    move_data = {
                        controller_type: {
                            controller_name: episode[controller_name],
                        },
                    }
                    self.move(move_data, key_banned=key_banned)

def remove_duplicate_keys(source_dict, keys_to_remove):
    return {k: v for k, v in source_dict.items() if k not in keys_to_remove}

if __name__ == "__main__":
    robot = Robot()
    robot.vis_video("save/test_robot/0.hdf5", "cam_head")