#!/usr/bin/env python3
"""
Slamware机器人控制脚本
"""

import sys
sys.path.append("./")

from robot.controller.mobile_controller import MobileController

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
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.controller = None
        self.controller_type = "user_controller"

    def set_up(self, robot_ip: str = "192.168.11.1", port: int = 1448):
        self.last_move_time = None

        self.base_url = f"http://{robot_ip}:{port}"
        self.session = requests.Session()

        self.session.headers.update({
            "Content-Type": "application/json",
            "accept": "application/json"
        })

        self.set_max_moving_speed(0.4)

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

    
    def set_map(self, map_file_path):
        #加载初始地图
        upload_success = self.upload_map(map_file_path)
        if not upload_success:
            logger.error("❌ 地图上传失败，停止任务")
            raise ConnectionError
        
        reload_success = self.reload_map()
        if not reload_success:
            logger.error("❌ 地图重新加载失败，停止任务")
            raise ConnectionError
        

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
    
    def delta_move(self, delta_pos):
        move_succ = False
        if delta_pos[0] > 0.0001:
            move_succ = self.move_straight(duration=int(delta_pos[0]), direction=0, speed_ratio=0.4)
        elif delta_pos[0] < -0.0001:
            move_succ = self.move_straight(duration=int(abs(delta_pos[0])), direction=1, speed_ratio=0.4)
        if abs(delta_pos[1]) > 0.001:
            move_succ = self.mission_rotate(angle_deg=delta_pos[1], timeout=10)
        return move_succ

    def set_move_velocity(self, vel):
        """仅接受字典 {"move_velocity": [vx, vy, omega]}，内部仅调用 move_straight / rotate_by_time。"""
        try:
            if not isinstance(vel, dict) or "move_velocity" not in vel:
                raise ValueError("vel must be dict with key 'move_velocity'")

            arr = vel["move_velocity"]
            if arr is None or len(arr) < 3:
                raise ValueError("move_velocity must be [vx, vy, omega]")

            vx, vy, omega = map(float, arr[:3])

            # # 频率控制（保持 max_vel_time）
            # now = time.time()
            # if self.last_move_time is not None:
            #     elapsed = now - self.last_move_time
            #     if elapsed < self.max_vel_time:
            #         time.sleep(self.max_vel_time - elapsed)

            if abs(vy) > 1e-3:
                logger.warning("vy 暂不支持，将被忽略")

            # 优先处理角速度：使用 rotate_by_time
            if abs(omega) > 1e-4:
                ok = self.rotate_by_time(angular_velocity=omega, duration_ms=500, timeout=10)
                self.last_move_time = time.time()
                return ok

            # 直线：使用 move_straight
            if abs(vx) > 1e-3:
                direction = 0 if vx >= 0 else 1
                speed_ratio = max(0.1, min(1.0, abs(vx) / 0.4))
                ok = self.move_straight(duration=500, direction=direction, speed_ratio=speed_ratio)
                self.last_move_time = time.time()
                return ok

            # 近零速度：直接返回
            self.last_move_time = time.time()
            return True

        except Exception as e:
            logger.error(f"设置速度时发生错误: {e}")
            return False

    def check_connection(self) -> bool:
        """检查与机器人的连接"""
        try:
            response = self.session.get(f"{self.base_url}/api/core/system/v1/power/status", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"连接机器人失败: {e}")
            return False

    def get_power_status(self) -> Optional[Dict[str, Any]]:
        """获取电源状态"""
        try:
            response = self.session.get(f"{self.base_url}/api/core/system/v1/power/status")
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"获取电源状态时发生错误: {e}")
            return None

    def upload_map(self, map_file_path: str) -> bool:
        """上传地图文件到机器人 - 改进版"""
        try:
            import os
            if not os.path.exists(map_file_path):
                logger.error(f"地图文件不存在: {map_file_path}")
                return False

            # 检查文件
            if not self.check_map_file(map_file_path):
                return False

            # 读取文件内容
            with open(map_file_path, 'rb') as file:
                map_data = file.read()

            # 设置正确的headers
            headers = {
                'Content-Type': 'application/octet-stream',
                'accept': 'application/json'
            }

            logger.info(f"开始上传地图文件: {map_file_path} (大小: {len(map_data)} 字节)")

            # 发送POST请求
            response = self.session.post(
                f"{self.base_url}/api/multi-floor/map/v1/stcm",
                data=map_data,
                headers=headers,
                timeout=30  # 增加超时时间
            )

            logger.info(f"上传响应状态码: {response.status_code}")
            logger.info(f"上传响应内容: {response.text}")

            if response.status_code == 200:
                logger.info("✅ 地图上传成功")
                return True
            else:
                logger.error(f"❌ 地图上传失败，状态码: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return False

        except Exception as e:
            logger.error(f"地图上传过程中发生错误: {e}")
            return False

    def reload_map(self) -> bool:
        """
        重新加载地图。
        在上传(upload_map)新地图后，需要调用此接口来使新地图生效。
        [Slamware RESTful API开发手册, 4.6 保存地图, source: 378]
        """
        logger.info("开始重新加载地图 (reload map)...")

        # API端点
        endpoint = f"{self.base_url}/api/multi-floor/map/v1/stcm/:reload"

        try:
            # 这是一个POST动作
            response = self.session.post(endpoint, json={}, timeout=15)  # 重新加载可能需要更长时间

            if 200 <= response.status_code < 300:
                logger.info("✅ 地图重新加载成功")
                return True
            else:
                logger.error(f"❌ 地图重新加载失败，状态码: {response.status_code}, 响应: {response.text}")
                return False
        except Exception as e:
            logger.error(f"重新加载地图时发生错误: {e}")
            return False

    def check_map_file(self, map_file_path: str) -> bool:
        """检查地图文件是否有效"""
        import os
        try:
            if not os.path.exists(map_file_path):
                logger.error(f"地图文件不存在: {map_file_path}")
                return False

            file_size = os.path.getsize(map_file_path)
            logger.info(f"地图文件大小: {file_size} 字节")

            if file_size == 0:
                logger.error("地图文件为空")
                return False

            # 读取文件前几个字节检查文件头
            with open(map_file_path, 'rb') as f:
                header = f.read(8)
                logger.info(f"文件头: {header.hex()}")

            return True
        except Exception as e:
            logger.error(f"检查地图文件时出错: {e}")
            return False

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

    def get_robot_pose(self) -> Optional[Dict[str, float]]:
        try:
            # 构建完整的API端点URL
            pose_url = f"{self.base_url}/api/core/slam/v1/localization/pose"

            logger.info(f"请求机器人位姿: {pose_url}")

            # 发送GET请求（无参数）
            response = self.session.get(pose_url, timeout=5)

            logger.info(f"位姿请求状态码: {response.status_code}")

            if response.status_code == 200:
                # 解析JSON响应
                pose_data = response.json()

                # 验证响应数据结构
                required_fields = ['x', 'y', 'z', 'yaw', 'pitch', 'roll']
                if all(field in pose_data for field in required_fields):
                    logger.info(
                        f"✅ 位姿获取成功: x={pose_data['x']:.3f}, y={pose_data['y']:.3f}, yaw={pose_data['yaw']:.3f}")
                    return pose_data
                else:
                    logger.error("❌ 位姿数据不完整，缺少必要字段")
                    logger.error(f"获取到的数据: {pose_data}")
                    return None
            else:
                logger.error(f"❌ 位姿请求失败，状态码: {response.status_code}")
                logger.error(f"错误响应: {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error("❌ 位姿请求超时")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("❌ 网络连接错误，无法获取位姿")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ 位姿响应JSON解析错误: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 获取位姿时发生未知错误: {e}")
            return None
    
    def create_move_to_action(self, x: float, y: float, yaw: float = None) -> Optional[str]:
        """创建移动到指定坐标的动作（弧度制）"""
        move_data = {
            "action_name": "slamtec.agent.actions.MoveToAction",
            "options": {
                "target": {"x": x, "y": y, "z": 0},
                "move_options": {
                    "mode": 0,
                    "flags": ["precise"],
                    "acceptable_precision": 0.1,
                    "fail_retry_count": 3
                }
            }
        }

        if yaw is not None:
            move_data["options"]["move_options"]["flags"].append("with_yaw")
            move_data["options"]["move_options"]["yaw"] = yaw

        try:
            response = self.session.post(f"{self.base_url}/api/core/motion/v1/actions", json=move_data)
            if response.status_code == 200:
                result = response.json()
                action_id = result.get("action_id")
                if action_id:
                    self.current_action_id = action_id
                    logger.info(f"移动动作创建成功，动作ID: {action_id}")
                    return action_id
            else:
                logger.error(f"创建移动动作失败，状态码: {response.status_code}, 响应: {response.text}")
            return None
        except Exception as e:
            logger.error(f"创建移动动作时发生错误: {e}")
            return None

    def create_rotate_action(self, yaw_rad: float) -> Optional[str]:
        action_name = "slamtec.agent.actions.RotateToAction"

        # 修复后的结构：目标朝向 'yaw' 必须嵌套在 'target' 字段下
        rotate_data = {
            "angle": yaw_rad,  # 绝对旋转目标 (弧度)
        }

        try:
            response = self.session.post(f"{self.base_url}/api/core/motion/v1/actions", json=rotate_data)
            if response.status_code == 200:
                result = response.json()
                action_id = result.get("action_id")
                if action_id:
                    self.current_action_id = action_id
                    logger.info(f"绝对旋转动作创建成功，动作ID: {action_id}")
                    return action_id
            else:
                logger.error(f"创建绝对旋转动作失败，状态码: {response.status_code}, 响应: {response.text}")
            return None
        except Exception as e:
            logger.error(f"创建绝对旋转动作时发生错误: {e}")
            return None
        
    def get_action_status(self, action_id: str) -> Optional[Dict[str, Any]]:
        """获取动作状态"""
        try:
            response = self.session.get(f"{self.base_url}/api/core/motion/v1/actions/{action_id}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"获取动作状态失败，状态码: {response.status_code}, 响应: {response.text}")
            return None
        except Exception as e:
            logger.error(f"获取动作状态时发生错误: {e}")
            return None

    def interpret_action_status(self, status_info: Dict[str, Any]) -> tuple:
        """解释动作状态"""
        if not status_info:
            return "unknown", False, False

        current_status = None
        result_value = None

        state = status_info.get("state")
        if isinstance(state, dict):
            current_status = state.get("status")
            result_value = state.get("result")

        if current_status is None:
            current_status = status_info.get("status")

        if current_status is None:
            return "unknown", False, False

        status_str = str(current_status)

        if status_str == "4":
            if result_value == 0:
                return "succeeded", True, True
            elif result_value == -1:
                return "failed", True, False
            else:
                return f"completed_result_{result_value}", True, False
        elif status_str == "1":
            return "running", False, False
        elif status_str in ["2", "3"]:
            return "failed", True, False
        elif status_str == "0":
            return "unknown", False, False
        else:
            return f"unknown_{status_str}", False, False

    def wait_for_action_completion(self, action_id: str, action_type: str = "动作", timeout: int = 300) -> bool:
        """等待动作完成，新增 Ctrl+C 即时终止功能。"""
        start_time = time.time()
        check_interval = 2

        logger.info(f"开始监控{action_type}完成状态，超时时间: {timeout}秒")

        while time.time() - start_time < timeout:
            try:
                status_info = self.get_action_status(action_id)

                if status_info is None:
                    logger.warning("获取动作状态失败，等待后重试")
                    time.sleep(check_interval)
                    continue

                status_str, is_completed, is_success = self.interpret_action_status(status_info)
                logger.info(f"{action_type}状态: {status_str} (完成: {is_completed}, 成功: {is_success})")

                if is_completed:
                    if is_success:
                        logger.info(f"{action_type}执行成功完成")
                        return True
                    else:
                        # 记录错误信息，以便排查失败原因
                        # 可以在此获取并打印更详细的错误码
                        logger.error(f"{action_type}执行失败")
                        return False

                elapsed = time.time() - start_time
                remaining = timeout - elapsed
                if elapsed % 10 < check_interval:
                    logger.info(f"动作进行中，已等待{elapsed:.0f}秒，剩余{remaining:.0f}秒")

                # 阻塞点：程序在这里暂停等待状态更新
                time.sleep(check_interval)

            except KeyboardInterrupt:
                logger.warning("\n[内部捕获] 检测到 Ctrl+C！正在发送紧急停止命令...")
                self.emergency_stop()  # <--- 将 terminate_current_action 替换为 emergency_stop
                logger.info("机器人运动已立即终止。")
                raise

        logger.error(f"{action_type}执行超时（{timeout}秒）")
        return False

    def mission_move(self, target_x: float, target_y: float, target_yaw: float = None) -> bool:
        """执行移动任务：移动到指定坐标（target_yaw角度制输入）"""
        logger.info("=== 开始执行移动任务 ===")

        if target_yaw is not None:
            target_yaw = math.radians(target_yaw)  # ✅ 转换角度为弧度
            logger.info(f"输入角度 {math.degrees(target_yaw):.1f}° -> 转换为弧度 {target_yaw:.3f}")

        logger.info(f"创建移动到目标点({target_x}, {target_y})的动作")

        # 假设 self.create_move_to_action 返回 move_action_id
        move_action_id = self.create_move_to_action(target_x, target_y, target_yaw)

        if not move_action_id:
            logger.error("创建移动动作失败")
            return False

        # 【核心修改点】记录当前动作 ID
        self.current_action_id = move_action_id

        logger.info("等待移动动作完成...")
        # 假设您已将 wait_for_action_completion 修复为包含 Ctrl+C 处理的版本
        move_success = self.wait_for_action_completion(move_action_id, "移动", timeout=300)

        # 任务完成后，清除当前动作 ID
        self.current_action_id = None

        if move_success:
            logger.info("移动任务执行成功")
            return True
        else:
            logger.error("移动任务执行失败")
            return False

    def mission_sleep(self, duration: int) -> bool:
        """执行停留任务：在当前位置停留指定时间"""
        logger.info("=== 开始执行停留任务 ===")

        logger.info(f"开始在当前位置停留 {duration} 秒")

        for i in range(duration):
            remaining = duration - i
            logger.info(f"停留中... 剩余{remaining}秒")
            time.sleep(1)

        logger.info("停留任务执行完成")
        return True

    def emergency_stop(self) -> None:

        logger.warning(">>> 正在执行软件紧急停止 (Emergency Stop) <<<")

        # 步骤 1: 发送零速 Guided Motion 命令实现即时停止
        zero_velocity_endpoint = f"{self.base_url}/api/core/motion/v1/guided_motion"
        guided_motion_data = {
            "linear_velocity": 0.0,
            "angular_velocity": 0.0
        }

        try:
            # 这是一个POST请求，因为 Guided Motion 总是创建一个临时的速度命令
            response = self.session.post(zero_velocity_endpoint, json=guided_motion_data, timeout=1)
            if response.status_code == 200:
                logger.info("✅ 零速引导运动指令发送成功，机器人底盘应已停止。")
            else:
                logger.warning(f"❌ 零速指令发送失败，状态码: {response.status_code}。继续执行终止行为。")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 发送零速指令时发生网络错误: {e}")

        # 步骤 2: 终止当前高阶行为 (使用您指定的 DELETE 接口)
        terminate_endpoint = f"{self.base_url}/api/core/motion/v1/actions/current"

        try:
            response = self.session.delete(terminate_endpoint, timeout=1)
            if response.status_code == 200:
                logger.info("✅ 当前高阶行为已终止 (DELETE /api/core/motion/v1/actions/current)。")
            else:
                logger.warning(f"❌ 终止高阶行为失败，状态码: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 终止高阶行为时发生网络错误: {e}")

    def set_robot_pose(self, x: float, y: float, yaw_deg: float) -> bool:
        # 强制设置机器人位姿（坐标和朝向）。
        # 使用 PUT /api/core/slam/v1/localization/pose 接口，并使用官方六自由度 JSON 结构。

        yaw_rad = math.radians(yaw_deg)
        logger.info(f"开始强制设置机器人位姿: x={x}, y={y}, yaw={yaw_deg}°")

        # 官方端点：PUT /api/core/slam/v1/localization/pose
        endpoint = f"{self.base_url}/api/core/slam/v1/localization/pose"

        pose_data = {
            "x": x,
            "y": y,
            "z": 0.0,  # 根据文档设置为 0
            "yaw": yaw_rad,
            "pitch": 0.0,  # 根据文档设置为 0
            "roll": 0.0  # 根据文档设置为 0
        }

        try:
            # 使用 PUT 方法设置资源
            response = self.session.put(endpoint, json=pose_data, timeout=10)

            if 200 <= response.status_code < 300:
                logger.info(f"✅ 机器人位姿设置成功. 状态码: {response.status_code}")
                # 额外延迟等待定位稳定
                time.sleep(1)
                return True
            else:
                logger.error(f"❌ 设置机器人位姿失败，状态码: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"设置机器人位姿时发生网络错误: {e}")
            return False
        except Exception as e:
            logger.error(f"设置机器人位姿时发生未知错误: {e}")
            return False

    def set_max_moving_speed(self, max_speed: float) -> bool:

        logger.info(f"开始设置系统最大线速度: {max_speed} m/s")

        # 官方端点: PUT /api/core/system/v1/parameter
        endpoint = f"{self.base_url}/api/core/system/v1/parameter"

        # 严格使用官方 JSON 格式，值必须是字符串
        config_data = {
            "param": "base.max_moving_speed",
            "value": str(max_speed)
        }

        try:
            response = self.session.put(endpoint, json=config_data, timeout=5)

            if 200 <= response.status_code < 300:
                logger.info(f"✅ 系统最大线速度设置成功. 状态码: {response.status_code}")
                return True
            else:
                logger.error(f"❌ 设置系统最大线速度失败，状态码: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"设置最大速度时发生网络错误: {e}")
            return False
        except Exception as e:
            logger.error(f"设置最大速度时发生未知错误: {e}")
            return False

    def move_straight(self, duration: int = 2000, direction: int = 0, speed_ratio: float = 0.5) -> bool:
        logger.info(f"开始直线运动: {duration}ms, 方向{'前进' if direction == 0 else '后退'}")

        try:
            # 基础参数验证
            if duration <= 0:
                logger.error("持续时间必须为正数")
                return False

            # 构建运动指令
            move_data = {
                "action_name": "slamtec.agent.actions.MoveByAction",
                "options": {
                    "direction": direction,
                    "duration": duration,
                    "speed_ratio": max(0.1, min(1.0, speed_ratio))  # 限制在0.1-1.0范围内
                }
            }

            # 发送运动命令
            response = self.session.post(
                f"{self.base_url}/api/core/motion/v1/actions",
                json=move_data,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                action_id = result.get("action_id")

                if action_id:
                    self.current_action_id = action_id
                    logger.info(f"运动指令已发送，动作ID: {action_id}")

                    # 等待运动完成
                    success = self.wait_for_action_completion(action_id, "直线运动")
                    self.current_action_id = None
                    return success
                else:
                    logger.error("未获取到有效动作ID")
                    return False
            else:
                logger.error(f"运动指令发送失败: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"直线运动执行异常: {e}")
            self.current_action_id = None
            return False

    def rotate_by_time(self, angular_velocity: float, duration_ms: int, timeout: int = 60) -> bool:
        logger.info(f"=== 开始旋转控制（使用theta参数）===")
        logger.info(f"角速度: {angular_velocity:.3f}rad/s, 持续时间: {duration_ms}ms")

        # 计算旋转角度（用于日志显示）
        total_angle = angular_velocity * (duration_ms / 1000)
        logger.info(f"预计旋转角度: {total_angle:.3f}rad ({math.degrees(total_angle):.1f}°)")

        try:
            # 参数验证
            if duration_ms <= 0:
                logger.error("持续时间必须为正数")
                return False

            if abs(angular_velocity) < 0.001:
                logger.error("角速度过小，请设置有效的角速度")
                return False

            # 根据图片信息，使用theta参数而不是angular_velocity
            rotate_data = {
                "action_name": "slamtec.agent.actions.MoveByAction",
                "options": {
                    "theta": angular_velocity,  # 关键修正：使用theta而不是angular_velocity
                    "duration": duration_ms
                }
            }

            logger.info(f"发送旋转指令: {rotate_data}")

            # 发送旋转命令
            response = self.session.post(
                f"{self.base_url}/api/core/motion/v1/actions",
                json=rotate_data,
                timeout=10
            )

            logger.info(f"旋转请求状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                action_id = result.get("action_id")

                if action_id:
                    self.current_action_id = action_id
                    logger.info(f"✅ 旋转动作创建成功，动作ID: {action_id}")

                    # 等待旋转完成
                    success = self.wait_for_action_completion(
                        action_id,
                        f"旋转(theta={angular_velocity}rad/s, t={duration_ms}ms)",
                        timeout=timeout
                    )

                    self.current_action_id = None

                    if success:
                        logger.info("✅ 旋转执行成功完成")
                        return True
                    else:
                        logger.error("❌ 旋转执行失败或超时")
                        return False
                else:
                    logger.error("❌ 未获取到有效动作ID")
                    logger.error(f"响应内容: {result}")
                    return False
            else:
                logger.error(f"❌ 旋转指令发送失败，状态码: {response.status_code}")
                logger.error(f"错误响应: {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ 旋转过程中发生错误: {e}")
            self.current_action_id = None
            return False


    def mission_rotate(self, angle_deg: float, timeout: int) -> bool:
        logger.info(f"=== 开始执行原地旋转任务 ===")
        logger.info(f"目标旋转角度: {angle_deg}°")

        try:
            # 获取当前机器人位姿
            pose = self.get_robot_pose()
            if not pose:
                logger.error("❌ 无法获取当前位姿，旋转任务终止")
                return False

            # 记录当前位姿信息
            current_x = pose['x']
            current_y = pose['y']
            current_yaw_rad = pose['yaw']
            current_yaw_deg = math.degrees(current_yaw_rad)

            logger.info(f"当前位姿: x={current_x:.3f}, y={current_y:.3f}, yaw={current_yaw_deg:.1f}°")

            # 计算目标朝向角度
            target_yaw_deg = current_yaw_deg + angle_deg
            # 规范化角度到0-360范围
            target_yaw_deg = target_yaw_deg % 360
            if target_yaw_deg < 0:
                target_yaw_deg += 360

            logger.info(f"目标朝向角度: {target_yaw_deg:.1f}°")

            # 执行移动任务到同一位置但旋转指定角度
            success = self.mission_move(
                target_x=current_x,
                target_y=current_y,
                target_yaw=target_yaw_deg
            )

            if success:
                logger.info(f"✅ 原地旋转{angle_deg}°任务执行成功")
                return True
            else:
                logger.error(f"❌ 原地旋转{angle_deg}°任务执行失败")
                return False

        except Exception as e:
            logger.error(f"❌ 旋转任务执行过程中发生错误: {e}")
            return False


if __name__ == "__main__":
    mobile = SlamwareRobotController("mobile")

    mobile.set_up(robot_ip="192.168.11.1")

    mobile.set_collect_info(["position"])

    # mobile.upload_map("real1_walled.stcm")

    
    # idx = 0
    # while idx < 1:
    #     idx += 1
    #     move_data = {
    #         "move_velocity": [0.5, 0.0, 0.0],
    #     }
    #     mobile.set_move_velocity(move_data)
    #     print(f"move{idx}")
    #     time.sleep(0.1)
    # move_data = {
    #     "move_velocity": [0.0, 0.0, 0.0],
    # }
    # mobile.set_move_velocity(move_data)

    # try:
    #     while True:
    #         data = mobile.get_move_velocity()
    #         print(data)
    #         time.sleep(1/5)
    # except KeyboardInterrupt:
    #     logger.info("检测到 Ctrl+C，发送紧急停止并退出...")
    #     try:
    #         mobile.emergency_stop()
    #     except Exception:
    #         logger.exception("执行 emergency_stop 时发生错误")
    #     try:
    #         if hasattr(mobile, 'session') and mobile.session is not None:
    #             mobile.session.close()
    #     except Exception:
    #         logger.exception("关闭 session 时发生错误")
    #     logger.info("已退出")