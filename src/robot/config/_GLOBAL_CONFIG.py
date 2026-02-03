import os

current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)

ROOT_DIR = os.path.join(current_dir, "../../../")

CONFIG_DIR = os.path.join(ROOT_DIR, "config")

ROBOTS_PATH = os.path.join(ROOT_DIR, "assets/robots")
DATA_PATH = os.path.join(ROOT_DIR, "data")
COLLECT_CONFIG_PATH = os.path.join(ROOT_DIR, "collect_cfg")
