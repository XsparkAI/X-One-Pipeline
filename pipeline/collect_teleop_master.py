import argparse, os
from client_server.model_client import ModelClient
from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.data_handler import is_enter_pressed, debug_print
from robot.robot import get_robot
import time

parser = argparse.ArgumentParser()
parser.add_argument("--master_robot_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--port", type=int, required=True, help="number of evaluation episodes")
args_cli = parser.parse_args()

def main():
    port = args_cli.port
    master_robot_cfg = load_yaml(os.path.join(CONFIG_DIR, 'robot/',f"{args_cli.master_robot_cfg}.yml"))

    master_robot = get_robot(master_robot_cfg)
    master_robot.set_up(teleop=False)
    master_robot.reset()
    
    master_robot.change_mode(teleop=True)

    client = ModelClient(port=port)

    # Keep main thread alive until KeyboardInterrupt
    client.call(func_name="reset")
    client.call(func_name="start")

    while not is_enter_pressed():
        data = master_robot.get()[0]
        obs = {
            "arm": {
                "left_arm": {
                    "joint": data["left_arm"]["joint"],
                    "gripper": data["left_arm"]["gripper"],
                },
                "right_arm": {
                    "joint": data["right_arm"]["joint"],
                    "gripper": data["right_arm"]["gripper"],
                }
            }
        }
        client._send({"cmd": "move", "obs": obs}) 

        time.sleep(1 / 100)

    
    client.call(func_name="finish")
    
if __name__ == "__main__":
    main()