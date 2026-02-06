from robot.robot.base_robot import Robot
from robot.controller.TestArm_controller import TestArmController
from robot.sensor.TestVision_sensor import TestVisonSensor
from datetime import datetime
import time

class Dual_Test_Robot(Robot):
    def __init__(self, base_config):
        super().__init__(base_config=base_config)
        
        self.first_start = True
        self.controllers = {
            "arm":{
                "left_arm": TestArmController("left_arm"),
                "right_arm": TestArmController("right_arm"),
            },
        }
        self.sensors = {
            "image": {
                "cam_head": TestVisonSensor("cam_head"),
                "cam_left_wrist": TestVisonSensor("cam_left_wrist"),
                "cam_right_wrist": TestVisonSensor("cam_right_wrist"),
            },
        }

    def set_up(self, teleop=False):
        super().set_up()
        self.teleop_mode = teleop
        self.controllers["arm"]["left_arm"].set_up()
        self.controllers["arm"]["right_arm"].set_up()

        self.sensors["image"]["cam_head"].set_up(is_depth=False, is_jpeg=True)
        self.sensors["image"]["cam_left_wrist"].set_up(is_depth=False, is_jpeg=True)
        self.sensors["image"]["cam_right_wrist"].set_up(is_depth=False, is_jpeg=True)
        
        self.set_collect_type({"arm": ["joint", "qpos", "gripper"], "image": ["color"]})
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ✅ Setup complete.")

    def reset(self):
        super().reset()
        
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