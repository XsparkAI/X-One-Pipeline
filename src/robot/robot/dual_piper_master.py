from robot.robot.base_robot import Robot
from robot.controller.Piper_controller import PiperController
from robot.sensor.Orbbec_sensor import OrbbecSensor
from datetime import datetime
import time

from robot.utils.base.data_transform_pipeline import X_spark_format_pipeline
class Dual_Piper_Master(Robot):
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
        # self.collector._add_data_transform_pipeline(X_spark_format_pipeline)

    def set_up(self, teleop=False):
        super().set_up()
        self.teleop_mode = teleop
        self.teleop = False
        self.controllers["arm"]["left_arm"].set_up(self.robot_config['ROBOT_CAN']['left_arm'], teleop=self.teleop)
        self.controllers["arm"]["right_arm"].set_up(self.robot_config['ROBOT_CAN']['right_arm'], teleop=self.teleop)
        
        self.set_collect_type({"arm": ["joint", "eef", "gripper"], "image": ["color"]})
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ✅ Setup complete.")

    def reload_cameras(self):
        try:
            """Cleanup existing camera devices"""
            self.sensors["image"]["cam_head"].cleanup()
            self.sensors["image"]["cam_left_wrist"].cleanup()
            self.sensors["image"]["cam_right_wrist"].cleanup()
            print("Cleaning up existing cameras done.")

            """Reload camera devices"""
            self.sensors["image"]["cam_head"].set_up(CAMERA_SERIAL=self.robot_config['CAMERA_SERIALS']['head'], is_depth=False, is_jpeg=True)
            self.sensors["image"]["cam_left_wrist"].set_up(CAMERA_SERIAL=self.robot_config['CAMERA_SERIALS']['left_wrist'], is_depth=False, is_jpeg=True)
            self.sensors["image"]["cam_right_wrist"].set_up(CAMERA_SERIAL=self.robot_config['CAMERA_SERIALS']['right_wrist'], is_depth=False, is_jpeg=True)
            print("[INFO][camera] ✅ Cleaned up existing cameras.")
        except Exception as e:
            print(f"Error reloading cameras: {str(e)}")

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

    base_cfg = load_yaml("./config/x-one-piper-orbbec.yml")
    robot = get_robot(base_cfg)
    
    robot.set_up()
    robot.get_obs()
    robot.reset()
