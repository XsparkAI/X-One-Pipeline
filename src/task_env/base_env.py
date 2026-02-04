from robot.robot import ROBOT_REGISTRY
from robot.robot.base_robot_node import build_robot_node

class BaseEnv:
    def __init__(self, env_cfg):
        self.episode_idx = None
        self.episode_step = 0
        # robot
        robot_type = env_cfg["robot"]["type"]
        robot_cls = ROBOT_REGISTRY[robot_type]
        if env_cfg['use_node']:
            robot_cls = build_robot_node(robot_cls)
        self.robot = robot_cls(config=env_cfg)
    
    def set_up(self, teleop=False):
        self.robot.set_up(teleop=teleop)
    
    def set_episode_idx(self, idx):
        self.episode_idx = idx
    
    def take_action(self, action):
        self.robot.move(action)
    
    def get_obs(self): # TODO: type
        return self.robot.get_obs()