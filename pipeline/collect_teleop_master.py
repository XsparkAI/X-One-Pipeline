import argparse, os
from client_server.model_client import ModelClient
from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.data_handler import is_enter_pressed, flush_stdin, debug_print
from robot.robot import get_robot
import time

parser = argparse.ArgumentParser()
parser.add_argument("--master_base_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--port", type=int, required=True, help="number of evaluation episodes")
parser.add_argument("--teleop_freq", type=int, default=100, help="freq for teleop")
args_cli = parser.parse_args()

def main():
    port = args_cli.port
    master_base_cfg = load_yaml(os.path.join(CONFIG_DIR, f"{args_cli.master_base_cfg}.yml"))
    teleop_freq = args_cli.teleop_freq
    master_robot = get_robot(master_base_cfg)
    master_robot.set_up(teleop=True)
    
    client = ModelClient(port=port)

    # Keep main thread alive until KeyboardInterrupt
    step = 0

    # clean keyboard
    flush_stdin()

    while True:
        print(f"STEP: {step}")
        step += 1
        master_robot.reset()

        client.call(func_name="reset")
        client.call(func_name="start")

        debug_print("TELEOP", "Start to collect!", "INFO")

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

            time.sleep(1 / teleop_freq)

        
        client.call(func_name="finish")
    
if __name__ == "__main__":
    main()