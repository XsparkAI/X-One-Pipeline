import sys
sys.path.append("./")

from robot.controller.dexhand_controller import DexHandController
from typing import Dict, Any
import wujihandpy
from omegaconf import DictConfig, OmegaConf
import numpy as np
from robot.utils.base.data_manager import UDPDataManager
import threading
import time
import os

class WujiController(DexHandController):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.controller_type = "robotic_hand"
        self.is_set_up = False
        self.controller = None
    
    def run(self):
        # 等待首帧数据同步
        left_target, right_target = self.dm.wait_for_data()
        if left_target is None or right_target is None:
            print("无法同步数据，退出")
            return
        
        # 根据手性选择初始目标
        current_target = left_target if self.hand_type == "left" else right_target
        
        with self.controller.realtime_controller(enable_upstream=True, filter=wujihandpy.filter.LowPass(cutoff_freq=self.cfg.control.lowpass_cutoff)) as controller:
            update_period = 1.0 / self.cfg.control.freq

            print(f"进入{self.hand_type}手控制循环 (Ctrl+C 退出)")
            while True:
                loop_start = time.perf_counter()

                # 获取最新目标数据
                left_data, right_data, has_new = self.dm.get_hand_data()
                data = left_data if self.hand_type == "left" else right_data
                
                if has_new and not np.all(data == 0):
                    current_target = data

                # Realtime API 不阻塞
                controller.set_joint_target_position(current_target)


                # 获取当前状态
                actual = controller.get_joint_actual_position()
                error = current_target - actual
                effort = controller.get_joint_actual_effort()
                
                # 计算全手百分比
                error_pct = np.abs(error / self.pos_range) * 100
                effort_pct = np.abs(effort / self.effort_limit) * 100
                
                # 格式化输出: [F1] [F2] [F3] [F4] [F5]
                def format_hand(data):
                    return " ".join([f"[{' '.join([f'{x:3.0f}' for x in finger])}]" for finger in data])

                if os.getenv("INFO_LEVEL", "INFO").upper() == "DEBUG":
                    sys.stdout.write(f"\rERR%:{format_hand(error_pct)} | EFF%:{format_hand(effort_pct)}")
                    sys.stdout.flush()

                # 保持控制频率
                elapsed = time.perf_counter() - loop_start
                if elapsed < update_period:
                    time.sleep(update_period - elapsed)
        
    def set_up(self, hand_type, cfg_path: str):
        self.cfg = OmegaConf.load(cfg_path)
        self.dm = UDPDataManager(port=self.cfg.network.udp_port)
        self.dm.start()
        self.hand_type = hand_type

        if hand_type == "left":
            self.controller = wujihandpy.Hand(self.cfg.hardware.left_hand_serial)
        elif hand_type == "right":
            self.controller = wujihandpy.Hand(self.cfg.hardware.right_hand_serial)

        self.controller.disable_thread_safe_check()

        self.controller.write_joint_enabled(True)
        
        # 预读取限制用于百分比计算
        self.effort_limit = self.controller.read_joint_effort_limit()
        self.pos_lower = self.controller.read_joint_lower_limit()
        self.pos_upper = self.controller.read_joint_upper_limit()
        self.pos_range = np.maximum(self.pos_upper - self.pos_lower, 0.01) # 防止除零

        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()

    def get_joint(self):
        positions = self.controller.read_joint_actual_position()
        return positions

    def set_joint(self, joint):
        self.controller.write_joint_target_position(np.array(joint, dtype=np.float64))
        print("Set joint command sent.")

        
    def __repr__(self):
        if self.controller is not None:
            return f"{self.name}: \n \
                    controller: {self.controller}"
        else:
            return super().__repr__()

if __name__ == "__main__":
    import time
    left_wuji = WujiController("left_hand")
    right_wuji =  WujiController("right_hand")
    left_wuji.set_up("left", "third_party/wuji_hand/hand_setting.yml")

    move_data = {
                "joint": np.array([
                    # J1   J2   J3   J4
                    [0.5, 0.0, 0.0, 0.0],  # F1
                    [0.5, 0.0, 0.0, 0.0],  # F2
                    [0.5, 0.0, 0.0, 0.0],  # F3
                    [0.5, 0.0, 0.0, 0.0],  # F4
                    [0.5, 0.0, 0.0, 0.0],  # F5
                ],dtype=np.float64,)}
    
    left_wuji.move(move_data)
    # right_wuji.move(move_data)
    
    time.sleep(2)
    left_wuji.controller.write_joint_enabled(True)
    # right_wuji.controller.write_joint_enabled(False)
