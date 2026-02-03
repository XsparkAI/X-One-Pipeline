import os
from typing import Dict, Any, List
import numpy as np
import time
from hardware.data.collect_any import CollectAny
from hardware.utils.base.data_handler import debug_print, hdf5_groups_to_dict
import cv2


def get_array_length(data: Dict[str, Any]) -> int:
    for value in data.values():
        if isinstance(value, dict):
            return get_array_length(value)
        elif isinstance(value, np.ndarray):
            return value.shape[0]
    raise ValueError("No np.ndarray found in data.")

def split_nested_dict(data: Dict[str, Any], idx: int) -> Dict[str, Any]:
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = split_nested_dict(value, idx)
        elif isinstance(value, np.ndarray):
            result[key] = value[idx]
        else:
            raise TypeError(f"Unsupported type: {type(value)} at key {key}")
    return result

def dict_to_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    length = get_array_length(data)
    return [split_nested_dict(data, i) for i in range(length)]

def remove_duplicate_keys(source_dict, keys_to_remove):
    return {k: v for k, v in source_dict.items() if k not in keys_to_remove}

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
