import sys
sys.path.append("./")

import threading
from typing import Iterable, Sequence, Union

import rclpy
from geometry_msgs.msg import Twist

from robot.controller.mobile_controller import MobileController
from robot.utils.ros.ros2_publisher import ROS2Publisher
from robot.utils.base.data_handler import debug_print

import numpy as np
import requests
import json
import time
import logging
import math
import sys
from typing import Optional, Dict, Any

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SlamwareRobotController(MobileController):
    """Minimal ROS2 velocity controller that publishes /cmd_vel_no_limit.

    This adapts the tested pattern to the current ros2_ws. It only depends on
    rclpy and the helper ROS2Publisher, and avoids custom message deps like
    BunkerRCState.
    """

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.controller_type = "user_controller"
        self.controller = None

    def set_up(self, robot_ip: str = "192.168.11.1", port: int = 1448, vel_topic: str = "/cmd_vel_no_limit", publish_period: float = 0.01):
        self.vel_topic = vel_topic
        self.publish_period = publish_period
        self._ros_initialized_here = False
        self._pub_thread = None

        if not rclpy.ok():
            rclpy.init()
            self._ros_initialized_here = True

        publisher = ROS2Publisher(self.vel_topic, Twist, continuous=True)
        publisher.update_msg(Twist())  # start with zero cmd

        self._pub_thread = threading.Thread(target=publisher.continuous_publish, args=(self.publish_period,), daemon=True)
        self._pub_thread.start()

        self.controller = {"publisher": publisher}

        self.last_move_time = None

        self.base_url = f"http://{robot_ip}:{port}"
        self.session = requests.Session()

        self.session.headers.update({
            "Content-Type": "application/json",
            "accept": "application/json"
        })

        # self.set_max_moving_speed(0.4)

        self.current_action_id = None
        logger.info(f"机器人控制器初始化完成，连接地址: {self.base_url}")

        if not self.check_connection():
            logger.error("无法连接到机器人，请检查网络连接和IP地址")
            exit()

        logger.info("=== 检查机器人API状态 ===")
        self.check_map_apis()

        power_status = self.get_power_status()
        if power_status:
            battery = power_status.get("batteryPercentage", "未知")
            docking = power_status.get("dockingStatus", "未知")
            logger.info(f"机器人状态 - 电量: {battery}%, 充电状态: {docking}")


    def _parse_vel(self, vel: Union[dict, Sequence[float]]) -> Sequence[float]:
        # Accept {"move_velocity": [vx, vy, omega]} or list/tuple of length 3/6
        if isinstance(vel, dict) and "move_velocity" in vel:
            vel = vel["move_velocity"]
        if not isinstance(vel, Iterable):
            raise ValueError("vel must be iterable or dict with key 'move_velocity'")
        arr = list(vel)
        if len(arr) < 3:
            raise ValueError("move_velocity must have at least 3 elements [vx, vy, omega]")
        return arr

    def set_move_velocity(self, vel: Union[dict, Sequence[float]]):
        debug_print("SlamwareRobotController", f"\033[92m{self.name:<10}\033[0m: "f"[{', '.join(f'{x:9.3f}' for x in vel)}]", "INFO")
        if not self.controller or "publisher" not in self.controller:
            raise RuntimeError("Controller not set up; call set_up() first")

        arr = self._parse_vel(vel)
        vx, vy, omega = arr[0], arr[1], arr[2]

        msg = Twist()
        msg.linear.x = float(vx)
        msg.linear.y = float(vy)
        msg.angular.z = float(omega)

        self.controller["publisher"].update_msg(msg)

    def get_move_velocity(self):
        """
        获取机器人当前速度（vx, vy, wz）
        vx / vy 单位：m/s
        wz 单位：rad/s
        """
        try:
            response = self.session.get(f"{self.base_url}/api/core/motion/v1/speed", timeout=3)
            if response.status_code != 200:
                logger.error(f"获取速度失败，响应码: {response.status_code}")
                return None

            data = response.json()
            logger.debug(f"速度接口返回: {data}")

            vel = data.get("velocity")
            if vel is None:
                vel = data.get("result", {}).get("velocity")
            if vel is None:
                vel = data

            vx = vel.get("vx", 0.0)     # 前向速度 m/s
            vy = vel.get("vy", 0.0)     # 侧向速度（通常为0）
            wz = vel.get("omega", 0.0)   # 角速度 rad/s

            return np.array([vx, vy, wz])

        except Exception as e:
            logger.error(f"获取速度时发生错误: {e}")
            return None

    def get_information(self):
        """覆盖基类信息获取，支持采集底盘速度/位姿。"""
        info = {
            "move_velocity": None,
            "position": None,
        }

        try:
            if hasattr(self, "collect_info") and "move_velocity" in self.collect_info:
                info["move_velocity"] = self.get_move_velocity()

            if hasattr(self, "collect_info") and "position" in self.collect_info:
                pose = self.get_robot_pose()
                if pose:
                    info["position"] = np.array([
                        pose.get("x", 0.0),
                        pose.get("y", 0.0),
                        pose.get("z", 0.0),
                        pose.get("yaw", 0.0),
                        pose.get("pitch", 0.0),
                        pose.get("roll", 0.0),
                    ])
        except Exception as exc:  # 防御式，避免采集过程中断
            logger.error(f"获取底盘信息失败: {exc}")

        return info
    
    def check_map_apis(self):
        """检查机器人地图相关API是否可用"""
        try:
            # 检查地图列表的API似乎不支持GET，我们改为检查 POI 列表
            response_poi = self.session.get(f"{self.base_url}/api/multi-floor/map/v1/pois")
            logger.info(f"获取POI列表 - 状态码: {response_poi.status_code}")
            if response_poi.status_code == 200:
                logger.info(f"现有POI: {response_poi.json()}")

            # 检查系统信息 (使用 /robot/info)
            response_info = self.session.get(f"{self.base_url}/api/core/system/v1/robot/info")
            logger.info(f"系统信息 - 状态码: {response_info.status_code}")
            if response_info.status_code == 200:
                logger.info(f"系统信息: {response_info.json().get('model', '未知')}")

        except Exception as e:
            logger.error(f"检查API时出错: {e}")

    def get_power_status(self) -> Optional[Dict[str, Any]]:
        """获取电源状态"""
        try:
            response = self.session.get(f"{self.base_url}/api/core/system/v1/power/status")
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"获取电源状态时发生错误: {e}")
            return None
        
    def check_connection(self) -> bool:
        """检查与机器人的连接"""
        try:
            response = self.session.get(f"{self.base_url}/api/core/system/v1/power/status", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"连接机器人失败: {e}")
            return False
    
    def stop(self):
        if not self.controller:
            return
        pub = self.controller.get("publisher")
        if pub:
            pub.stop()
        if self._pub_thread:
            self._pub_thread.join(timeout=1.0)
        if pub:
            pub.destroy_node()
        if self._ros_initialized_here and rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":
    import time

    # 使用受监控的 /cmd_vel，并放慢发布频率，降低速度以通过监控限制
    ctrl = SlamwareRobotController("slamware_ros2", vel_topic="/cmd_vel_no_limit", publish_period=0.01)
    ctrl.set_up()

    # 先发零速，清状态
    ctrl.set_move_velocity({"move_velocity": [0.0, 0.0, 0.0]})
    time.sleep(0.1)
    ctrl.set_move_velocity({"move_velocity": [0.0, 0.0, 0.0]})
    time.sleep(0.1)

    # 小速度前进，保持 1.5s
    ctrl.set_move_velocity({"move_velocity": [0.05, 0.0, 0.0]})
    time.sleep(1)

    # 小角速度旋转，保持 1s
    ctrl.set_move_velocity({"move_velocity": [0.0, 0.0, 0.2]})
    time.sleep(7.9)

    # 再次停止
    ctrl.set_move_velocity({"move_velocity": [0.0, 0.0, 0.0]})
    time.sleep(0.3)
    ctrl.set_move_velocity({"move_velocity": [0.0, 0.0, 0.0]})
    time.sleep(0.2)

    ctrl.stop()