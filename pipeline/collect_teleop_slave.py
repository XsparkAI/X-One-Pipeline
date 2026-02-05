import argparse, os
from client_server.model_server import ModelServer
from robot.utils.base.load_file import load_yaml
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.robot import get_robot
import threading
import time
import types

parser = argparse.ArgumentParser()
parser.add_argument("--task_name", required=True, type=str)
parser.add_argument("--slave_robot_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--collect_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--port", type=int, required=True, help="number of evaluation episodes")
args_cli = parser.parse_args()

def main():
    port = args_cli.port
    slave_robot_cfg = load_yaml(os.path.join(CONFIG_DIR, 'robot/',f"{args_cli.slave_robot_cfg}.yml"))
    collect_cfg = load_yaml(os.path.join(CONFIG_DIR, 'collect/',f"{args_cli.collect_cfg}.yml"))

    slave_robot = get_robot(slave_robot_cfg)
    slave_robot.set_up(teleop=False)
    
    slave_robot.collect_init(collect_cfg)
    
    server = ModelServer(slave_robot, port=port)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()

    # Keep main thread alive until KeyboardInterrupt
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        server.stop()
        thread.join()

if __name__ == "__main__":
    main()