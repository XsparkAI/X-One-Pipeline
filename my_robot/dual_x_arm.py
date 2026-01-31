import sys
sys.path.append("./")

from robot.robot.base_robot import Robot
from robot.controller.Y1_controller import Y1Controller
from robot.sensor.V4l2_sensor import V4l2Sensor
from config._GLOBAL_CONFIG import CAMERA_SERIALS, ROBOT_CAN, START_POSITION_ANGLE_LEFT_ARM, START_POSITION_ANGLE_RIGHT_ARM
import time

condition = {
    "save_path": "./save/",
    "task_name": "new",
    "save_format": "hdf5",
    "save_freq": 10, 
}

class XsparkRobot(Robot):
    def __init__(self, condition=condition, move_check=True, start_episode=0):
        super().__init__(condition=condition, move_check=move_check, start_episode=start_episode)
        self.first_start = True
        self.controllers = {
            "arm":{
                "left_arm": Y1Controller("left_arm"),
                "right_arm": Y1Controller("right_arm"),
            },
        }
        self.sensors = {
            "image": {
                "cam_head": V4l2Sensor("cam_head"), # CvSensor
                "cam_left_wrist": V4l2Sensor("cam_left_wrist"),
                "cam_right_wrist": V4l2Sensor("cam_right_wrist"),
            },
        }

    def set_up(self, teleop=False):
        super().set_up()
        self.teleop_mode = teleop
        self.controllers["arm"]["left_arm"].set_up(ROBOT_CAN['left_arm'], teleop=teleop)
        self.controllers["arm"]["right_arm"].set_up(ROBOT_CAN['right_arm'], teleop=teleop)

        self.sensors["image"]["cam_head"].set_up(CAMERA_SERIALS['head'], is_depth=False, is_jepg=True)
        self.sensors["image"]["cam_left_wrist"].set_up(CAMERA_SERIALS['left_wrist'], is_depth=False, is_jepg=True)
        self.sensors["image"]["cam_right_wrist"].set_up(CAMERA_SERIALS['right_wrist'], is_depth=False, is_jepg=True)
        
        self.set_collect_type({"arm": ["joint", "qpos", "gripper"], "image": ["color"]})
        print("set up success!")

    def reload_cameras(self):
        try:
            """Cleanup existing camera devices"""
            self.sensors["image"]["cam_head"].cleanup()
            self.sensors["image"]["cam_left_wrist"].cleanup()
            self.sensors["image"]["cam_right_wrist"].cleanup()
            print("Cleaning up existing cameras done.")

            """Reload camera devices"""
            self.sensors["image"]["cam_head"].set_up(CAMERA_SERIALS['head'], is_depth=False, is_jepg=True)
            self.sensors["image"]["cam_left_wrist"].set_up(CAMERA_SERIALS['left_wrist'], is_depth=False, is_jepg=True)
            self.sensors["image"]["cam_right_wrist"].set_up(CAMERA_SERIALS['right_wrist'], is_depth=False, is_jepg=True)
            print("Cameras reloaded successfully.")
        except Exception as e:
            print(f"Error reloading cameras: {str(e)}")

    def reset(self):
        if self.teleop_mode:
            self.change_mode(teleop=False)
        time.sleep(2) # TODO
        move_data = {
            "arm": {
                "left_arm": {"joint": START_POSITION_ANGLE_LEFT_ARM[:-1], "gripper": START_POSITION_ANGLE_LEFT_ARM[-1]},
                "right_arm":{"joint": START_POSITION_ANGLE_RIGHT_ARM[:-1], "gripper":  START_POSITION_ANGLE_RIGHT_ARM[-1]}
            }
        }
        self.move(move_data)
        time.sleep(5) # TODO
        if self.teleop_mode:
            self.change_mode(teleop=True)
    
    # ======================== EXTRA ======================== #
    def change_mode(self, teleop):
        time.sleep(1) # TODO
        self.controllers["arm"]["left_arm"].change_mode(teleop)
        time.sleep(1)
        self.controllers["arm"]["right_arm"].change_mode(teleop)
        time.sleep(1)
    
    def set_map(self, map_path):
        self.controllers["mobile"]["slamware"].set_map(map_path)
