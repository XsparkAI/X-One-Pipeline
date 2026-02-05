import argparse, os
from client_server.model_server import ModelServer
from robot.utils.base.load_file import load_yaml
from robot.robot import get_robot
import threading
import time
parser = argparse.ArgumentParser()
parser.add_argument("--master_robot_cfg", type=str, required=True, help="config file name for data collection")
parser.add_argument("--port", type=int, required=True, help="number of evaluation episodes")
args_cli = parser.parse_args()

def main():
    port = args_cli.get("port")
    master_robot_cfg = load_yaml(args_cli.get(master_robot_cfg))

    master_robot = get_robot(master_robot_cfg)

    server = ModelServer(slave_robot, port)
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