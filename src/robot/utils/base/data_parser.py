"""
数据解析模块
负责将协议数据转换为灵巧手可用的 numpy 数组格式
"""

import numpy as np
from typing import Dict, Any, Tuple


def parse_hand_data(data: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """
    解析手部关节数据
    
    将字典格式的关节数据转换为 (5, 4) 的 numpy 数组。
    
    Args:
        data: 包含关节数据的字典，键名格式为 "left_finger{1-5}_joint{1-4}"
              或 "right_finger{1-5}_joint{1-4}"
    
    Returns:
        (left_array, right_array): 左右手的关节数据，shape=(5, 4)
        
    数组布局:
        - 行: 5个手指 (F1-F5)
        - 列: 4个关节 (J1-J4)
    """
    left = np.zeros((5, 4), dtype=np.float64)
    right = np.zeros((5, 4), dtype=np.float64)
    
    for finger in range(1, 6):
        for joint in range(1, 5):
            left_key = f"left_finger{finger}_joint{joint}"
            right_key = f"right_finger{finger}_joint{joint}"
            
            if left_key in data:
                left[finger - 1, joint - 1] = float(data[left_key])
            if right_key in data:
                right[finger - 1, joint - 1] = float(data[right_key])
    
    return left, right


def extract_response_data(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取响应中的数据部分
    
    Args:
        response: 服务器原始响应
        
    Returns:
        提取的数据字典
    """
    return response.get("res", response)
