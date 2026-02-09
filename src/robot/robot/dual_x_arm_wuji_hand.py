from robot.robot.base_robot import Robot
from robot.controller.Y1_controller import Y1Controller
from robot.controller.Wuji_controller import WujiController
from robot.sensor.V4l2_sensor import V4l2Sensor
from datetime import datetime
import time

class Dual_X_Arm_hand(Robot):
    def __init__(self, base_config):
        super().__init__(base_config=base_config)
        self.first_start = True
        self.controllers = {
            "arm":{
                "left_arm": Y1Controller("left_arm"),
                "right_arm": Y1Controller("right_arm"),
            },
            "hand": {
                "left_hand": WujiController("left_hand"),
                # "right_hand": WujiController("right_hand"),
            }
        }
        self.sensors = {
        }
        

    def set_up(self, teleop=False):
        super().set_up()

        self.teleop_mode = teleop

        self.controllers["arm"]["left_arm"].set_up(self.robot_config['ROBOT_CAN']['left_arm'], teleop=teleop)
        self.controllers["arm"]["right_arm"].set_up(self.robot_config['ROBOT_CAN']['right_arm'], teleop=teleop)
        self.controllers["hand"]["left_hand"].set_up("left", self.robot_config["LEFT_HAND_CFG_PATH"])
        # self.controllers["hand"]["right_hand"].set_up("right", self.robot_config["RIGHT_HAND_CFG_PATH"])
        
        self.set_collect_type({"arm": ["joint", "qpos"], "hand": ["joint"]})
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ✅ Setup complete.")

    def reset(self):
        super().reset()

        if self.teleop_mode:
            self._change_mode(teleop=False)
        time.sleep(2) # TODO
        move_data = {
            "arm": {
                "left_arm":{
                    "joint": self.robot_config['init_qpos']['left_arm'],
                    # "gripper":  self.robot_config['init_qpos']['left_gripper'],
                },
                "right_arm":{
                    "joint": self.robot_config['init_qpos']['right_arm'],
                    # "gripper":  self.robot_config['init_qpos']['right_gripper'],
                }
            },
            "hand": {
                "left_hand": {
                    "joint": self.robot_config['init_qpos']['left_hand'],
                }
            }
        }
        self.move(move_data)
        time.sleep(5)
        if self.teleop_mode:
            self._change_mode(teleop=True)
    
    # ======================== EXTRA ======================== #
    def _change_mode(self, teleop):
        time.sleep(1)
        self.controllers["arm"]["left_arm"].change_mode(teleop)
        time.sleep(1)
        self.controllers["arm"]["right_arm"].change_mode(teleop)
        time.sleep(1)