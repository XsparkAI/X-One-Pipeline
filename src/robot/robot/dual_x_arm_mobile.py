from robot.robot.base_robot import Robot
from robot.controller.Y1_controller import Y1Controller
from robot.sensor.V4l2_sensor import V4l2Sensor
from robot.controller.SlamwareRobot_controller import SlamwareRobotController
from datetime import datetime
import time

class Dual_X_Arm_Mobile(Robot):
    def __init__(self, base_config):
        super().__init__(base_config=base_config)

        self.first_start = True
        self.controllers = {
            "arm":{
                "left_arm": Y1Controller("left_arm"),
                "right_arm": Y1Controller("right_arm"),
            },
            "mobile":{
                "slamware": SlamwareRobotController("slamware"),
            },
        }
        self.sensors = {
            "image": {
                "cam_head": V4l2Sensor("cam_head"),
                "cam_left_wrist": V4l2Sensor("cam_left_wrist"),
                "cam_right_wrist": V4l2Sensor("cam_right_wrist"),
            },
        }

    def set_up(self, teleop=False):
        super().set_up()
        self.teleop_mode = teleop
        self.controllers["arm"]["left_arm"].set_up(self.robot_config['ROBOT_CAN']['left_arm'], teleop=teleop)
        self.controllers["arm"]["right_arm"].set_up(self.robot_config['ROBOT_CAN']['right_arm'], teleop=teleop)
        self.controllers["mobile"]["slamware"].set_up(self.robot_config['SLAMWARE']['robot_ip'], self.robot_config['SLAMWARE']['port'])

        self.sensors["image"]["cam_head"].set_up(self.robot_config['CAMERA_SERIALS']['head'], is_depth=False, is_jpeg=True)
        self.sensors["image"]["cam_left_wrist"].set_up(self.robot_config['CAMERA_SERIALS']['left_wrist'], is_depth=False, is_jpeg=True)
        self.sensors["image"]["cam_right_wrist"].set_up(self.robot_config['CAMERA_SERIALS']['right_wrist'], is_depth=False, is_jpeg=True)
        
        self.set_collect_type({"arm": ["joint", "qpos", "gripper"], "image": ["color"], "mobile": ["move_velocity"]})
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ✅ Setup complete.")

    def reload_cameras(self):
        try:
            """Cleanup existing camera devices"""
            self.sensors["image"]["cam_head"].cleanup()
            self.sensors["image"]["cam_left_wrist"].cleanup()
            self.sensors["image"]["cam_right_wrist"].cleanup()
            print("Cleaning up existing cameras done.")

            """Reload camera devices"""
            self.sensors["image"]["cam_head"].set_up(self.robot_config['CAMERA_SERIALS']['head'], is_depth=False, is_jpeg=True)
            self.sensors["image"]["cam_left_wrist"].set_up(self.robot_config['CAMERA_SERIALS']['left_wrist'], is_depth=False, is_jpeg=True)
            self.sensors["image"]["cam_right_wrist"].set_up(self.robot_config['CAMERA_SERIALS']['right_wrist'], is_depth=False, is_jpeg=True)
            print("[INFO][camera] ✅ Cleaned up existing cameras.")
        except Exception as e:
            print(f"Error reloading cameras: {str(e)}")

    def reset(self):
        super().reset()
        
        if self.teleop_mode:
            self._change_mode(teleop=False)
        time.sleep(2) # TODO
        move_data = {
            "arm":{
                "left_arm":{
                    "joint": self.robot_config['init_qpos']['left_arm'],
                    "gripper":  self.robot_config['init_qpos']['left_gripper'],
                },
                "right_arm":{
                    "joint": self.robot_config['init_qpos']['right_arm'],
                    "gripper":  self.robot_config['init_qpos']['right_gripper'],
                }
            }
        }
        self.move(move_data)
        time.sleep(5) # TODO
        if self.teleop_mode:
            self._change_mode(teleop=True)
    
    # ======================== EXTRA ======================== #
    def _change_mode(self, teleop):
        time.sleep(1)
        self.controllers["arm"]["left_arm"].change_mode(teleop)
        time.sleep(1)
        self.controllers["arm"]["right_arm"].change_mode(teleop)
        time.sleep(1)
    
    def set_map(self, map_path):
        self.controllers["mobile"]["slamware"].set_map(map_path)
