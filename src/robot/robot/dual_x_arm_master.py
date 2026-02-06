from robot.robot.base_robot import Robot
from robot.controller.Y1_controller import Y1Controller
from robot.sensor.V4l2_sensor import V4l2Sensor
from datetime import datetime
import time

class Dual_X_Arm_master(Robot):
    def __init__(self, robot_config):
        super().__init__(robot_config=robot_config)

        self.first_start = True
        self.controllers = {
            "arm":{
                "left_arm": Y1Controller("left_arm"),
                "right_arm": Y1Controller("right_arm"),
            },
        }
        self.sensors = {
        }

    def set_up(self, teleop=False):
        super().set_up()
        self.teleop_mode = teleop
        self.controllers["arm"]["left_arm"].set_up(self.robot_config['ROBOT_CAN']['left_arm'], teleop=teleop)
        self.controllers["arm"]["right_arm"].set_up(self.robot_config['ROBOT_CAN']['right_arm'], teleop=teleop)
        
        self.set_collect_type({"arm": ["joint", "qpos", "gripper"]})
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ✅ Setup complete.")

    def reset(self):
        super().reset()
        
        if self.teleop_mode:
            self.change_mode(teleop=False)
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
            self.change_mode(teleop=True)
    
    # ======================== EXTRA ======================== #
    def change_mode(self, teleop):
        time.sleep(1) # TODO
        self.controllers["arm"]["left_arm"].change_mode(teleop)
        time.sleep(1)
        self.controllers["arm"]["right_arm"].change_mode(teleop)
        time.sleep(1)