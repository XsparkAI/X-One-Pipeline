from robot.robot.base_robot import Robot
from robot.controller.Piper_controller import PiperController
from datetime import datetime
import time

class Dual_PiperX_Master(Robot):
    def __init__(self, base_config):
        super().__init__(base_config=base_config)

        self.first_start = True
        self.controllers = { 
            "arm":{
                "left_arm": PiperController("left_arm"),
                "right_arm": PiperController("right_arm"),
            },
        }
        self.sensors = {
        }

    def set_up(self, teleop=False):
        super().set_up()
        self.teleop_mode = teleop
        self.teleop = False
        self.controllers["arm"]["left_arm"].set_up(self.robot_config['ROBOT_CAN']['left_arm'],arm_type="piper_x", teleop=self.teleop)
        self.controllers["arm"]["right_arm"].set_up(self.robot_config['ROBOT_CAN']['right_arm'], arm_type="piper_x", teleop=self.teleop)
        
        self.set_collect_type({"arm": ["joint", "eef", "gripper"]})
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ✅ Setup complete.")
    
    def reset(self):	
        self._change_mode(teleop=False)
            
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
        
        # self.move_blocking(move_data)
        self.controllers["arm"]["left_arm"].controller.move_j(move_data["arm"]["left_arm"]["joint"])
        self.controllers["arm"]["right_arm"].controller.move_j(move_data["arm"]["right_arm"]["joint"])
        self.controllers["arm"]["left_arm"].end_effector.move_gripper(move_data["arm"]["left_arm"]["gripper"])
        self.controllers["arm"]["right_arm"].end_effector.move_gripper(move_data["arm"]["right_arm"]["gripper"])

        time.sleep(2)
        
        if self.teleop_mode:
                self._change_mode(teleop=True)


    def cleanup(self):
        # TODO: decide whether to add cleanup
        pass
    
    # ======================== EXTRA ======================== #
    def _change_mode(self, teleop):
        print("teleop mode: ", teleop)
        if self.teleop == teleop:
            return 
        self.controllers["arm"]["left_arm"].change_mode(teleop)
        self.controllers["arm"]["right_arm"].change_mode(teleop)

        self.teleop = teleop
        time.sleep(0.5) # wait for mode change to take effect

if __name__ == "__main__":
    from robot.utils.base.load_file import load_yaml
    from robot.robot import get_robot

    base_cfg = load_yaml("./config/x-one-piperX-master.yml")
    robot = get_robot(base_cfg)
    
    robot.set_up()
    robot.get_obs()
    robot.reset()
