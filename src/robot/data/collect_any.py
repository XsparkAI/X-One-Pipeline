"""
This function stores all incoming data without any filtering or config checks.
The storage format differs from the standard format used for dual-arm robots:
each controller/sensor corresponds to a separate group.
"""
import os

from robot.utils.base.data_handler import debug_print

import os
import numpy as np
import json
import glob
import re
import h5py

KEY_BANNED = ["timestamp"]

class CollectAny:
    def __init__(self, config=None, start_episode=0, resume=False):
        
        self.config = config
        self.episode = []
        self.move_check = config.get("move_check", False) if config is not None else False
        self.last_controller_data = None
        self.resume = resume
        self.handler = None
        self.move_tolerance = config.get("move_tolerance", 0.001)
        
        # Initialize episode_index based on resume parameter
        if resume and config is not None:
            self.episode_index = self._get_next_episode_index()
        else:
            self.episode_index = start_episode
    
    def _add_data_transform_pipeline(self, handler):
        self.handler = handler

    def _get_next_episode_index(self):
        save_dir = os.path.join(self.config["save_dir"], f"{self.config['task_name']}")
        if not os.path.exists(save_dir):
            debug_print("CollectAny", f"Save path {save_dir} does not exist, starting from episode 0", "INFO")
            return 0

        hdf5_files = glob.glob(os.path.join(save_dir, "*.hdf5"))
        if not hdf5_files:
            debug_print("CollectAny", f"No existing hdf5 files found in {save_dir}, starting from episode 0", "INFO")
            return 0

        existing_ids = set()
        for file_path in hdf5_files:
            file_name = os.path.basename(file_path)
            match = re.match(r"(\d+)\.hdf5", file_name)
            if match:
                existing_ids.add(int(match.group(1)))

        next_episode = 0
        while next_episode in existing_ids:
            next_episode += 1

        debug_print("CollectAny", f"Found {len(hdf5_files)} existing episodes, next free episode id {next_episode}", "INFO")
        return next_episode

    def collect(self, controllers_data, sensors_data):
        episode_data = {}
        if controllers_data is not None:    
            for controller_name, controller_data in controllers_data.items():
                episode_data[controller_name] = controller_data

        if sensors_data is not None:    
            for sensor_name, sensor_data in sensors_data.items():
                episode_data[sensor_name] = sensor_data
        
        if self.move_check:
            if controllers_data is None:
                self.episode.append(episode_data)
            elif self.last_controller_data is None:
                self.last_controller_data = controllers_data
                self.episode.append(episode_data)
            else:
                if self.move_check_success(controllers_data, tolerance=self.move_tolerance):
                    self.episode.append(episode_data)
                else:
                    debug_print("CollectAny", f"robot is not moving, skip this frame!", "INFO")
                self.last_controller_data = controllers_data
        else:
            self.episode.append(episode_data)
    
    def get_item(self, controller_name, item):
        data = None
        for ep in self.episode:
            if controller_name in ep.keys():
                if data is None:
                    data = [ep[controller_name][item]] 
                else:
                    data.append(ep[controller_name][item])
        if data is None:
            debug_print("CollectAny", f"item {item} not in {controller_name}", "ERROR")
            return None

        data = np.array(data)
        return data
        
    def add_extra_cfg_info(self, extra_info):
        save_dir = os.path.join(self.config["save_dir"], f"{self.config['task_name']}/")
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        config_path = os.path.join(save_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            for key in extra_info.keys():
                if key in self.config.keys():
                    value = self.config[key]
                    if not isinstance(value, list):
                        value = [value]
                    value.append(extra_info[key])
                    
                    self.config[key] = value
                else:
                    self.config[key] = extra_info[key]
        else:
            if len(self.episode) > 0:
                for key in self.episode[0].keys():
                    self.config[key] = list(self.episode[0][key].keys())
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)
        
    def write(self, episode_id=None):
        save_dir = os.path.join(self.config["save_dir"], f"{self.config['task_name']}")
        
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        config_path = os.path.join(save_dir, "config.json")
        if not os.path.exists(config_path):
             if len(self.episode) > 0:
                for key in self.episode[0].keys():
                    self.config[key] = list(self.episode[0][key].keys())

             with open(config_path, 'w', encoding='utf-8') as f:
                 json.dump(self.config, f, ensure_ascii=False, indent=4)
        if not episode_id is None:
            hdf5_path = os.path.join(save_dir, f"{episode_id}.hdf5")
        else:
            hdf5_path = os.path.join(save_dir, f"{self.episode_index}.hdf5")
        
        id_input = self.episode_index if episode_id is None else episode_id
       
        mapping = {}
        for ep in self.episode:
            for outer_key, inner_dict in ep.items():
                if isinstance(inner_dict, dict):
                    mapping[outer_key] = set(inner_dict.keys())
        
        if self.handler:
            self.handler(self, save_dir, id_input, mapping)
        else:
            with h5py.File(hdf5_path, "w") as f:
                obs = f
                for name, items in mapping.items():
                    group = obs.create_group(name)
                    for item in items:
                        data = self.get_item(name, item)
                        group.create_dataset(item, data=data)
            debug_print("CollectAny", f"write to {hdf5_path}", "INFO")
        self.episode = []
        self.episode_index += 1

    def move_check_success(self, controller_data: dict, tolerance: float) -> bool:
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
                        return True 

                    if np.any(np.abs(current_arr - previous_arr) > tolerance):
                        return True 
            else:
                current_arr = np.atleast_1d(current_subdata)
                previous_arr = np.atleast_1d(previous_subdata)

                if current_arr.shape != previous_arr.shape:
                    return True

                if np.any(np.abs(current_arr - previous_arr) > tolerance):
                    return True

        return False