import h5py
from typing import *
import cv2
import numpy as np
import os
import fnmatch
import sys
import select
from typing import Dict, Any, List

def get_item(Dict_data: Dict, item):
    if isinstance(item, str):
        keys = item.split(".")
        data = Dict_data
        for key in keys:
            data = data[key]
    elif isinstance(item, list):
        key_item = None
        for it in item:
            now_data = get_item(Dict_data, it)
            # import pdb;pdb.set_trace()
            if key_item is None:
                key_item = now_data
            else:
                key_item = np.column_stack((key_item, now_data))
        data = key_item
    else:
        raise ValueError(f"input type is not allow!")
    return data

def hdf5_to_dict(h5obj):
    if isinstance(h5obj, h5py.Dataset):
        return h5obj[()]
    elif isinstance(h5obj, h5py.Group):
        return {k: hdf5_to_dict(v) for k, v in h5obj.items()}
    else:
        return None


def load_hdf5_as_dict(hdf5_path):
    with h5py.File(hdf5_path, "r") as f:
        return hdf5_to_dict(f)
        
def hdf5_groups_to_dict(hdf5_path):
    """
    读取 HDF5 文件，返回真正的嵌套 dict
    - dict.keys() 只包含第一层
    - 子 group / dataset 保持原始层级
    """
    import h5py

    def read_group(group):
        out = {}
        for key, item in group.items():
            if isinstance(item, h5py.Dataset):
                out[key] = item[()]
            elif isinstance(item, h5py.Group):
                out[key] = read_group(item)
        return out

    with h5py.File(hdf5_path, "r") as f:
        result = read_group(f)

    return result

def get_files(directory, extension):
    """使用pathlib获取所有匹配的文件"""
    file_paths = []
    for root, _, files in os.walk(directory):
            for filename in fnmatch.filter(files, extension):
                file_path = os.path.join(root, filename)
                file_paths.append(file_path)
    return file_paths

def get_array_length(data: Dict[str, Any]) -> int:
    """获取最外层np.array的长度"""
    for value in data.values():
        if isinstance(value, dict):
            return get_array_length(value)
        elif isinstance(value, np.ndarray):
            return value.shape[0]
        elif isinstance(value, list):
            return len(value)
    raise ValueError("No np.ndarray found in data.")

def split_nested_dict(data: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """提取每一帧的子结构"""
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = split_nested_dict(value, idx)
        elif isinstance(value, np.ndarray):
            result[key] = value[idx]
        elif isinstance(value, list):
            result[key] = value[idx]
        else:
            raise TypeError(f"Unsupported type: {type(value)} at key {key}")
    return result

def dict_to_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    length = get_array_length(data)
    return [split_nested_dict(data, i) for i in range(length)]

def debug_print(name, info, level="INFO"):
    levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
    if level not in levels.keys():
        debug_print("DEBUG_PRINT", f"level setting error : {level}", "ERROR")
        return
    env_level = os.getenv("INFO_LEVEL", "INFO").upper()
    env_level_value = levels.get(env_level, 20)

    msg_level_value = levels.get(level.upper(), 20)

    if msg_level_value < env_level_value:
        return

    colors = {
        "DEBUG": "\033[94m",   # blue
        "INFO": "\033[92m",    # green
        "WARNING": "\033[93m", # yellow
        "ERROR": "\033[91m",   # red
        "ENDC": "\033[0m",
    }
    color = colors.get(level.upper(), "")
    endc = colors["ENDC"]
    print(f"{color}[{level}][{name}] {info}{endc}")

def is_enter_pressed():
    return select.select([sys.stdin], [], [], 0)[0] and sys.stdin.read(1) == '\n'    

def vis_video(data_path, picture_key, save_path=None, fps=30):
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
    episode = dict_to_list(hdf5_groups_to_dict(data_path))
    
    video_writer = None
    
    for idx, ep in enumerate(episode):
        img_data = ep[picture_key]["color"]
        
        if isinstance(img_data, (bytes, bytearray)) or (isinstance(img_data, np.ndarray) and img_data.ndim == 1):
            img_array = np.frombuffer(img_data, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        else:
            img = img_data 
        
        # RGB -> BGR
        img = img[:,:,::-1]
        if save_path:
            if video_writer is None:
                h, w = img.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # mp4 编码
                video_writer = cv2.VideoWriter(save_path, fourcc, fps, (w, h))
            
            video_writer.write(img)
        else:
            cv2.imshow(f"{picture_key}", img)
            cv2.waitKey(int(1000 / fps)) 

    if video_writer:
        video_writer.release()
        debug_print("vis_video", f"save video at: {save_path} .", "INFO")


class DataBuffer:
    '''
    一个用于共享存储不同组件采集的数据的信息的类
    输入:
    manager: 创建的一个独立的控制器, multiprocessing::Manager
    '''
    def __init__(self, manager):
        self.manager = manager
        self.buffer = manager.dict()

    def collect(self, name, data):
        if name not in self.buffer:
            self.buffer[name] = self.manager.list()
        self.buffer[name].append(data)

    def get(self):
        return dict(self.buffer)

